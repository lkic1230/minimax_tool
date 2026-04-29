"""
配置管理模块 - API 密钥安全存储（Windows 优先 DPAPI + 多因子设备绑定）。
"""
import base64
import ctypes
import hashlib
import json
import os
import platform
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .paths import ensure_dirs, get_cache_dir, get_outputs_dir


class ConfigManager:
    """配置管理器 - 负责 API 密钥加密存储、设备绑定与读取。"""

    _FINGERPRINT_WEIGHTS = {
        "machine_guid": 8,
        "machine_name": 2,
        "system": 1,
        "machine": 1,
        "user_domain": 1,
        "username": 1,
        "mac": 1,
    }
    _STRONG_KEYS = {"machine_guid"}

    def __init__(self, config_dir: str = None):
        if config_dir is None:
            if os.name == "nt":
                config_dir = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "minimax_tool"
            else:
                config_dir = Path(os.path.expanduser("~")) / ".minimax_tool"

        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.config_file = self.config_dir / "config.enc"
        self.key_file = self.config_dir / ".key"  # 仅用于非 Windows 或兼容迁移
        self.device_file = self.config_dir / ".device"

        self._device_mismatch = False
        self._device_mismatch_reason = ""
        self._encryption_mode = "dpapi" if os.name == "nt" else "fernet"
        self._fernet: Optional[Fernet] = None

        if self._encryption_mode == "fernet":
            self._fernet = self._get_or_create_fernet()

        self._check_or_create_device_binding()
        ensure_dirs()

    # ==================== 设备指纹 ====================

    @staticmethod
    def _serialize_mac(mac_value: int) -> str:
        return ":".join(f"{(mac_value >> shift) & 0xFF:02x}" for shift in range(40, -1, -8))

    def _get_current_mac_serialized(self) -> str:
        return self._serialize_mac(uuid.getnode())

    def _get_machine_guid_windows(self) -> str:
        if os.name != "nt":
            return ""
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                value, _ = winreg.QueryValueEx(key, "MachineGuid")
                return str(value).strip().lower()
        except Exception:
            return ""

    def _collect_device_fingerprint(self) -> Dict[str, str]:
        return {
            "machine_guid": self._get_machine_guid_windows(),
            "machine_name": platform.node().strip().lower(),
            "system": platform.system().strip().lower(),
            "machine": platform.machine().strip().lower(),
            "user_domain": os.environ.get("USERDOMAIN", "").strip().lower(),
            "username": os.environ.get("USERNAME", "").strip().lower(),
            "mac": self._get_current_mac_serialized().strip().lower(),
        }

    @classmethod
    def _fingerprint_match_score(
        cls,
        stored_fp: Dict[str, str],
        current_fp: Dict[str, str],
    ) -> Tuple[int, int, bool]:
        score = 0
        max_score = 0
        strong_match = False
        for key, weight in cls._FINGERPRINT_WEIGHTS.items():
            stored_val = str(stored_fp.get(key, "")).strip().lower()
            current_val = str(current_fp.get(key, "")).strip().lower()
            if not stored_val:
                continue
            max_score += weight
            if stored_val == current_val:
                score += weight
                if key in cls._STRONG_KEYS:
                    strong_match = True
        return score, max_score, strong_match

    @classmethod
    def _fingerprint_matches(cls, stored_fp: Dict[str, str], current_fp: Dict[str, str]) -> bool:
        score, max_score, strong_match = cls._fingerprint_match_score(stored_fp, current_fp)
        if max_score <= 0:
            return False
        if strong_match:
            return True
        required = max(4, int(max_score * 0.6))
        return score >= required

    def _read_device_binding(self) -> Optional[dict]:
        if not self.device_file.exists():
            return None
        try:
            with open(self.device_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _write_device_binding(self, fingerprint: Dict[str, str]):
        payload = {
            "version": 2,
            "created_at": datetime.now().isoformat(),
            "fingerprint": fingerprint,
        }
        with open(self.device_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        try:
            os.chmod(self.device_file, 0o600)
        except Exception:
            pass

    def _legacy_binding_to_fingerprint(self, legacy_data: dict) -> Dict[str, str]:
        # 兼容旧格式：{"mac_serialized": "..."}
        mac_value = str(legacy_data.get("mac_serialized", "")).strip().lower()
        current = self._collect_device_fingerprint()
        current["mac"] = mac_value
        return current

    def _check_or_create_device_binding(self):
        current_fp = self._collect_device_fingerprint()
        data = self._read_device_binding()
        if not data:
            self._write_device_binding(current_fp)
            self._device_mismatch = False
            self._device_mismatch_reason = ""
            return

        if "fingerprint" in data:
            stored_fp = data.get("fingerprint", {})
        elif "mac_serialized" in data:
            stored_fp = self._legacy_binding_to_fingerprint(data)
        else:
            self._device_mismatch = True
            self._device_mismatch_reason = "设备绑定文件格式异常"
            return

        if self._fingerprint_matches(stored_fp, current_fp):
            # 旧格式自动升级到新格式，减少 MAC-only 带来的误判。
            if "fingerprint" not in data:
                self._write_device_binding(current_fp)
            self._device_mismatch = False
            self._device_mismatch_reason = ""
            return

        self._device_mismatch = True
        self._device_mismatch_reason = "当前运行环境与已绑定设备指纹不一致"

    # ==================== 加密实现 ====================

    def _derive_key(self, password: bytes, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password))

    def _get_machine_password(self, mac_serialized: str) -> bytes:
        machine_info = f"{platform.node()}{platform.system()}{platform.machine()}{mac_serialized}".encode()
        return hashlib.sha256(machine_info).digest()

    def _ensure_fernet(self) -> Fernet:
        if self._fernet is None:
            self._fernet = self._get_or_create_fernet()
        return self._fernet

    def _get_or_create_fernet(self) -> Fernet:
        mac_serialized = self._get_current_mac_serialized()
        if self.key_file.exists():
            with open(self.key_file, "r", encoding="utf-8") as f:
                key_data = json.load(f)
            salt = base64.b64decode(key_data["salt"])
        else:
            salt = os.urandom(16)
            with open(self.key_file, "w", encoding="utf-8") as f:
                json.dump({"salt": base64.b64encode(salt).decode()}, f)
            try:
                os.chmod(self.key_file, 0o600)
            except Exception:
                pass
        key = self._derive_key(self._get_machine_password(mac_serialized), salt)
        return Fernet(key)

    def _dpapi_encrypt(self, data: bytes) -> bytes:
        if os.name != "nt":
            raise RuntimeError("DPAPI 仅支持 Windows")

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        data_buffer = ctypes.create_string_buffer(data, len(data))
        in_blob = DATA_BLOB(len(data), ctypes.cast(data_buffer, ctypes.POINTER(ctypes.c_ubyte)))
        out_blob = DATA_BLOB()

        if not crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            "minimax_tool",
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob),
        ):
            raise OSError(ctypes.get_last_error(), "DPAPI 加密失败")

        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            if out_blob.pbData:
                kernel32.LocalFree(out_blob.pbData)

    def _dpapi_decrypt(self, encrypted_data: bytes) -> bytes:
        if os.name != "nt":
            raise RuntimeError("DPAPI 仅支持 Windows")

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        data_buffer = ctypes.create_string_buffer(encrypted_data, len(encrypted_data))
        in_blob = DATA_BLOB(len(encrypted_data), ctypes.cast(data_buffer, ctypes.POINTER(ctypes.c_ubyte)))
        out_blob = DATA_BLOB()

        if not crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob),
        ):
            raise OSError(ctypes.get_last_error(), "DPAPI 解密失败")

        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            if out_blob.pbData:
                kernel32.LocalFree(out_blob.pbData)

    def _legacy_try_decrypt_with_fernet(self, encrypted_data: bytes) -> Optional[dict]:
        # 用于 Windows 迁移：如果旧配置还是 Fernet，则尝试解密并迁移到 DPAPI。
        try:
            fernet = self._ensure_fernet()
            plain = fernet.decrypt(encrypted_data)
            return json.loads(plain.decode("utf-8"))
        except Exception:
            return None

    def _encrypt_payload(self, payload: bytes) -> bytes:
        if self._encryption_mode == "dpapi":
            return self._dpapi_encrypt(payload)
        return self._ensure_fernet().encrypt(payload)

    def _decrypt_payload(self, encrypted_data: bytes) -> Optional[bytes]:
        if self._encryption_mode == "dpapi":
            try:
                return self._dpapi_decrypt(encrypted_data)
            except Exception:
                # 兼容旧 Fernet 配置迁移
                migrated = self._legacy_try_decrypt_with_fernet(encrypted_data)
                if migrated is None:
                    return None
                # 迁移写回由 _load_config 统一处理
                return json.dumps(migrated, ensure_ascii=False).encode("utf-8")
        try:
            return self._ensure_fernet().decrypt(encrypted_data)
        except Exception:
            return None

    # ==================== 配置读写 ====================

    def _load_config(self) -> dict:
        if self._device_mismatch:
            return {}
        if not self.config_file.exists():
            return {}
        try:
            with open(self.config_file, "rb") as f:
                encrypted_data = f.read()
            plain = self._decrypt_payload(encrypted_data)
            if not plain:
                return {}
            data = json.loads(plain.decode("utf-8"))
            # Windows 模式下完成 Fernet -> DPAPI 一次性迁移
            if self._encryption_mode == "dpapi":
                if not self._is_probably_dpapi_blob(encrypted_data):
                    self._save_config(data)
            return data
        except Exception:
            return {}

    @staticmethod
    def _is_probably_dpapi_blob(encrypted_data: bytes) -> bool:
        # DPAPI 输出为二进制，旧 Fernet token 通常是 base64 文本（以 gAAAAA 开头）。
        if not encrypted_data:
            return False
        if encrypted_data.startswith(b"gAAAAA"):
            return False
        return True

    def _save_config(self, config_data: dict) -> bool:
        if self._device_mismatch:
            return False
        try:
            payload = json.dumps(config_data, ensure_ascii=False).encode("utf-8")
            encrypted_data = self._encrypt_payload(payload)
            with open(self.config_file, "wb") as f:
                f.write(encrypted_data)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    # ==================== 公开接口 ====================

    def set_api_key(self, api_key: str) -> bool:
        if self._device_mismatch:
            # 用户在本机重新录入 API Key 视为显式授权，自动重绑当前设备。
            self._write_device_binding(self._collect_device_fingerprint())
            self._device_mismatch = False
            self._device_mismatch_reason = ""
        config_data = self._load_config()
        config_data["api_key"] = api_key
        return self._save_config(config_data)

    def get_api_key(self) -> str:
        return self._load_config().get("api_key", "")

    def has_api_key(self) -> bool:
        return bool(self.get_api_key())

    def delete_api_key(self) -> bool:
        config_data = self._load_config()
        if "api_key" in config_data:
            del config_data["api_key"]
        if not config_data:
            try:
                if self.config_file.exists():
                    self.config_file.unlink()
                return True
            except Exception as e:
                print(f"删除配置文件失败: {e}")
                return False
        return self._save_config(config_data)

    def set_output_dir(self, output_dir: str) -> bool:
        config_data = self._load_config()
        config_data["output_dir"] = output_dir
        return self._save_config(config_data)

    def get_output_dir(self) -> str:
        output_dir = self._load_config().get("output_dir", "")
        if output_dir:
            return output_dir
        return str(get_outputs_dir())

    def set_show_thinking(self, show_thinking: bool) -> bool:
        config_data = self._load_config()
        config_data["show_thinking"] = bool(show_thinking)
        return self._save_config(config_data)

    def get_show_thinking(self) -> bool:
        return bool(self._load_config().get("show_thinking", False))

    def get_config_info(self) -> dict:
        cached_dir = self.get_cached_output_dir()
        output_dir = cached_dir if cached_dir else self.get_output_dir()
        return {
            "has_api_key": self.has_api_key(),
            "api_key_preview": self._mask_api_key(self.get_api_key()) if self.has_api_key() else None,
            "config_dir": str(self.config_dir),
            "output_dir": output_dir,
            "default_output_dir": str(get_outputs_dir()),
            "cache_dir": str(get_cache_dir()),
            "device_bound": self.device_file.exists(),
            "device_match": not self._device_mismatch,
            "device_mismatch_reason": self._device_mismatch_reason or None,
            "encryption_mode": self._encryption_mode,
        }

    def _mask_api_key(self, api_key: str) -> str:
        if len(api_key) <= 8:
            return "*" * len(api_key)
        return api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]

    def get_cached_output_dir(self) -> str:
        cache_file = get_cache_dir() / "output_dir_cache.txt"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_path = f.read().strip()
                if cached_path and Path(cached_path).exists():
                    return cached_path
            except Exception:
                pass
        return ""

    def cache_output_dir(self, output_dir: str) -> bool:
        try:
            cache_file = get_cache_dir() / "output_dir_cache.txt"
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(output_dir)
            return True
        except Exception as e:
            print(f"缓存输出目录失败: {e}")
            return False

    def get_default_output_dir(self) -> str:
        return str(get_outputs_dir())

    def clear_cache(self) -> bool:
        """清除缓存目录内容（保留目录本身）。"""
        import shutil

        cache_dir = get_cache_dir()
        if cache_dir.exists():
            try:
                for item in cache_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                return True
            except Exception as e:
                print(f"清除缓存失败: {e}")
                return False
        return True

    def clear_all_data(self) -> dict:
        """
        清除所有本地数据（API 密钥、加密密钥、设备绑定、缓存）。
        返回清除结果摘要。
        """
        result = {
            "config_deleted": False,
            "key_deleted": False,
            "device_deleted": False,
            "cache_cleared": False,
        }

        if self.config_file.exists():
            try:
                self.config_file.unlink()
                result["config_deleted"] = True
            except Exception as e:
                print(f"删除配置文件失败: {e}")

        if self.key_file.exists():
            try:
                self.key_file.unlink()
                result["key_deleted"] = True
            except Exception as e:
                print(f"删除密钥文件失败: {e}")

        if self.device_file.exists():
            try:
                self.device_file.unlink()
                result["device_deleted"] = True
            except Exception as e:
                print(f"删除设备绑定文件失败: {e}")

        result["cache_cleared"] = self.clear_cache()

        self._device_mismatch = False
        self._device_mismatch_reason = ""
        self._fernet = None
        if self._encryption_mode == "fernet":
            self._fernet = self._get_or_create_fernet()
        self._check_or_create_device_binding()
        return result

    def bind_device(self, force: bool = False) -> bool:
        current_fp = self._collect_device_fingerprint()
        data = self._read_device_binding()
        if data and not force:
            stored_fp = data.get("fingerprint", {})
            if not stored_fp and "mac_serialized" in data:
                stored_fp = self._legacy_binding_to_fingerprint(data)
            if not self._fingerprint_matches(stored_fp, current_fp):
                self._device_mismatch = True
                self._device_mismatch_reason = "当前设备与已有绑定不一致，需 --force 重绑"
                return False

        self._write_device_binding(current_fp)
        self._device_mismatch = False
        self._device_mismatch_reason = ""
        return True


_config_manager = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例。"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

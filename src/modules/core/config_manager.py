"""
配置管理模块 - 加密存储API密钥
"""
import os
import json
import base64
import hashlib
import uuid
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .paths import get_outputs_dir, get_cache_dir, ensure_dirs


class ConfigManager:
    """配置管理器 - 负责API密钥的安全存储和读取。"""

    def __init__(self, config_dir: str = None):
        if config_dir is None:
            if os.name == "nt":
                config_dir = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "minimax_tool"
            else:
                config_dir = Path(os.path.expanduser("~")) / ".minimax_tool"

        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.config_file = self.config_dir / "config.enc"
        self.key_file = self.config_dir / ".key"
        self.device_file = self.config_dir / ".device"
        self._device_mismatch = False
        self._fernet = self._get_or_create_fernet()
        if self._device_mismatch:
            self._reset_after_device_mismatch()
        ensure_dirs()

    def _derive_key(self, password: bytes, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password))

    def _get_or_create_fernet(self) -> Fernet:
        device_serialized_mac = self._get_or_create_device_binding()
        if device_serialized_mac is None:
            self._device_mismatch = True
            device_serialized_mac = ""

        if self.key_file.exists():
            with open(self.key_file, "rb") as f:
                key_data = json.load(f)
            salt = base64.b64decode(key_data["salt"])
            password = self._get_machine_password(device_serialized_mac)
            key = self._derive_key(password, salt)
        else:
            salt = os.urandom(16)
            password = self._get_machine_password(device_serialized_mac)
            key = self._derive_key(password, salt)
            with open(self.key_file, "w") as f:
                json.dump({"salt": base64.b64encode(salt).decode()}, f)
            try:
                os.chmod(self.key_file, 0o600)
            except Exception:
                pass
        return Fernet(key)

    @staticmethod
    def _serialize_mac(mac_value: int) -> str:
        return ":".join(f"{(mac_value >> shift) & 0xFF:02x}" for shift in range(40, -1, -8))

    def _get_current_mac_serialized(self) -> str:
        return self._serialize_mac(uuid.getnode())

    def _get_or_create_device_binding(self) -> Optional[str]:
        current_mac = self._get_current_mac_serialized()
        if self.device_file.exists():
            try:
                with open(self.device_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                stored_mac = str(data.get("mac_serialized", "")).strip().lower()
                return stored_mac if stored_mac == current_mac else None
            except Exception:
                return None

        self._write_device_binding(current_mac)
        return current_mac

    def _write_device_binding(self, mac_serialized: str):
        with open(self.device_file, "w", encoding="utf-8") as f:
            json.dump({"mac_serialized": mac_serialized}, f)
        try:
            os.chmod(self.device_file, 0o600)
        except Exception:
            pass

    def _get_machine_password(self, mac_serialized: str) -> bytes:
        import platform

        machine_info = f"{platform.node()}{platform.system()}{platform.machine()}{mac_serialized}".encode()
        return hashlib.sha256(machine_info).digest()

    def _reset_after_device_mismatch(self):
        self.clear_cache()
        for file_path in [self.config_file, self.key_file, self.device_file]:
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception:
                    pass
        current_mac = self._get_current_mac_serialized()
        self._write_device_binding(current_mac)
        self._device_mismatch = False
        self._fernet = self._get_or_create_fernet()

    def _load_config(self) -> dict:
        if self._device_mismatch:
            return {}
        if not self.config_file.exists():
            return {}
        try:
            with open(self.config_file, "rb") as f:
                encrypted_data = f.read()
            decrypted_data = self._fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception:
            return {}

    def _save_config(self, config_data: dict) -> bool:
        if self._device_mismatch:
            return False
        try:
            encrypted_data = self._fernet.encrypt(json.dumps(config_data).encode())
            with open(self.config_file, "wb") as f:
                f.write(encrypted_data)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    def set_api_key(self, api_key: str) -> bool:
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
        清除所有本地数据（API 密钥、加密密钥、缓存）。
        返回清除结果摘要。
        """
        result = {
            "config_deleted": False,
            "key_deleted": False,
            "device_deleted": False,
            "cache_cleared": False
        }

        # 删除加密配置文件
        if self.config_file.exists():
            try:
                self.config_file.unlink()
                result["config_deleted"] = True
            except Exception as e:
                print(f"删除配置文件失败: {e}")

        # 删除加密密钥文件
        if self.key_file.exists():
            try:
                self.key_file.unlink()
                result["key_deleted"] = True
            except Exception as e:
                print(f"删除密钥文件失败: {e}")

        # 删除设备绑定文件
        if self.device_file.exists():
            try:
                self.device_file.unlink()
                result["device_deleted"] = True
            except Exception as e:
                print(f"删除设备绑定文件失败: {e}")

        # 清除缓存
        result["cache_cleared"] = self.clear_cache()

        # 重新创建 Fernet（会生成新密钥）
        self._device_mismatch = False
        self._fernet = self._get_or_create_fernet()

        return result

    def bind_device(self, force: bool = False) -> bool:
        current_mac = self._get_current_mac_serialized()
        if self.device_file.exists() and not force:
            try:
                with open(self.device_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                stored_mac = str(data.get("mac_serialized", "")).strip().lower()
                if stored_mac and stored_mac != current_mac:
                    self._device_mismatch = True
                    return False
            except Exception:
                return False
        self._write_device_binding(current_mac)
        self._device_mismatch = False
        self._fernet = self._get_or_create_fernet()
        return True


_config_manager = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例。"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

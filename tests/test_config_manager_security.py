import tempfile
import unittest
from unittest.mock import patch

from minimax_tool.src.modules.core.config_manager import ConfigManager


class TestConfigManagerSecurity(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)

    def _make_manager_with_fingerprint(self, fingerprint: dict) -> ConfigManager:
        with patch.object(ConfigManager, "_collect_device_fingerprint", return_value=fingerprint):
            return ConfigManager(config_dir=self._tmp_dir.name)

    def test_fingerprint_match_with_strong_factor(self):
        stored = {
            "machine_guid": "guid-1",
            "machine_name": "pc-a",
            "system": "windows",
            "machine": "amd64",
            "user_domain": "domain",
            "username": "user",
            "mac": "aa:bb:cc:dd:ee:ff",
        }
        current = {
            "machine_guid": "guid-1",
            "machine_name": "pc-b",
            "system": "windows",
            "machine": "amd64",
            "user_domain": "domain2",
            "username": "user2",
            "mac": "11:22:33:44:55:66",
        }
        self.assertTrue(ConfigManager._fingerprint_matches(stored, current))

    def test_fingerprint_mismatch_without_strong_factor(self):
        stored = {
            "machine_guid": "",
            "machine_name": "pc-a",
            "system": "windows",
            "machine": "amd64",
            "user_domain": "domain",
            "username": "user",
            "mac": "aa:bb:cc:dd:ee:ff",
        }
        current = {
            "machine_guid": "",
            "machine_name": "pc-b",
            "system": "windows",
            "machine": "amd64",
            "user_domain": "domain-x",
            "username": "user-x",
            "mac": "11:22:33:44:55:66",
        }
        self.assertFalse(ConfigManager._fingerprint_matches(stored, current))

    def test_bind_device_requires_force_when_mismatch(self):
        first_fp = {
            "machine_guid": "guid-a",
            "machine_name": "pc-a",
            "system": "windows",
            "machine": "amd64",
            "user_domain": "domain",
            "username": "user",
            "mac": "aa:bb:cc:dd:ee:ff",
        }
        second_fp = {
            "machine_guid": "guid-b",
            "machine_name": "pc-b",
            "system": "windows",
            "machine": "amd64",
            "user_domain": "domain",
            "username": "user",
            "mac": "11:22:33:44:55:66",
        }

        manager = self._make_manager_with_fingerprint(first_fp)
        with patch.object(ConfigManager, "_collect_device_fingerprint", return_value=second_fp):
            self.assertFalse(manager.bind_device(force=False))
            self.assertTrue(manager.bind_device(force=True))

    def test_set_api_key_auto_rebinds_on_mismatch(self):
        first_fp = {
            "machine_guid": "guid-a",
            "machine_name": "pc-a",
            "system": "windows",
            "machine": "amd64",
            "user_domain": "domain",
            "username": "user",
            "mac": "aa:bb:cc:dd:ee:ff",
        }
        second_fp = {
            "machine_guid": "guid-b",
            "machine_name": "pc-b",
            "system": "windows",
            "machine": "amd64",
            "user_domain": "domain",
            "username": "user",
            "mac": "11:22:33:44:55:66",
        }
        manager = self._make_manager_with_fingerprint(first_fp)
        with patch.object(ConfigManager, "_collect_device_fingerprint", return_value=second_fp):
            self.assertFalse(manager.bind_device(force=False))
            self.assertTrue(manager.set_api_key("sk-test-1234"))
            info = manager.get_config_info()
            self.assertTrue(info["device_match"])
            self.assertTrue(info["has_api_key"])


if __name__ == "__main__":
    unittest.main()

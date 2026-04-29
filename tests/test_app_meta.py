import json
import os
import tempfile
import unittest

from minimax_tool.src.modules.core.app_meta import get_app_meta


class TestAppMeta(unittest.TestCase):
    def test_load_from_env_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = os.path.join(tmp, "app_config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "app_name": "MyApp",
                        "display_name": "我的应用",
                        "version": "2.3.4",
                        "organization": "ACME",
                    },
                    f,
                    ensure_ascii=False,
                )
            old = os.environ.get("MINIMAX_APP_CONFIG")
            os.environ["MINIMAX_APP_CONFIG"] = config_path
            try:
                meta = get_app_meta()
            finally:
                if old is None:
                    os.environ.pop("MINIMAX_APP_CONFIG", None)
                else:
                    os.environ["MINIMAX_APP_CONFIG"] = old

            self.assertEqual(meta["app_name"], "MyApp")
            self.assertEqual(meta["display_name"], "我的应用")
            self.assertEqual(meta["version"], "2.3.4")
            self.assertEqual(meta["organization"], "ACME")


if __name__ == "__main__":
    unittest.main()

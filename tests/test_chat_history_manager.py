import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from minimax_tool.src.modules.ui.components.chat_history_manager import ChatHistoryManager


class TestChatHistoryManager(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)
        self.manager = ChatHistoryManager(cache_dir=self._tmp_dir.name)

    def test_save_generates_full_uuid_id(self):
        conv_id = self.manager.save(
            title="",
            messages=[{"role": "user", "content": "hello"}],
            model="chat-model",
            max_tokens=256,
            temperature=0.7,
            top_p=0.9,
        )
        self.assertEqual(len(conv_id), 36)
        self.assertTrue((Path(self._tmp_dir.name) / f"{conv_id}.json").exists())

    def test_generate_conv_id_retries_on_collision(self):
        first = "11111111-1111-1111-1111-111111111111"
        second = "22222222-2222-2222-2222-222222222222"
        (Path(self._tmp_dir.name) / f"{first}.json").write_text("{}", encoding="utf-8")

        with patch("minimax_tool.src.modules.ui.components.chat_history_manager.uuid.uuid4", side_effect=[first, second]):
            conv_id = self.manager._generate_conv_id()

        self.assertEqual(conv_id, second)

    def test_generate_title_handles_missing_content(self):
        title = self.manager._generate_title([{"role": "user"}, {"role": "assistant", "content": "x"}])
        self.assertEqual(title, "新对话")

    def test_save_uses_fallback_title_when_title_empty(self):
        conv_id = self.manager.save(
            title="",
            messages=[{"role": "user", "content": "第一条用户消息标题"}],
            model="chat-model",
            max_tokens=256,
            temperature=0.7,
            top_p=0.9,
        )
        data = self.manager.load(conv_id)
        self.assertEqual(data["title"], "第一条用户消息标题")


if __name__ == "__main__":
    unittest.main()

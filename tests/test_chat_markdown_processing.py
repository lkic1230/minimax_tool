import unittest

from minimax_tool.src.modules.ui.components.chat_message_widget import _resolve_markdown_copy_payload
from minimax_tool.src.modules.ui.tabs.chat_tab import ChatTabWidget


class TestMarkdownCopyPayload(unittest.TestCase):
    def test_copy_raw_uses_markdown_source(self):
        payload = _resolve_markdown_copy_payload(
            copy_raw=True,
            raw_content="**bold**",
            selected_text="bold",
            plain_text="bold",
        )
        self.assertEqual(payload, "**bold**")

    def test_copy_plain_prefers_selected_text(self):
        payload = _resolve_markdown_copy_payload(
            copy_raw=False,
            raw_content="**bold**",
            selected_text="line1\u2029line2",
            plain_text="line1\nline2\nline3",
        )
        self.assertEqual(payload, "line1\nline2")

    def test_copy_plain_falls_back_to_full_plain_text(self):
        payload = _resolve_markdown_copy_payload(
            copy_raw=False,
            raw_content="**bold**",
            selected_text="",
            plain_text="bold",
        )
        self.assertEqual(payload, "bold")


class TestStripThinkingContent(unittest.TestCase):
    def test_strip_regular_think_block(self):
        text = "前文\n<think>internal reasoning</think>\n正文"
        cleaned = ChatTabWidget._strip_thinking_content(text)
        self.assertEqual(cleaned, "前文\n\n正文")

    def test_keep_think_tag_inside_fenced_code_block(self):
        text = "说明\n```xml\n<think>keep me</think>\n```\n尾部"
        cleaned = ChatTabWidget._strip_thinking_content(text)
        self.assertIn("<think>keep me</think>", cleaned)
        self.assertIn("```xml", cleaned)
        self.assertTrue(cleaned.endswith("尾部"))

    def test_strip_standalone_think_tags(self):
        text = "A</think>\nB<think id='x'>\nC"
        cleaned = ChatTabWidget._strip_thinking_content(text)
        self.assertEqual(cleaned, "A\nB")


if __name__ == "__main__":
    unittest.main()

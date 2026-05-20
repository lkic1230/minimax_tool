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
        text = "\u524d\u6587\n\U0001f9e0internal reasoning\U0001f9e0\n\u6b63\u6587"
        cleaned = ChatTabWidget._strip_thinking_content(text)
        self.assertEqual(cleaned, "\u524d\u6587\n\n\u6b63\u6587")

    def test_keep_think_tag_inside_fenced_code_block(self):
        text = "\u8bf4\u660e\n```xml\n\U0001f9e0keep me\U0001f9e0\n```\n\u5c3e\u90e8"
        cleaned = ChatTabWidget._strip_thinking_content(text)
        self.assertIn("\U0001f9e0keep me\U0001f9e0", cleaned)
        self.assertIn("```xml", cleaned)
        self.assertTrue(cleaned.endswith("\u5c3e\u90e8"))

    def test_strip_standalone_think_tags(self):
        text = "A\U0001f9e0\nB<think id='x'>\nC"
        cleaned = ChatTabWidget._strip_thinking_content(text)
        # Single brain emoji not matched by paired format4,
        # <think> without </think> not matched by format1
        self.assertIn("A", cleaned)
        self.assertIn("B", cleaned)
        self.assertIn("C", cleaned)
        self.assertNotIn("<think", cleaned)


if __name__ == "__main__":
    unittest.main()

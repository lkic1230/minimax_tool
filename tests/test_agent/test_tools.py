"""
Test Tools - 工具测试。
"""
import unittest
from pathlib import Path
from src.modules.tools.web_search import WebSearchTool
from src.modules.tools.web_scrape import WebScrapeTool
from src.modules.tools.file_ops import FileReadTool, FileWriteTool


class TestWebSearchTool(unittest.TestCase):
    """测试联网搜索工具"""
    
    def setUp(self):
        self.tool = WebSearchTool()
        
    def test_validate(self):
        """测试参数校验"""
        self.assertTrue(self.tool.validate({"query": "test"}))
        self.assertFalse(self.tool.validate({}))
        self.assertFalse(self.tool.validate({"query": ""}))
        
    def test_execute(self):
        """测试执行搜索"""
        result = self.tool.execute(query="Python", max_results=2)
        self.assertTrue(result.success)
        self.assertIn("results", result.data)


class TestWebScrapeTool(unittest.TestCase):
    """测试网页抓取工具"""
    
    def setUp(self):
        self.tool = WebScrapeTool()
        
    def test_validate(self):
        """测试参数校验"""
        self.assertTrue(self.tool.validate({"url": "https://example.com"}))
        self.assertFalse(self.tool.validate({}))
        self.assertFalse(self.tool.validate({"url": "not_a_url"}))


class TestFileTools(unittest.TestCase):
    """测试文件工具"""
    
    def setUp(self):
        self.base_dir = "d:/Custom AI App/minimax_tool"
        self.read_tool = FileReadTool(base_dir=self.base_dir)
        self.write_tool = FileWriteTool(base_dir=self.base_dir)
        
    def test_file_write(self):
        """测试文件写入"""
        result = self.write_tool.execute(
            path="outputs/test_cli.txt",
            content="Test content",
            append=False
        )
        self.assertTrue(result.success)
        
    def test_file_read(self):
        """测试文件读取"""
        # 先写入
        self.write_tool.execute(
            path="outputs/test_cli.txt",
            content="Test content",
            append=False
        )
        # 再读取
        result = self.read_tool.execute(path="outputs/test_cli.txt")
        self.assertTrue(result.success)
        self.assertIn("Test", result.data.get("content", ""))


if __name__ == "__main__":
    unittest.main()
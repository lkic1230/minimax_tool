"""
Test Tool Framework - 工具框架测试。
"""
import unittest
from src.modules.agent.tool_framework import (
    BaseTool, ToolResult, ToolRegistry, ToolExecutor
)


class TestToolResult(unittest.TestCase):
    """测试 ToolResult"""
    
    def test_success_result(self):
        """测试成功结果"""
        result = ToolResult(success=True, data={"key": "value"})
        self.assertTrue(result.success)
        self.assertEqual(result.data["key"], "value")
        
    def test_error_result(self):
        """测试错误结果"""
        result = ToolResult(success=False, error="Error message")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Error message")


class MockTool(BaseTool):
    """测试工具"""
    
    name = "mock_tool"
    description = "Mock tool for testing"
    
    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, data=kwargs)
        
    def validate(self, params) -> bool:
        return "value" in params


class TestToolRegistry(unittest.TestCase):
    """测试工具注册表"""
    
    def setUp(self):
        self.registry = ToolRegistry()
        
    def test_register_tool(self):
        """测试工具注册"""
        tool = MockTool()
        self.registry.register(tool)
        self.assertIsNotNone(self.registry.get("mock_tool"))
        
    def test_get_tool(self):
        """测试获取工具"""
        tool = MockTool()
        self.registry.register(tool)
        retrieved = self.registry.get("mock_tool")
        self.assertEqual(retrieved.name, "mock_tool")
        
    def test_list_tools(self):
        """测试列出工具"""
        tool = MockTool()
        self.registry.register(tool)
        tools = self.registry.list_tools()
        self.assertIn("mock_tool", tools)


class TestToolExecutor(unittest.TestCase):
    """测试工具执行器"""
    
    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(MockTool())
        self.executor = ToolExecutor(self.registry)
        
    def test_execute_success(self):
        """测试成功执行"""
        result = self.executor.execute("mock_tool", {"value": "test"})
        self.assertTrue(result.success)
        
    def test_execute_invalid_tool(self):
        """测试无效工具"""
        result = self.executor.execute("non_existent", {})
        self.assertFalse(result.success)
        self.assertIn("不存在", result.error)


if __name__ == "__main__":
    unittest.main()
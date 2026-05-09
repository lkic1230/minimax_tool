"""
Agent Tool Framework - 工具调用框架核心模块。

包含：
- BaseTool: 工具基类
- ToolResult: 工具执行结果
- ToolRegistry: 工具注册表
- ToolExecutor: 工具执行器
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"        # 待执行
    RUNNING = "running"        # 执行中
    PAUSED = "paused"        # 已暂停
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"        # 已失败
    CANCELLED = "cancelled"  # 已取消
    WAITING_CONFIRM = "waiting_confirm"  # 待确认


class StepStatus(Enum):
    """步骤状态枚举"""
    WAITING = "waiting"      # 等待中
    RUNNING = "running"      # 执行中
    SUCCESS = "success"    # 成功
    FAILED = "failed"     # 失败


@dataclass
class ToolResult:
    """工具执行结果标准化"""
    success: bool = False
    data: Any = None
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """工具抽象基类"""

    name: str = ""
    description: str = ""
    parameters_schema: Dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """执行工具并返回标准化结果"""
        pass

    def validate(self, params: Dict[str, Any]) -> bool:
        """校验参数合法性"""
        return True


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._aliases: Dict[str, str] = {}

    def register(self, tool: BaseTool) -> None:
        """注册工具"""
        if not tool.name:
            raise ValueError("工具名称不能为空")
        self._tools[tool.name] = tool

    def register_function(
        self,
        name: str,
        description: str,
        func: Callable,
        schema: Optional[Dict] = None
    ) -> None:
        """注册函数为工具"""
        self._tools[name] = _FunctionTool(name, description, func, schema or {})

    def get(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        tool_name = self._aliases.get(name, name)
        return self._tools.get(tool_name)

    def list_tools(self) -> Dict[str, str]:
        """列出所有工具"""
        return {name: tool.description for name, tool in self._tools.items()}

    def add_alias(self, alias: str, tool_name: str) -> None:
        """添加工具别名"""
        self._aliases[alias] = tool_name


class _FunctionTool(BaseTool):
    """函数工具封装"""

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable,
        schema: Dict[str, Any]
    ):
        self.name = name
        self.description = description
        self.func = func
        self.parameters_schema = schema

    def execute(self, **kwargs) -> ToolResult:
        try:
            result = self.func(**kwargs)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ToolExecutor:
    """工具执行器"""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(
        self,
        tool_name: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """执行工具"""
        tool = self.registry.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"工具不存在: {tool_name}"
            )

        params = parameters or {}
        if not tool.validate(params):
            return ToolResult(
                success=False,
                error="参数校验失败"
            )

        try:
            return tool.execute(**params)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
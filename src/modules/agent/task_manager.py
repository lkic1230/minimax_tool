"""
Task Manager - 任务状态管理模块。

包含：
- TaskStatus: 任务状态枚举
- StepStatus: 步骤状态枚举
- Task: 任务数据模型
- Step: 步骤数据模型
- TaskManager: 任务管理器
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"          # 待执行
    RUNNING = "running"          # 执行中
    PAUSED = "paused"          # 已暂停
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"         # 已失败
    CANCELLED = "cancelled"    # 已取消
    WAITING_CONFIRM = "waiting_confirm"  # 待确认


class StepStatus(Enum):
    """步骤状态枚举"""
    WAITING = "waiting"       # 等待中
    RUNNING = "running"       # 执行中
    SUCCESS = "success"     # 成功
    FAILED = "failed"      # 失败


@dataclass
class Step:
    """步骤数据模型"""
    index: int
    name: str
    description: str = ""

    status: StepStatus = StepStatus.WAITING
    tool_name: str = ""
    tool_input: Dict[str, Any] = field(default_factory=dict)
    tool_output: Dict[str, Any] = field(default_factory=dict)

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: str = ""

    def duration(self) -> float:
        """计算步骤耗时(秒)"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0


@dataclass
class Task:
    """任务数据模型"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal: str = ""                      # 任务目标
    constraints: Dict[str, Any] = field(default_factory=dict)  # 约束条件

    status: TaskStatus = TaskStatus.PENDING
    current_step: int = 0             # 当前步骤索引
    steps: List[Step] = field(default_factory=list)

    # 结果
    conclusion: str = ""                # 结论摘要
    sources: List[Dict[str, str]] = field(default_factory=list)  # 来源
    pending_items: List[str] = field(default_factory=list)   # 待确认项

    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_step(self, name: str, description: str = "", tool_name: str = "") -> Step:
        """添加步骤"""
        step = Step(
            index=len(self.steps),
            name=name,
            description=description,
            tool_name=tool_name
        )
        self.steps.append(step)
        return step

    def get_current_step(self) -> Optional[Step]:
        """获取当前步骤"""
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None

    def next_step(self) -> None:
        """进入下一步"""
        if self.current_step < len(self.steps) - 1:
            self.current_step += 1

    def duration(self) -> float:
        """计算任务总耗时(秒)"""
        if self.steps:
            first = self.steps[0]
            last = self.steps[-1]
            if first.started_at and last.completed_at:
                return (last.completed_at - first.started_at).total_seconds()
        return 0.0


class TaskManager:
    """任务管理器"""

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._callbacks: Dict[str, callable] = {}

    def create_task(self, goal: str, constraints: Optional[Dict] = None) -> Task:
        """创建任务"""
        task = Task(
            goal=goal,
            constraints=constraints or {}
        )
        self._tasks[task.id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)

    def list_tasks(self) -> List[Task]:
        """列出所有任务"""
        return list(self._tasks.values())

    def start_task(self, task_id: str) -> bool:
        """开始任务"""
        task = self.get_task(task_id)
        if not task:
            return False
        task.status = TaskStatus.RUNNING
        step = task.get_current_step()
        if step:
            step.status = StepStatus.RUNNING
            step.started_at = datetime.now()
        return True

    def complete_step(self, task_id: str, output: Dict[str, Any]) -> bool:
        """完成当前步骤"""
        task = self.get_task(task_id)
        if not task:
            return False
        step = task.get_current_step()
        if step:
            step.status = StepStatus.SUCCESS
            step.tool_output = output
            step.completed_at = datetime.now()
            task.next_step()
            next_step = task.get_current_step()
            if next_step:
                next_step.status = StepStatus.RUNNING
                next_step.started_at = datetime.now()
            else:
                task.status = TaskStatus.COMPLETED
        return True

    def fail_step(self, task_id: str, error: str) -> bool:
        """步骤失败"""
        task = self.get_task(task_id)
        if not task:
            return False
        step = task.get_current_step()
        if step:
            step.status = StepStatus.FAILED
            step.error = error
            step.completed_at = datetime.now()
            task.status = TaskStatus.FAILED
        return True

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self.get_task(task_id)
        if not task:
            return False
        task.status = TaskStatus.CANCELLED
        return True

    def retry_step(self, task_id: str) -> bool:
        """重试当前步骤"""
        task = self.get_task(task_id)
        if not task:
            return False
        step = task.get_current_step()
        if step and step.status == StepStatus.FAILED:
            step.status = StepStatus.RUNNING
            step.error = ""
            step.started_at = datetime.now()
            task.status = TaskStatus.RUNNING
            return True
        return False
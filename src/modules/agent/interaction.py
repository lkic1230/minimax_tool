"""
Interaction Controller - 交互控制模块。

包含：
- ConfirmCallback: 用户确认回调
- InterruptHandler: 中断处理器
- RetryManager: 重试管理器
- ResultExporter: 结果导出器
"""
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class ConfirmLevel(Enum):
    """确认级别"""
    LOW = "low"      # 低风险，自动确认
    MEDIUM = "medium" # 中风险，需要确认
    HIGH = "high"    # 高风险，必须确认
    CRITICAL = "critical"  # 极高风险，需二次确认


@dataclass
class ConfirmRequest:
    """确认请求"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    step_id: str = ""
    message: str = ""
    level: ConfirmLevel = ConfirmLevel.MEDIUM
    timestamp: datetime = field(default_factory=datetime.now)
    confirmed: Optional[bool] = None
    confirmed_at: Optional[datetime] = None
    
    def is_expired(self, timeout_seconds: int = 300) -> bool:
        """检查是否超时"""
        delta = datetime.now() - self.timestamp
        return delta.total_seconds() > timeout_seconds


class ConfirmCallback(ABC):
    """用户确认回调抽象类"""
    
    @abstractmethod
    def request_confirm(self, request: ConfirmRequest) -> bool:
        """请求用户确认，返回 True 表示确认"""
        pass
    
    def should_auto_confirm(self, level: ConfirmLevel) -> bool:
        """检查是否应该自动确认"""
        return level == ConfirmLevel.LOW


class ConsoleConfirmCallback(ConfirmCallback):
    """控制台确认回调"""
    
    def __init__(self, auto_approve: bool = False):
        self.auto_approve = auto_approve
        
    def request_confirm(self, request: ConfirmRequest) -> bool:
        """请求用户确认"""
        if self.auto_approve or request.level == ConfirmLevel.LOW:
            return True
            
        print(f"\n⚠️  确认请求 [{request.level.value.upper()}]")
        print(f"   {request.message}")
        print(f"   (y/n): ", end="")
        
        try:
            response = input().strip().lower()
            return response in ("y", "yes", "是")
        except EOFError:
            return False


class InterruptHandler:
    """中断处理器"""
    
    def __init__(self):
        self._interrupted = False
        self._callbacks: List[Callable[[], None]] = []
        
    def interrupt(self) -> None:
        """触发中断"""
        self._interrupted = True
        for callback in self._callbacks:
            try:
                callback()
            except Exception:
                pass
                
    def is_interrupted(self) -> bool:
        """检查是否中断"""
        return self._interrupted
        
    def reset(self) -> None:
        """重置中断状态"""
        self._interrupted = False
        
    def register_callback(self, callback: Callable[[], None]) -> None:
        """注册中断回调"""
        self._callbacks.append(callback)


class RetryPolicy(Enum):
    """重试策略"""
    IMMEDIATE = "immediate"      # 立即重试
    LINEAR = "linear"           # 线性间隔
    EXPONENTIAL = "exponential" # 指数退避
    FIBONACCI = "fibonacci"     # 斐波那契间隔


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    initial_delay: float = 1.0  # 秒
    max_delay: float = 60.0
    policy: RetryPolicy = RetryPolicy.EXPONENTIAL
    

class RetryManager:
    """重试管理器"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self._attempt_counts: Dict[str, int] = {}
        
    def should_retry(self, task_id: str, step_id: str = "") -> bool:
        """检查是否应该重试"""
        key = f"{task_id}:{step_id}"
        current = self._attempt_counts.get(key, 0)
        return current < self.config.max_attempts
        
    def recordAttempt(self, task_id: str, step_id: str = "") -> int:
        """记录重试次数"""
        key = f"{task_id}:{step_id}"
        self._attempt_counts[key] = self._attempt_counts.get(key, 0) + 1
        return self._attempt_counts[key]
        
    def get_retry_delay(self, task_id: str, step_id: str = "") -> float:
        """计算重试延迟"""
        key = f"{task_id}:{step_id}"
        attempt = self._attempt_counts.get(key, 1)
        
        delay = self.config.initial_delay
        if self.config.policy == RetryPolicy.LINEAR:
            delay = delay * (attempt - 1)
        elif self.config.policy == RetryPolicy.EXPONENTIAL:
            delay = delay * (2 ** (attempt - 2))
        elif self.config.policy == RetryPolicy.FIBONACCI:
            a, b = 1, 1
            for _ in range(attempt - 2):
                a, b = b, a + b
            delay = delay * a
            
        return min(delay, self.config.max_delay)
        
    def reset(self, task_id: str = None) -> None:
        """重置重试计数"""
        if task_id:
            keys = [k for k in self._attempt_counts if k.startswith(task_id)]
            for key in keys:
                del self._attempt_counts[key]
        else:
            self._attempt_counts.clear()


class ResultExporter:
    """结果导出器"""
    
    def __init__(self, base_dir: str = "outputs"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
    def export_text(self, task, path: Optional[str] = None) -> str:
        """导出为文本"""
        if not path:
            path = self.base_dir / f"task_{task.id[:8]}.txt"
        else:
            path = Path(path)
            
        lines = [
            f"# 任务结果",
            f"# ID: {task.id}",
            f"# 目标: {task.goal}",
            f"# 状态: {task.status.value}",
            f"# 创建时间: {task.created_at.isoformat()}",
            f"",
            f"## 结论",
            f"{task.conclusion}",
            f"",
            f"## 来源",
        ]
        
        for source in task.sources:
            lines.append(f"- [{source.get('title', '')}]({source.get('url', '')})")
            
        if task.pending_items:
            lines.extend(["", "## 待确认项"])
            for item in task.pending_items:
                lines.append(f"- {item}")
                
        lines.extend(["", "## 步骤详情"])
        for step in task.steps:
            lines.extend([
                f"### 步骤 {step.index + 1}: {step.name}",
                f"- 状态: {step.status.value}",
                f"- 工具: {step.tool_name}",
            ])
            if step.error:
                lines.append(f"- 错误: {step.error}")
            if step.started_at:
                lines.append(f"- 开始: {step.started_at.isoformat()}")
            if step.completed_at:
                lines.append(f"- 结束: {step.completed_at.isoformat()}")
            lines.append("")
            
        content = "\n".join(lines)
        path.write_text(content, encoding="utf-8")
        return str(path)
        
    def export_json(self, task, path: Optional[str] = None) -> str:
        """导出为 JSON"""
        if not path:
            path = self.base_dir / f"task_{task.id[:8]}.json"
        else:
            path = Path(path)
            
        data = {
            "id": task.id,
            "goal": task.goal,
            "status": task.status.value,
            "conclusion": task.conclusion,
            "sources": task.sources,
            "pending_items": task.pending_items,
            "created_at": task.created_at.isoformat(),
            "steps": [
                {
                    "index": s.index,
                    "name": s.name,
                    "status": s.status.value,
                    "tool_name": s.tool_name,
                    "error": s.error,
                }
                for s in task.steps
            ]
        }
        
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)
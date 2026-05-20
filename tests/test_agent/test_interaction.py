"""
Test Interaction - 交互控制模块测试。

覆盖：ConfirmRequest, ConsoleConfirmCallback, InterruptHandler, RetryManager, ResultExporter。
不依赖 Qt。
"""
import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from src.modules.agent.interaction import (
    ConfirmLevel, ConfirmRequest, ConfirmCallback, ConsoleConfirmCallback,
    InterruptHandler, RetryPolicy, RetryConfig, RetryManager, ResultExporter,
)
from src.modules.agent.task_manager import Task, TaskStatus, StepStatus, Step


class TestConfirmRequest(unittest.TestCase):
    """测试 ConfirmRequest"""

    def test_default_fields(self):
        req = ConfirmRequest()
        self.assertIsNotNone(req.id)
        self.assertEqual(req.step_id, "")
        self.assertEqual(req.message, "")
        self.assertEqual(req.level, ConfirmLevel.MEDIUM)
        self.assertIsNone(req.confirmed)
        self.assertIsNone(req.confirmed_at)

    def test_custom_fields(self):
        req = ConfirmRequest(
            step_id="step-1",
            message="确认执行？",
            level=ConfirmLevel.HIGH,
        )
        self.assertEqual(req.step_id, "step-1")
        self.assertEqual(req.message, "确认执行？")
        self.assertEqual(req.level, ConfirmLevel.HIGH)

    def test_is_expired_false(self):
        req = ConfirmRequest()
        self.assertFalse(req.is_expired(timeout_seconds=300))

    def test_is_expired_true(self):
        req = ConfirmRequest()
        # 手动将时间设为过去
        req.timestamp = datetime.now() - timedelta(seconds=301)
        self.assertTrue(req.is_expired(timeout_seconds=300))

    def test_is_expired_custom_timeout(self):
        req = ConfirmRequest()
        req.timestamp = datetime.now() - timedelta(seconds=10)
        self.assertTrue(req.is_expired(timeout_seconds=5))
        self.assertFalse(req.is_expired(timeout_seconds=15))


class TestConfirmCallback(unittest.TestCase):
    """测试 ConfirmCallback 抽象类"""

    def test_cannot_instantiate_abstract(self):
        """不能直接实例化抽象类"""
        with self.assertRaises(TypeError):
            ConfirmCallback()

    def test_should_auto_confirm_low(self):
        """LOW 级别应自动确认"""
        self.assertTrue(ConfirmCallback.should_auto_confirm(None, ConfirmLevel.LOW))

    def test_should_auto_confirm_medium(self):
        """MEDIUM 级别不应自动确认"""
        self.assertFalse(ConfirmCallback.should_auto_confirm(None, ConfirmLevel.MEDIUM))


class TestConsoleConfirmCallback(unittest.TestCase):
    """测试 ConsoleConfirmCallback"""

    def test_auto_approve_true(self):
        cb = ConsoleConfirmCallback(auto_approve=True)
        req = ConfirmRequest(level=ConfirmLevel.HIGH)
        # auto_approve=True 不需要输入
        self.assertTrue(cb.request_confirm(req))

    def test_low_level_auto_confirms(self):
        cb = ConsoleConfirmCallback(auto_approve=False)
        req = ConfirmRequest(level=ConfirmLevel.LOW)
        # LOW 级别即使 auto_approve=False 也自动确认
        self.assertTrue(cb.request_confirm(req))


class TestInterruptHandler(unittest.TestCase):
    """测试 InterruptHandler"""

    def test_initial_state(self):
        handler = InterruptHandler()
        self.assertFalse(handler.is_interrupted())

    def test_interrupt(self):
        handler = InterruptHandler()
        handler.interrupt()
        self.assertTrue(handler.is_interrupted())

    def test_reset(self):
        handler = InterruptHandler()
        handler.interrupt()
        handler.reset()
        self.assertFalse(handler.is_interrupted())

    def test_callback_on_interrupt(self):
        handler = InterruptHandler()
        called = []
        handler.register_callback(lambda: called.append(True))
        handler.interrupt()
        self.assertEqual(len(called), 1)

    def test_multiple_callbacks(self):
        handler = InterruptHandler()
        calls = []
        handler.register_callback(lambda: calls.append("a"))
        handler.register_callback(lambda: calls.append("b"))
        handler.interrupt()
        self.assertEqual(calls, ["a", "b"])

    def test_callback_exception_ignored(self):
        """回调抛异常不应中断 interrupt 流程"""
        handler = InterruptHandler()
        handler.register_callback(lambda: 1/0)
        handler.register_callback(lambda: None)  # noqa
        # 不应抛异常
        handler.interrupt()
        self.assertTrue(handler.is_interrupted())


class TestRetryManager(unittest.TestCase):
    """测试 RetryManager"""

    def test_initial_should_retry(self):
        manager = RetryManager()
        self.assertTrue(manager.should_retry("task-1"))

    def test_max_attempts(self):
        config = RetryConfig(max_attempts=2)
        manager = RetryManager(config)
        # recordAttempt 记录第1次尝试，current=1, 1 < 2 = True (仍可重试)
        manager.recordAttempt("task-1")
        self.assertTrue(manager.should_retry("task-1"))
        # recordAttempt 记录第2次，current=2, 2 < 2 = False (达到上限)
        manager.recordAttempt("task-1")
        self.assertFalse(manager.should_retry("task-1"))

    def test_record_attempt(self):
        manager = RetryManager()
        count = manager.recordAttempt("task-1")
        self.assertEqual(count, 1)
        count = manager.recordAttempt("task-1")
        self.assertEqual(count, 2)

    def test_separate_keys(self):
        manager = RetryManager()
        manager.recordAttempt("task-1", "step-1")
        manager.recordAttempt("task-1", "step-1")
        # step-2 应从 0 开始
        self.assertTrue(manager.should_retry("task-1", "step-2"))

    def test_reset_single_task(self):
        manager = RetryManager()
        manager.recordAttempt("task-1")
        manager.recordAttempt("task-2")
        manager.reset("task-1")
        self.assertTrue(manager.should_retry("task-1"))
        # task-2 有1次尝试记录，1 < 3(默认max)=True，应可重试
        self.assertTrue(manager.should_retry("task-2"))

    def test_reset_all(self):
        manager = RetryManager()
        manager.recordAttempt("task-1")
        manager.recordAttempt("task-2")
        manager.reset()
        self.assertTrue(manager.should_retry("task-1"))
        self.assertTrue(manager.should_retry("task-2"))


class TestRetryDelay(unittest.TestCase):
    """测试重试延迟计算"""

    def test_immediate_policy(self):
        config = RetryConfig(policy=RetryPolicy.IMMEDIATE, initial_delay=1.0, max_delay=60.0)
        manager = RetryManager(config)
        # IMMEDIATE 不修改 delay，始终返回 initial_delay
        manager.recordAttempt("t1")
        self.assertAlmostEqual(manager.get_retry_delay("t1"), 1.0)
        manager.recordAttempt("t1")
        self.assertAlmostEqual(manager.get_retry_delay("t1"), 1.0)

    def test_linear_policy(self):
        config = RetryConfig(policy=RetryPolicy.LINEAR, initial_delay=2.0, max_delay=60.0)
        manager = RetryManager(config)
        # attempt 1: 2.0 * 0 = 0 → clamped to initial_delay
        manager.recordAttempt("t1")
        d1 = manager.get_retry_delay("t1")
        # attempt 2: 2.0 * 1 = 2.0
        manager.recordAttempt("t1")
        d2 = manager.get_retry_delay("t1")
        # attempt 3: 2.0 * 2 = 4.0
        manager.recordAttempt("t1")
        d3 = manager.get_retry_delay("t1")
        self.assertLessEqual(d1, d2)
        self.assertLessEqual(d2, d3)

    def test_exponential_policy(self):
        config = RetryConfig(policy=RetryPolicy.EXPONENTIAL, initial_delay=1.0, max_delay=60.0)
        manager = RetryManager(config)
        delays = []
        for _ in range(5):
            manager.recordAttempt("t1")
            delays.append(manager.get_retry_delay("t1"))
        # 延迟应该递增（指数增长）
        for i in range(1, len(delays)):
            self.assertGreaterEqual(delays[i], delays[i-1])

    def test_fibonacci_policy(self):
        config = RetryConfig(policy=RetryPolicy.FIBONACCI, initial_delay=1.0, max_delay=60.0)
        manager = RetryManager(config)
        delays = []
        for _ in range(6):
            manager.recordAttempt("t1")
            delays.append(manager.get_retry_delay("t1"))
        # 至少应该递增
        for i in range(1, len(delays)):
            self.assertGreaterEqual(delays[i], delays[i-1])

    def test_max_delay_cap(self):
        config = RetryConfig(policy=RetryPolicy.EXPONENTIAL, initial_delay=100.0, max_delay=60.0)
        manager = RetryManager(config)
        for _ in range(5):
            manager.recordAttempt("t1")
            delay = manager.get_retry_delay("t1")
            self.assertLessEqual(delay, 60.0)


class TestResultExporter(unittest.TestCase):
    """测试 ResultExporter"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _make_task(self) -> Task:
        task = Task(goal="测试任务")
        task.status = TaskStatus.COMPLETED
        task.conclusion = "测试结论"
        task.sources = [{"title": "Source 1", "url": "https://example.com"}]
        step1 = Step(index=0, name="搜索", tool_name="web_search")
        step1.status = StepStatus.SUCCESS
        step1.started_at = datetime.now() - timedelta(minutes=5)
        step1.completed_at = datetime.now()
        task.steps.append(step1)
        return task

    def test_export_text(self):
        exporter = ResultExporter(base_dir=self.tmpdir)
        task = self._make_task()
        path = exporter.export_text(task)

        self.assertTrue(os.path.exists(path))
        content = Path(path).read_text(encoding="utf-8")
        self.assertIn("测试任务", content)
        self.assertIn("测试结论", content)
        self.assertIn("Source 1", content)

    def test_export_json(self):
        exporter = ResultExporter(base_dir=self.tmpdir)
        task = self._make_task()
        path = exporter.export_json(task)

        self.assertTrue(os.path.exists(path))
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual(data["goal"], "测试任务")
        self.assertEqual(data["status"], "completed")
        self.assertEqual(len(data["steps"]), 1)

    def test_export_custom_path(self):
        exporter = ResultExporter(base_dir=self.tmpdir)
        task = self._make_task()
        custom_path = os.path.join(self.tmpdir, "custom.txt")
        path = exporter.export_text(task, path=custom_path)
        self.assertEqual(path, custom_path)
        self.assertTrue(os.path.exists(custom_path))

    def test_export_with_pending_items(self):
        exporter = ResultExporter(base_dir=self.tmpdir)
        task = self._make_task()
        task.pending_items = ["待确认项1", "待确认项2"]
        path = exporter.export_text(task)

        content = Path(path).read_text(encoding="utf-8")
        self.assertIn("待确认项", content)
        self.assertIn("待确认项1", content)


if __name__ == "__main__":
    unittest.main()

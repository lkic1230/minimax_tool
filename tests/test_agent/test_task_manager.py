"""
Test Task Manager - 任务管理测试。
"""
import unittest
from datetime import datetime
from src.modules.agent.task_manager import (
    Task, Step, TaskManager, TaskStatus, StepStatus
)


class TestTask(unittest.TestCase):
    """测试 Task"""
    
    def test_create_task(self):
        """测试创建任务"""
        task = Task(goal="测试目标")
        self.assertEqual(task.goal, "测试目标")
        self.assertEqual(task.status, TaskStatus.PENDING)
        
    def test_add_step(self):
        """测试添加步骤"""
        task = Task(goal="测试")
        step = task.add_step("步骤1", "描述", "web_search")
        self.assertEqual(len(task.steps), 1)
        self.assertEqual(step.name, "步骤1")
        
    def test_get_current_step(self):
        """测试获取当前步骤"""
        task = Task(goal="测试")
        task.add_step("步骤1", "描述", "web_search")
        current = task.get_current_step()
        self.assertIsNotNone(current)


class TestStep(unittest.TestCase):
    """测试 Step"""
    
    def test_create_step(self):
        """测试创建步骤"""
        step = Step(index=0, name="测试步骤")
        self.assertEqual(step.index, 0)
        self.assertEqual(step.status, StepStatus.WAITING)
        
    def test_duration(self):
        """测试耗时计算"""
        step = Step(index=0, name="测试")
        step.started_at = datetime.now()
        step.completed_at = datetime.now()
        duration = step.duration()
        self.assertGreaterEqual(duration, 0)


class TestTaskManager(unittest.TestCase):
    """测试 TaskManager"""
    
    def setUp(self):
        self.manager = TaskManager()
        
    def test_create_task(self):
        """测试创建任务"""
        task = self.manager.create_task("测试目标")
        self.assertEqual(task.goal, "测试目标")
        self.assertIn(task.id, self.manager._tasks)
        
    def test_list_tasks(self):
        """测试列出任务"""
        self.manager.create_task("目标1")
        self.manager.create_task("目标2")
        tasks = self.manager.list_tasks()
        self.assertEqual(len(tasks), 2)
        
    def test_start_task(self):
        """测试开始任务"""
        task = self.manager.create_task("测试")
        result = self.manager.start_task(task.id)
        self.assertTrue(result)
        self.assertEqual(task.status, TaskStatus.RUNNING)
        
    def test_complete_step(self):
        """测试完成步骤"""
        task = self.manager.create_task("测试")
        task.add_step("步骤1", "描述", "web_search")
        self.manager.start_task(task.id)
        result = self.manager.complete_step(task.id, {"result": "ok"})
        self.assertTrue(result)
        
    def test_fail_step(self):
        """测试步骤失败"""
        task = self.manager.create_task("测试")
        task.add_step("步骤1", "描述", "web_search")
        self.manager.start_task(task.id)
        self.manager.fail_step(task.id, "错误")
        self.assertEqual(task.steps[0].status, StepStatus.FAILED)
        
    def test_cancel_task(self):
        """测试取消任务"""
        task = self.manager.create_task("测试")
        result = self.manager.cancel_task(task.id)
        self.assertTrue(result)
        self.assertEqual(task.status, TaskStatus.CANCELLED)


if __name__ == "__main__":
    unittest.main()
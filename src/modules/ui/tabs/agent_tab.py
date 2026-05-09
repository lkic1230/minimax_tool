# -*- coding: utf-8 -*-
"""
Agent Tab - Agent 任务管理界面 (P0 MVP)

功能：
- 任务创建
- 任务列表展示
- 步骤进度显示
- 结果展示
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QTextEdit, QListWidget,
    QListWidgetItem, QProgressBar, QGroupBox,
    QSplitter, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.modules.agent.tool_framework import ToolRegistry, ToolExecutor
from src.modules.agent.task_manager import TaskManager, TaskStatus, StepStatus
from src.modules.agent.interaction import ResultExporter
from src.modules.tools.web_search import WebSearchTool
from src.modules.tools.web_scrape import WebScrapeTool
from src.modules.tools.file_ops import FileReadTool, FileWriteTool


class AgentWorker(QThread):
    """Agent 后台工作线程"""
    progress = Signal(str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, task_manager, task_id, parent=None):
        super().__init__(parent)
        self.task_manager = task_manager
        self.task_id = task_id

    def run(self):
        """执行任务"""
        try:
            task = self.task_manager.get_task(self.task_id)
            if not task:
                self.error.emit("任务不存在")
                return

            # 获取当前步骤
            step = task.get_current_step()
            if not step:
                self.finished.emit({})
                return

            self.progress.emit(f"执行步骤: {step.name}")

            # 根据工具执行
            if step.tool_name == "web_search":
                tool = WebSearchTool()
                result = tool.execute(
                    query=step.tool_input.get("query", ""),
                    max_results=step.tool_input.get("max_results", 5)
                )
                self.task_manager.complete_step(
                    self.task_id,
                    {"result": result.data, "success": result.success}
                )
            elif step.tool_name == "web_scrape":
                tool = WebScrapeTool()
                result = tool.execute(url=step.tool_input.get("url", ""))
                self.task_manager.complete_step(
                    self.task_id,
                    {"result": result.data, "success": result.success}
                )
            else:
                self.task_manager.complete_step(self.task_id, {"result": "done"})

            self.finished.emit({})

        except Exception as e:
            self.error.emit(str(e))


class AgentTabWidget(QWidget):
    """Agent 任务管理 Tab"""

    def __init__(self, client_getter=None, check_client_func=None):
        super().__init__()
        self.client_getter = client_getter
        self.check_client_func = check_client_func

        # 初始化 Agent 组件
        self.tool_registry = ToolRegistry()
        self.tool_registry.register(WebSearchTool())
        self.tool_registry.register(WebScrapeTool())
        self.tool_registry.register(FileReadTool())
        self.tool_registry.register(FileWriteTool())
        self.tool_executor = ToolExecutor(self.tool_registry)
        self.task_manager = TaskManager()
        self.result_exporter = ResultExporter()

        self.worker = None
        self.current_task_id = None

        self.setup_ui()

    def setup_ui(self):
        """设置 UI"""
        main_layout = QHBoxLayout(self)

        # 左侧：任务列表
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # 标题
        title = QLabel("🤖 Agent 任务")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        left_layout.addWidget(title)

        # 任务输入
        input_group = QGroupBox("创建任务")
        input_layout = QVBoxLayout(input_group)

        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("输入任务目标...")
        input_layout.addWidget(self.task_input)

        btn_layout = QHBoxLayout()
        self.create_btn = QPushButton("创建任务")
        self.create_btn.clicked.connect(self.create_task)
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_tasks)
        btn_layout.addWidget(self.create_btn)
        btn_layout.addWidget(self.refresh_btn)
        input_layout.addLayout(btn_layout)

        left_layout.addWidget(input_group)

        # 任务列表
        list_label = QLabel("任务列表")
        left_layout.addWidget(list_label)

        self.task_list = QListWidget()
        self.task_list.itemClicked.connect(self.on_task_selected)
        left_layout.addWidget(self.task_list)

        main_layout.addWidget(left_panel, 1)

        # 右侧：详情面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # 任务详情
        detail_group = QGroupBox("任务详情")
        detail_layout = QVBoxLayout(detail_group)

        self.detail_label = QLabel("请选择任务")
        detail_layout.addWidget(self.detail_label)

        # 步骤进度
        progress_label = QLabel("步骤进度")
        detail_layout.addWidget(progress_label)

        self.step_list = QListWidget()
        detail_layout.addWidget(self.step_list)

        # 控制按钮
        control_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始执行")
        self.start_btn.clicked.connect(self.start_task)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self.stop_task)
        self.retry_btn = QPushButton("重试")
        self.retry_btn.clicked.connect(self.retry_step)
        self.export_btn = QPushButton("导出结果")
        self.export_btn.clicked.connect(self.export_result)

        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.retry_btn)
        control_layout.addWidget(self.export_btn)

        detail_layout.addLayout(control_layout)

        # 结果显示
        result_label = QLabel("执行结果")
        detail_layout.addWidget(result_label)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        detail_layout.addWidget(self.result_text)

        right_layout.addWidget(detail_group)

        main_layout.addWidget(right_panel, 2)

    def create_task(self):
        """创建任务"""
        goal = self.task_input.text().strip()
        if not goal:
            return

        # 创建任务
        task = self.task_manager.create_task(goal)

        # 自动添加搜索步骤
        task.add_step("联网搜索", "搜索相关信息", "web_search")
        task.tool_input = {"query": goal, "max_results": 5}

        self.task_input.clear()
        self.refresh_tasks()

    def refresh_tasks(self):
        """刷新任务列表"""
        self.task_list.clear()
        for task in self.task_manager.list_tasks():
            item = QListWidgetItem(f"{task.goal} [{task.status.value}]")
            item.setData(Qt.UserRole, task.id)
            self.task_list.addItem(item)

    def on_task_selected(self, item):
        """选择任务"""
        task_id = item.data(Qt.UserRole)
        task = self.task_manager.get_task(task_id)
        if not task:
            return

        self.current_task_id = task_id

        # 显示详情
        self.detail_label.setText(
            f"目标: {task.goal}\n"
            f"状态: {task.status.value}\n"
            f"步骤数: {len(task.steps)}"
        )

        # 显示步骤
        self.step_list.clear()
        for step in task.steps:
            status_icon = {
                StepStatus.WAITING: "⏳",
                StepStatus.RUNNING: "🔄",
                StepStatus.SUCCESS: "✅",
                StepStatus.FAILED: "❌"
            }.get(step.status, "?")

            text = f"{status_icon} {step.name} - {step.status.value}"
            if step.error:
                text += f"\n   错误: {step.error}"
            self.step_list.addItem(text)

    def start_task(self):
        """开始执行任务"""
        if not self.current_task_id:
            return

        task = self.task_manager.get_task(self.current_task_id)
        if not task:
            return

        self.task_manager.start_task(self.current_task_id)
        self.result_text.setText("任务已开始...")

        # 启动工作线程
        self.worker = AgentWorker(self.task_manager, self.current_task_id)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def stop_task(self):
        """停止任务"""
        if self.current_task_id:
            self.task_manager.cancel_task(self.current_task_id)
            self.result_text.setText("任务已取消")
            self.refresh_tasks()

    def retry_step(self):
        """重试步骤"""
        if self.current_task_id:
            self.task_manager.retry_step(self.current_task_id)
            self.result_text.setText("步骤已重试")
            self.refresh_tasks()

    def export_result(self):
        """导出结果"""
        if not self.current_task_id:
            return

        task = self.task_manager.get_task(self.current_task_id)
        if not task:
            return

        # 收集结果
        task.conclusion = self.result_text.toPlainText()

        try:
            path = self.result_exporter.export_text(task)
            self.result_text.append(f"\n结果已导出到: {path}")
        except Exception as e:
            self.result_text.append(f"\n导出失败: {e}")

    def on_progress(self, msg):
        """进度更新"""
        self.result_text.append(msg)

    def on_finished(self, result):
        """完成"""
        self.result_text.append("步骤完成!")
        self.refresh_tasks()

    def on_error(self, error):
        """错误"""
        self.result_text.append(f"错误: {error}")
        self.refresh_tasks()
# -*- coding: utf-8 -*-
"""
Agent Chat Tab - 对话式 Agent UI

集成到现有 Chat Tab，支持：
- 普通对话模式
- Agent 任务模式（AI 自动执行）
- 实时状态展示
- 步骤进度显示
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QTextEdit, QPushButton, QSplitter, QProgressBar,
    QScrollArea, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

import re
import json

from ..components.common import GenerationThread
from ..components.chat_message_widget import create_message_row
from ..components.chat_history_manager import ChatHistoryManager
from ...core.constants import CHAT_MODEL_DEFAULT


class AgentChatWorker(QThread):
    """Agent 后台工作线程"""
    status_update = Signal(str)
    step_update = Signal(dict)
    result_ready = Signal(str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, agent_engine, user_message, parent=None):
        super().__init__(parent)
        self.agent_engine = agent_engine
        self.user_message = user_message

    def run(self):
        try:
            # 设置回调
            self.agent_engine.on_status_update = lambda s: self.status_update.emit(s)
            self.agent_engine.on_step_update = lambda d: self.step_update.emit(d)
            self.agent_engine.on_result_ready = lambda r: self.result_ready.emit(r)
            
            # 处理消息
            result = self.agent_engine.process_message(
                self.user_message,
                self.agent_engine.conversation_history if hasattr(self.agent_engine, 'conversation_history') else []
            )
            
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(str(e))


class AgentChatTabWidget(QWidget):
    """
    Agent 增强版 Chat Tab
    
    自动识别任务类型：
    - 普通对话：直接回复
    - 任务型：自动执行工具调用循环
    """

    def __init__(self, client_getter=None, check_client_func=None, get_show_thinking_func=None):
        super().__init__()
        self.client_getter = client_getter
        self.check_client_func = check_client_func
        self.get_show_thinking_func = get_show_thinking_func or (lambda: True)
        
        # 初始化 Agent 引擎
        self._init_agent_engine()
        
        # 状态
        self._is_generating = False
        self.worker = None
        self.conversation_history = []
        
        self.setup_ui()

    def _init_agent_engine(self):
        """初始化 Agent 引擎"""
        from ...agent.agent_engine import AgentEngine
        from ...agent.tool_framework import ToolRegistry
        from ...tools.web_search import WebSearchTool
        from ...tools.web_scrape import WebScrapeTool
        from ...tools.file_ops import FileReadTool, FileWriteTool
        
        # 创建工具注册表
        self.tool_registry = ToolRegistry()
        self.tool_registry.register(WebSearchTool())
        self.tool_registry.register(WebScrapeTool())
        self.tool_registry.register(FileReadTool())
        self.tool_registry.register(FileWriteTool())
        
        # 创建 Agent 引擎
        self.agent_engine = AgentEngine(
            client_getter=self.client_getter,
            tool_registry=self.tool_registry
        )

    def setup_ui(self):
        """设置 UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        # ===== 状态栏 =====
        self.status_bar = QLabel("🤖 Agent 就绪 - 输入任务目标开始")
        self.status_bar.setStyleSheet("""
            QLabel {
                background-color: #e3f2fd;
                color: #1565c0;
                padding: 8px;
                border-radius: 4px;
                font-size: 13px;
            }
        """)
        main_layout.addWidget(self.status_bar)
        
        # ===== 进度条 =====
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4caf50;
            }
        """)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # ===== 步骤显示区 =====
        self.steps_group = QGroupBox("执行步骤")
        steps_layout = QVBoxLayout(self.steps_group)
        
        self.steps_area = QScrollArea()
        self.steps_area.setWidgetResizable(True)
        self.steps_area.setMaximumHeight(150)
        self.steps_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #eee;
                background-color: #fafafa;
            }
        """)
        
        self.steps_content = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_content)
        self.steps_layout.setAlignment(Qt.AlignTop)
        self.steps_area.setWidget(self.steps_content)
        steps_layout.addWidget(self.steps_area)
        
        self.steps_group.setVisible(False)
        main_layout.addWidget(self.steps_group)
        
        # ===== 消息区 =====
        self.message_scroll = QScrollArea()
        self.message_scroll.setWidgetResizable(True)
        self.message_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.message_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f5f5f5;
            }
        """)
        
        self.message_list_widget = QWidget()
        self.message_list_widget.setStyleSheet("background-color: #f5f5f5;")
        self.message_list_layout = QVBoxLayout(self.message_list_widget)
        self.message_list_layout.setContentsMargins(4, 8, 4, 8)
        self.message_list_layout.setSpacing(8)
        self.message_list_layout.addStretch()
        
        self.message_scroll.setWidget(self.message_list_widget)
        main_layout.addWidget(self.message_scroll, 1)
        
        # ===== 输入区 =====
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 4, 0, 0)
        
        # 模式提示
        self.mode_hint = QLabel("💡 尝试输入如「调研Python最新动态」体验 Agent 模式")
        self.mode_hint.setStyleSheet("color: #666; font-size: 12px; padding: 4px;")
        input_layout.addWidget(self.mode_hint)
        
        self.chat_input = QTextEdit()
        self.chat_input.setPlaceholderText("输入消息或任务目标...")
        self.chat_input.setMinimumHeight(60)
        self.chat_input.setMaximumHeight(120)
        self.chat_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
            }
        """)
        input_layout.addWidget(self.chat_input)
        
        # 按钮行
        btn_layout = QHBoxLayout()
        
        self.stop_btn = QPushButton("⏹️ 停止")
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._stop_task)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #d32f2f; }
        """)
        btn_layout.addWidget(self.stop_btn)
        
        btn_layout.addStretch()
        
        self.chat_send_btn = QPushButton("🚀 发送")
        self.chat_send_btn.setFixedWidth(100)
        self.chat_send_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:disabled { background-color: #a5d6a7; }
            QPushButton:hover { background-color: #43a047; }
        """)
        self.chat_send_btn.clicked.connect(self._send_message)
        btn_layout.addWidget(self.chat_send_btn)
        
        input_layout.addLayout(btn_layout)
        main_layout.addWidget(input_widget)

    def _send_message(self):
        """发送消息"""
        if not self.check_client_func():
            return
        if self._is_generating:
            return
            
        user_text = self.chat_input.toPlainText().strip()
        if not user_text:
            return
        
        self._set_generating(True)
        
        # 添加用户消息
        self._add_message("user", user_text)
        self.conversation_history.append({"role": "user", "content": user_text})
        
        self.chat_input.clear()
        
        # 检查是否使用 Agent 模式
        if self._should_use_agent(user_text):
            self._run_agent_mode(user_text)
        else:
            self._run_chat_mode(user_text)

    def _should_use_agent(self, message: str) -> bool:
        """判断是否使用 Agent 模式"""
        agent_keywords = [
            "调研", "研究", "查找", "搜索", "收集", "整理",
            "获取", "查询", "分析", "整理", "报告",
            "帮我", "给我", "能否", "可以帮我",
        ]
        for keyword in agent_keywords:
            if keyword in message:
                return True
        return False

    def _run_chat_mode(self, user_text: str):
        """普通对话模式"""
        self.status_bar.setText("💬 对话中...")
        
        def do_chat():
            client = self.client_getter()
            return client.chat_completions(
                messages=self.conversation_history,
                model=CHAT_MODEL_DEFAULT,
                stream=False,
                max_completion_tokens=4096,
                temperature=0.7
            )
        
        self.worker = GenerationThread(do_chat)
        self.worker.finished.connect(self._on_chat_finished)
        self.worker.error.connect(self._on_chat_error)
        self.worker.start()

    def _run_agent_mode(self, user_text: str):
        """Agent 任务模式"""
        self.status_bar.setText("🤖 分析任务中...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(10)
        self.steps_group.setVisible(True)
        self.stop_btn.setVisible(True)
        
        # 清除之前的步骤
        while self.steps_layout.count():
            item = self.steps_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.worker = AgentChatWorker(self.agent_engine, user_text)
        self.worker.status_update.connect(self._on_status_update)
        self.worker.step_update.connect(self._on_step_update)
        self.worker.result_ready.connect(self._on_result_ready)
        self.worker.finished.connect(self._on_agent_finished)
        self.worker.error.connect(self._on_agent_error)
        self.worker.start()

    def _on_status_update(self, status: str):
        """状态更新"""
        self.status_bar.setText(status)
        
        # 更新进度
        current = self.progress_bar.value()
        if current < 90:
            self.progress_bar.setValue(current + 10)

    def _on_step_update(self, step_data: dict):
        """步骤更新"""
        step_type = step_data.get("type", "")
        
        if step_type == "plan":
            # 显示计划
            steps = step_data.get("steps", [])
            for i, step in enumerate(steps):
                label = QLabel(f"📋 步骤 {i+1}: {step.get('action', '执行')}")
                label.setStyleSheet("color: #1565c0; padding: 4px;")
                self.steps_layout.addWidget(label)
                
        elif step_type == "step_start":
            # 执行中
            step = step_data.get("step", 0)
            info = step_data.get("info", {})
            label = QLabel(f"⚙️ 执行中: {info.get('action', '处理中')}")
            label.setStyleSheet("color: #ff9800; padding: 4px;")
            self.steps_layout.addWidget(label)
            
        elif step_type == "step_complete":
            # 完成
            step = step_data.get("step", 0)
            label = QLabel(f"✅ 步骤 {step+1} 完成")
            label.setStyleSheet("color: #4caf50; padding: 4px;")
            self.steps_layout.addWidget(label)
            
        elif step_type == "step_error":
            # 错误
            step = step_data.get("step", 0)
            error = step_data.get("error", "")
            label = QLabel(f"❌ 步骤 {step+1} 失败: {error}")
            label.setStyleSheet("color: #f44336; padding: 4px;")
            self.steps_layout.addWidget(label)

    def _on_result_ready(self, result: str):
        """结果就绪"""
        pass  # 已在 finished 中处理

    def _on_agent_finished(self, result: str):
        """Agent 任务完成"""
        self._set_generating(False)
        self.progress_bar.setValue(100)
        self.status_bar.setText("✅ 任务完成")
        
        # 添加 AI 回复
        self._add_message("assistant", result)
        self.conversation_history.append({"role": "assistant", "content": result})
        
        # 延迟隐藏进度条
        QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))

    def _on_agent_error(self, error: str):
        """Agent 错误"""
        self._set_generating(False)
        self.progress_bar.setVisible(False)
        self.stop_btn.setVisible(False)
        self.status_bar.setText(f"❌ 错误: {error}")
        QMessageBox.critical(self, "错误", f"执行失败: {error}")

    def _on_chat_finished(self, result):
        """普通对话完成"""
        self._set_generating(False)
        
        choices = result.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            if not self.get_show_thinking_func():
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
            self._add_message("assistant", content)
            self.conversation_history.append({"role": "assistant", "content": content})
            self.status_bar.setText("✅ 对话完成")

    def _on_chat_error(self, error: str):
        """对话错误"""
        self._set_generating(False)
        self.status_bar.setText("❌ 对话失败")
        QMessageBox.critical(self, "错误", f"对话失败: {error}")

    def _set_generating(self, is_generating: bool):
        """设置生成状态"""
        self._is_generating = is_generating
        self.chat_send_btn.setEnabled(not is_generating)
        self.chat_input.setEnabled(not is_generating)

    def _stop_task(self):
        """停止任务"""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
        self._set_generating(False)
        self.progress_bar.setVisible(False)
        self.stop_btn.setVisible(False)
        self.status_bar.setText("⏹️ 已停止")

    def _add_message(self, role: str, content: str):
        """添加消息"""
        row = create_message_row(role, content, self.message_list_widget.width() - 40)
        self.message_list_layout.insertWidget(self.message_list_layout.count() - 1, row)
        
        # 滚动到底部
        self.message_scroll.verticalScrollBar().setValue(
            self.message_scroll.verticalScrollBar().maximum()
        )
# -*- coding: utf-8 -*-
"""
Agent 增强版 Chat Tab - 带模式切换

流程说明：
- 💬 对话模式：直接调用父类 ChatTabWidget.send_chat_message()，走原有 LLM 对话
- 🔍 Agent 模式：通过 AgentEngine 完整流程执行
    1. LLM 分析用户意图（是否需要搜索/调研等）
    2. LLM 生成任务执行计划（选择工具、参数）
    3. 执行工具（WebSearch 等）
    4. LLM 基于工具结果生成结构化报告
"""
import json
from PySide6.QtWidgets import QComboBox, QLabel
from PySide6.QtCore import QThread, Signal
from .chat_tab import ChatTabWidget
from ...agent.agent_engine import AgentEngine
from ...agent.tool_framework import ToolRegistry


class AgentChatWorker(QThread):
    """Agent 后台执行线程，通过 AgentEngine 走完整 LLM 流程"""

    status_update = Signal(str)   # 状态文字，用于更新 chat_status
    result_ready = Signal(dict)   # AgentEngine.process_message() 返回的结构化结果
    error = Signal(str)           # 错误信息

    def __init__(self, agent_engine, user_message, conversation_history, parent=None):
        super().__init__(parent)
        self.agent_engine = agent_engine
        self.user_message = user_message
        self.conversation_history = conversation_history

    def run(self):
        try:
            # 将引擎状态回调桥接到线程信号
            self.agent_engine.on_status_update = lambda s: self.status_update.emit(s)

            result = self.agent_engine.process_message(
                self.user_message,
                self.conversation_history,
            )
            self.result_ready.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class AgentChatTabWidget(ChatTabWidget):
    """
    Agent 增强版 Chat Tab - 带模式切换

    用户可以选择：
    - 💬 普通对话模式（走原有 LLM 直接对话）
    - 🔍 Agent 模式（走 AgentEngine：意图分析 → 任务规划 → 工具执行 → LLM 报告）
    """

    def __init__(self, client_getter=None, check_client_func=None, get_show_thinking_func=None):
        super().__init__(client_getter, check_client_func, get_show_thinking_func)
        # 构建 Agent 引擎
        self._init_agent_engine(client_getter)
        # 向工具栏注入模式开关
        self._add_mode_to_toolbar()
        # 当前 Agent Worker 引用（防止重入）
        self._agent_worker = None

    # ==================== Agent 引擎初始化 ====================

    def _init_agent_engine(self, client_getter):
        """初始化 AgentEngine + 注册工具"""
        registry = ToolRegistry()

        # 注册可用工具
        from ...tools.web_search import WebSearchTool
        registry.register(WebSearchTool())

        self._agent_engine = AgentEngine(
            client_getter=client_getter,
            tool_registry=registry,
        )

    # ==================== 工具栏模式开关 ====================

    def _add_mode_to_toolbar(self):
        """在顶部工具栏右侧（保存按钮前）插入模式切换下拉框。"""
        toolbar_widget = self.save_btn.parentWidget()
        if toolbar_widget is None:
            return
        toolbar_layout = toolbar_widget.layout()
        if toolbar_layout is None:
            return

        mode_label = QLabel("  模式:")
        mode_label.setStyleSheet("color: #666; font-size: 12px;")

        self.chat_mode = QComboBox()
        self.chat_mode.addItems(["💬 对话", "🔍 Agent"])
        self.chat_mode.setFixedWidth(120)
        self.chat_mode.setStyleSheet("""
            QComboBox {
                padding: 4px 8px;
                border: 1px solid #bbb;
                border-radius: 4px;
                background-color: white;
                color: #333;
                font-size: 12px;
            }
            QComboBox:hover { border-color: #888; }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #333;
                border: 1px solid #ccc;
                selection-background-color: #e3f2fd;
                selection-color: #1565c0;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                height: 28px;
                padding: 2px 8px;
                color: #333;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #e3f2fd;
                color: #1565c0;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #bbdefb;
                color: #0d47a1;
            }
        """)

        for i in range(toolbar_layout.count()):
            item = toolbar_layout.itemAt(i)
            if item.widget() is self.save_btn:
                toolbar_layout.insertWidget(i, mode_label)
                toolbar_layout.insertWidget(i + 1, self.chat_mode)
                return

    # ==================== 发送逻辑 ====================

    def send_chat_message(self):
        """根据模式选择处理方式"""
        if not self.check_client_func():
            return
        if self._is_generating:
            return

        user_text = self.chat_input.toPlainText().strip()
        if not user_text:
            return

        mode = self.chat_mode.currentText() if hasattr(self, "chat_mode") else "💬 对话"

        if "Agent" in mode:
            self._run_agent_mode(user_text)
        else:
            super().send_chat_message()

    # ==================== Agent 模式 ====================

    def _run_agent_mode(self, user_text: str):
        """启动 Agent 后台线程"""
        self._set_generating_state(True)
        self.chat_status.setText("🤔 分析意图中...")

        # 先渲染用户消息气泡
        self.chat_input.clear()
        user_msg = {"role": "user", "content": user_text}
        self.chat_messages.append(user_msg)
        self._mark_conversation_dirty()
        self._append_message("user", user_text)

        # 启动后台线程
        self._agent_worker = AgentChatWorker(
            agent_engine=self._agent_engine,
            user_message=user_text,
            conversation_history=self.chat_messages[:-1],  # 不含刚追加的当前消息
            parent=self,
        )
        self._agent_worker.status_update.connect(self._on_agent_status)
        self._agent_worker.result_ready.connect(self._on_agent_result)
        self._agent_worker.error.connect(self._on_agent_error)
        self._agent_worker.start()

    def _on_agent_status(self, status: str):
        """Agent 执行过程中的状态更新"""
        self.chat_status.setText(status)

    def _on_agent_result(self, result: dict):
        """Agent 执行完成，处理结果"""
        self._set_generating_state(False)

        result_type = result.get("type", "chat")

        if result_type == "agent":
            # Agent 模式：展示任务计划或执行结果
            content = result.get("content", "")
            task_plan = result.get("task_plan", {})
            confirmation = result.get("confirmation", "")

            if not content and task_plan:
                # 有计划但还没执行（需要用户确认的场景）
                goal = task_plan.get("goal", "")
                steps = task_plan.get("steps", [])
                parts = [f"**🎯 任务目标**: {goal}\n"]
                for i, step in enumerate(steps, 1):
                    action = step.get("action", "执行步骤")
                    tool = step.get("tool", "")
                    parts.append(f"{i}. {action}（工具: {tool}）")
                if confirmation:
                    parts.append(f"\n💬 {confirmation}")
                content = "\n".join(parts)

            if not content:
                content = "Agent 执行完成，但未返回有效内容。"

            self.chat_messages.append({"role": "assistant", "content": content})
            self._mark_conversation_dirty()
            self._append_message("assistant", content)
            self.chat_status.setText("✅ Agent 完成")

        else:
            # 降级为普通对话：LLM 认为不需要 Agent，返回了直接回复
            content = result.get("response", "")
            if not content:
                content = "（意图分析判定为普通对话，但未生成回复内容）"

            self.chat_messages.append({"role": "assistant", "content": content})
            self._mark_conversation_dirty()
            self._append_message("assistant", content)
            self.chat_status.setText("✅ 对话完成")

        self._agent_worker = None

    def _on_agent_error(self, error_msg: str):
        """Agent 执行出错"""
        self._set_generating_state(False)
        self._agent_worker = None

        error_content = f"Agent 执行出错: {error_msg}"
        self.chat_messages.append({"role": "assistant", "content": error_content})
        self._append_message("assistant", error_content)
        self.chat_status.setText("❌ Agent 出错")

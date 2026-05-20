# -*- coding: utf-8 -*-
"""
Agent 增强版 Chat Tab - 带模式切换

流程说明：
- 💬 对话模式：直接调用父类 ChatTabWidget.send_chat_message()，走原有 LLM 对话
- 🔍 Agent 模式：通过 AgentEngine 完整流程执行
    1. LLM 分析用户意图（是否需要搜索/调研等）
    2. LLM 生成任务执行计划（选择工具、参数）→ 展示计划卡片 → 用户确认
    3. 执行工具（WebSearch 等）→ 步骤面板实时高亮
    4. LLM 基于工具结果生成结构化报告 + 来源引用卡片
"""
import json
from PySide6.QtWidgets import (
    QComboBox, QLabel, QPushButton, QWidget,
    QVBoxLayout, QHBoxLayout, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from .chat_tab import ChatTabWidget
from ...agent.agent_engine import AgentEngine
from ...agent.tool_framework import ToolRegistry


class AgentChatWorker(QThread):
    """Agent 后台执行线程，通过 AgentEngine 走完整 LLM 流程"""

    status_update = Signal(str)       # 状态文字
    step_update = Signal(dict)        # 步骤事件（开始/完成）
    result_ready = Signal(dict)       # 最终结果
    error = Signal(str)               # 错误信息

    def __init__(self, agent_engine, user_message, conversation_history, parent=None):
        super().__init__(parent)
        self.agent_engine = agent_engine
        self.user_message = user_message
        self.conversation_history = conversation_history

    def run(self):
        try:
            # 将引擎状态回调桥接到线程信号
            self.agent_engine.on_status_update = lambda s: self.status_update.emit(s)
            self.agent_engine.on_step_update = lambda d: self.step_update.emit(d)

            result = self.agent_engine.process_message(
                self.user_message,
                self.conversation_history,
            )
            self.result_ready.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ==================== 步骤列表组件 ====================

_STEP_PANEL_STYLE = """
    QWidget#stepPanel {
        background-color: #fafafa;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
    }
    QLabel#stepItem {
        padding: 3px 0;
        font-size: 12px;
    }
    QLabel#stepItemActive {
        padding: 3px 0;
        font-size: 12px;
        color: #1565c0;
        font-weight: bold;
    }
    QLabel#stepItemDone {
        padding: 3px 0;
        font-size: 12px;
        color: #2e7d32;
    }
    QLabel#stepItemError {
        padding: 3px 0;
        font-size: 12px;
        color: #c62828;
    }
"""

_STEP_HEADER_STYLE = """
    QLabel {
        color: #666;
        font-size: 11px;
        padding: 4px 10px 2px;
        background-color: transparent;
    }
"""


class StepListWidget(QWidget):
    """步骤列表面板，显示在对话区域内，实时高亮当前步骤。"""

    def __init__(self, steps: list, parent=None):
        super().__init__(parent)
        self.setObjectName("stepPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(_STEP_PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 6)
        layout.setSpacing(1)

        # 标题
        header = QLabel("📋 执行计划")
        header.setObjectName("stepPanel")
        header.setStyleSheet("color: #888; font-size: 11px; font-weight: bold; border: none;")
        layout.addWidget(header)

        # 步骤标签列表
        self._step_labels = []
        for i, step in enumerate(steps, 1):
            action = step.get("action", f"步骤{i}")
            tool = step.get("tool", "")
            text = f"  {i}. {action}"
            if tool:
                text += f"  ({tool})"
            label = QLabel(text)
            label.setObjectName("stepItem")
            layout.addWidget(label)
            self._step_labels.append(label)

    def mark_step_active(self, step_index: int):
        """标记当前执行中的步骤"""
        for i, label in enumerate(self._step_labels):
            if i == step_index:
                label.setText(label.text().replace("  ○", "").replace("  ✓", "").replace("  ✗", "") + "  ○")
                label.setObjectName("stepItemActive")
                label.setStyleSheet(
                    "padding: 3px 0; font-size: 12px; color: #1565c0; font-weight: bold;"
                )
            else:
                label.setText(label.text().replace("  ○", ""))

    def mark_step_done(self, step_index: int, success: bool, elapsed: float = 0):
        """标记步骤完成"""
        label = self._step_labels[step_index]
        elapsed_str = f"  ({elapsed}s)" if elapsed > 0 else ""
        mark = "  ✓" if success else "  ✗"
        label.setText(label.text().replace("  ○", "") + mark + elapsed_str)
        label.setObjectName("stepItemDone" if success else "stepItemError")
        label.setStyleSheet(
            f"padding: 3px 0; font-size: 12px; color: {'#2e7d32' if success else '#c62828'};"
        )

    def mark_stopped(self, step_index: int):
        """标记被停止的步骤"""
        for i, label in enumerate(self._step_labels):
            if i > step_index and "✓" not in label.text() and "✗" not in label.text():
                label.setText(label.text().replace("  ○", "") + "  —")
                label.setObjectName("stepItemError")
                label.setStyleSheet("padding: 3px 0; font-size: 12px; color: #999;")


# ==================== 任务确认卡片 ====================

_CONFIRM_CARD_STYLE = """
    QWidget#confirmCard {
        background-color: #fffde7;
        border: 1px solid #ffe082;
        border-radius: 8px;
    }
"""

_CONFIRM_BTN_EXECUTE_STYLE = """
    QPushButton {
        background-color: #4caf50;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 5px 16px;
        font-size: 12px;
    }
    QPushButton:hover { background-color: #43a047; }
"""

_CONFIRM_BTN_CANCEL_STYLE = """
    QPushButton {
        background-color: #fafafa;
        color: #666;
        border: 1px solid #ccc;
        border-radius: 4px;
        padding: 5px 16px;
        font-size: 12px;
    }
    QPushButton:hover { background-color: #f0f0f0; }
"""


class ConfirmCardWidget(QWidget):
    """任务确认卡片，展示任务计划并等待用户确认。"""

    confirmed = Signal()   # 用户确认执行
    cancelled = Signal()   # 用户取消

    def __init__(self, goal: str, steps: list, confirmation: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("confirmCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(_CONFIRM_CARD_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # 标题
        title = QLabel("🎯 任务计划")
        title.setStyleSheet("color: #f57f17; font-size: 13px; font-weight: bold; border: none;")
        layout.addWidget(title)

        # 目标
        goal_label = QLabel(f"目标: {goal}")
        goal_label.setWordWrap(True)
        goal_label.setStyleSheet("color: #333; font-size: 12px; border: none;")
        layout.addWidget(goal_label)

        # 步骤列表
        for i, step in enumerate(steps, 1):
            action = step.get("action", f"步骤{i}")
            tool = step.get("tool", "")
            params = step.get("params", {})
            detail = ""
            if tool in ("web_search", "搜索"):
                detail = params.get("query", "")
            elif tool in ("web_scrape", "抓取"):
                detail = params.get("url", "")
            text = f"  {i}. {action}"
            if tool:
                text += f"  [{tool}]"
            if detail:
                text += f"\n     {detail[:80]}"
            step_label = QLabel(text)
            step_label.setStyleSheet("color: #555; font-size: 11px; border: none;")
            step_label.setWordWrap(True)
            layout.addWidget(step_label)

        # 确认提示
        if confirmation:
            hint = QLabel(confirmation)
            hint.setWordWrap(True)
            hint.setStyleSheet("color: #888; font-size: 11px; border: none;")
            layout.addWidget(hint)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 4, 0, 0)

        self._execute_btn = QPushButton("✅ 确认执行")
        self._execute_btn.setStyleSheet(_CONFIRM_BTN_EXECUTE_STYLE)
        self._execute_btn.clicked.connect(self.confirmed.emit)
        btn_row.addWidget(self._execute_btn)

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setStyleSheet(_CONFIRM_BTN_CANCEL_STYLE)
        self._cancel_btn.clicked.connect(self.cancelled.emit)
        btn_row.addWidget(self._cancel_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    def set_enabled(self, enabled: bool):
        """启用/禁用按钮"""
        self._execute_btn.setEnabled(enabled)
        self._cancel_btn.setEnabled(enabled)


# ==================== 来源引用卡片 ====================

_SOURCE_CARD_STYLE = """
    QWidget#sourceCard {
        background-color: #f5f5f5;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
    }
"""


class SourceCardWidget(QWidget):
    """来源引用卡片，展示搜索结果来源列表。"""

    def __init__(self, sources: list, parent=None):
        super().__init__(parent)
        self.setObjectName("sourceCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(_SOURCE_CARD_STYLE)

        if not sources:
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(3)

        header = QLabel("📎 信息来源")
        header.setStyleSheet("color: #888; font-size: 11px; font-weight: bold; border: none;")
        layout.addWidget(header)

        # 显示全部来源，不限制条数
        for src in sources:
            title = src.get("title", "未知来源")
            url = src.get("url", "")
            snippet = src.get("snippet", "")

            row = QWidget()
            row.setStyleSheet("border: none;")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(4, 2, 4, 2)
            row_layout.setSpacing(1)

            if url:
                title_label = QLabel(f'<a href="{url}" style="color: #1565c0; text-decoration: none; font-size: 12px;">{title}</a>')
            else:
                title_label = QLabel(title)
                title_label.setStyleSheet("font-size: 12px; color: #333;")
            title_label.setOpenExternalLinks(True)
            title_label.setTextFormat(Qt.RichText)
            row_layout.addWidget(title_label)

            if snippet:
                # 显示完整 snippet，最多 500 字符，超出部分省略
                display_snippet = snippet if len(snippet) <= 500 else snippet[:500] + "…"
                snippet_label = QLabel(display_snippet)
                snippet_label.setWordWrap(True)
                snippet_label.setStyleSheet("color: #888; font-size: 11px; border: none;")
                row_layout.addWidget(snippet_label)

            layout.addWidget(row)

        # 底部提示：当来源超过一定数量时可选择性添加分隔线
        if len(sources) > 20:
            sep = QLabel("─" * 20)
            sep.setStyleSheet("color: #ddd; font-size: 10px; border: none;")
            layout.addWidget(sep, 0, Qt.AlignCenter)


class AgentChatTabWidget(ChatTabWidget):
    """
    Agent 增强版 Chat Tab - 带模式切换

    用户可以选择：
    - 💬 普通对话模式（走原有 LLM 直接对话）
    - 🔍 Agent 模式（走 AgentEngine：意图分析 → 任务规划 → 工具执行 → LLM 报告）

    Agent 状态会以气泡形式实时显示在对话区域内。
    """

    def __init__(self, client_getter=None, check_client_func=None, get_show_thinking_func=None):
        super().__init__(client_getter, check_client_func, get_show_thinking_func)
        # 构建 Agent 引擎
        self._init_agent_engine(client_getter)
        # 向工具栏注入模式开关 + 停止按钮
        self._add_mode_to_toolbar()
        # 当前 Agent Worker 引用（防止重入）
        self._agent_worker = None
        # 当前对话区域内的状态气泡引用（用于实时更新）
        self._current_status_row = None
        # 当前步骤面板引用
        self._current_step_panel = None
        # 待确认的任务计划（用户确认后执行）
        self._pending_task = None

    # ==================== Agent 引擎初始化 ====================

    def _init_agent_engine(self, client_getter):
        """初始化 AgentEngine + 注册工具"""
        registry = ToolRegistry()

        # 注册可用工具：搜索、抓取、文件操作
        from ...tools.web_search import WebSearchTool
        from ...tools.web_scrape import WebScrapeTool
        from ...tools.file_ops import FileReadTool, FileWriteTool
        registry.register(WebSearchTool())
        registry.register(WebScrapeTool())
        registry.register(FileReadTool())
        registry.register(FileWriteTool())

        # 添加工具别名（兼容不同命名方式）
        registry.add_alias("搜索", "web_search")
        registry.add_alias("抓取", "web_scrape")
        registry.add_alias("读取文件", "file_read")
        registry.add_alias("写入文件", "file_write")

        self._agent_engine = AgentEngine(
            client_getter=client_getter,
            tool_registry=registry,
        )

    # ==================== 工具栏模式开关 + 停止按钮 ====================

    def _add_mode_to_toolbar(self):
        """在顶部工具栏右侧（保存按钮前）插入模式切换下拉框和停止按钮。"""
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

        # 停止按钮（默认隐藏）
        self._stop_btn = QPushButton("⏹ 停止")
        self._stop_btn.setFixedHeight(30)
        self._stop_btn.setFixedWidth(70)
        self._stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #d32f2f; }
            QPushButton:disabled {
                background-color: #ffcdd2;
                color: #999;
            }
        """)
        self._stop_btn.clicked.connect(self._stop_agent)
        self._stop_btn.setVisible(False)

        for i in range(toolbar_layout.count()):
            item = toolbar_layout.itemAt(i)
            if item.widget() is self.save_btn:
                toolbar_layout.insertWidget(i, self._stop_btn)
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
        self._current_status_row = None
        self._current_step_panel = None
        self.chat_status.setText("Agent 执行中...")

        # 显示停止按钮
        if hasattr(self, "_stop_btn"):
            self._stop_btn.setVisible(True)

        # 先渲染用户消息气泡
        self.chat_input.clear()
        user_msg = {"role": "user", "content": user_text}
        self.chat_messages.append(user_msg)
        self._mark_conversation_dirty()
        self._append_message("user", user_text)

        # 在对话区域插入初始状态气泡
        self._current_status_row = self._append_status_bubble("🤔 分析意图中...")

        # 启动后台线程
        self._agent_worker = AgentChatWorker(
            agent_engine=self._agent_engine,
            user_message=user_text,
            conversation_history=self.chat_messages[:-1],
            parent=self,
        )
        self._agent_worker.status_update.connect(self._on_agent_status)
        self._agent_worker.step_update.connect(self._on_agent_step)
        self._agent_worker.result_ready.connect(self._on_agent_result)
        self._agent_worker.error.connect(self._on_agent_error)
        self._agent_worker.start()

    def _on_agent_status(self, status: str):
        """Agent 执行过程中的状态更新 —— 实时更新对话区域内的状态气泡"""
        # 更新底部状态栏（简要）
        self.chat_status.setText(status)
        # 更新对话区域内的状态气泡（详细）
        if self._current_status_row:
            bubble = self._current_status_row.findChild(QWidget, "statusBubble")
            if bubble:
                bubble.update_text(status)

    def _on_agent_step(self, step_data: dict):
        """步骤事件处理 —— 更新步骤面板"""
        step_type = step_data.get("type", "")
        step_index = step_data.get("step_index", 0)
        total_steps = step_data.get("total_steps", 0)

        if step_type == "step_start":
            # 第一次收到步骤事件时，创建步骤面板
            if self._current_step_panel is None and total_steps > 0:
                # 从引擎获取完整步骤列表创建面板
                steps = self._agent_engine.state.task_steps
                if steps:
                    self._current_step_panel = StepListWidget(steps)
                    # 插入到状态气泡之后
                    count = self.message_list_layout.count()
                    # 找到状态气泡的位置并插入后面
                    for idx in range(count):
                        item = self.message_list_layout.itemAt(idx)
                        if item.widget() is self._current_status_row:
                            self.message_list_layout.insertWidget(idx + 1, self._current_step_panel)
                            break
                    else:
                        self.message_list_layout.insertWidget(count - 1, self._current_step_panel)

            if self._current_step_panel:
                self._current_step_panel.mark_step_active(step_index)

            # 更新进度信息
            progress = f" ({step_index + 1}/{total_steps})"
            action = step_data.get("action", "")
            if self._current_status_row:
                bubble = self._current_status_row.findChild(QWidget, "statusBubble")
                if bubble:
                    bubble.update_text(f"🔄 执行中{progress}: {action}")

        elif step_type == "step_complete":
            if self._current_step_panel:
                self._current_step_panel.mark_step_done(
                    step_index,
                    step_data.get("success", True),
                    step_data.get("elapsed", 0),
                )

    def _on_agent_result(self, result: dict):
        """Agent 执行完成，处理结果"""
        self._set_generating_state(False)
        self._current_status_row = None
        self._current_step_panel = None

        # 隐藏停止按钮
        if hasattr(self, "_stop_btn"):
            self._stop_btn.setVisible(False)

        result_type = result.get("type", "chat")
        sources = result.get("sources", [])
        was_stopped = result.get("stopped", False)

        if result_type == "agent":
            raw_content = result.get("content", "")
            task_plan = result.get("task_plan", {})

            if not raw_content and task_plan:
                # 有计划但还没执行 —— 展示确认卡片
                self._show_confirm_card(task_plan)
                self._agent_worker = None
                return

            if not raw_content:
                raw_content = "Agent 执行完成，但未返回有效内容。"

            # 从 content 中分离 thinking（格式：<think>...</think>）
            thinking, content = self._extract_thinking_content(raw_content)

            # 追加结果气泡 + 思考折叠区
            self.chat_messages.append({"role": "assistant", "content": content})
            self._mark_conversation_dirty()
            self._append_message("assistant", content, thinking=thinking)

            # 追加来源引用卡片
            if sources:
                self._append_source_card(sources)

            status = "⏹️ 已停止" if was_stopped else "✅ Agent 完成"
            self.chat_status.setText(status)

        else:
            raw_content = result.get("response", "")
            if not raw_content:
                raw_content = "（意图分析判定为普通对话，但未生成回复内容）"

            # 从 response 中分离 thinking
            thinking, content = self._extract_thinking_content(raw_content)

            self.chat_messages.append({"role": "assistant", "content": content})
            self._mark_conversation_dirty()
            self._append_message("assistant", content, thinking=thinking)
            self.chat_status.setText("✅ 对话完成")

        self._agent_worker = None

    def _on_agent_error(self, error_msg: str):
        """Agent 执行出错"""
        self._set_generating_state(False)
        self._agent_worker = None
        self._current_status_row = None
        self._current_step_panel = None

        # 隐藏停止按钮
        if hasattr(self, "_stop_btn"):
            self._stop_btn.setVisible(False)

        error_content = f"Agent 执行出错: {error_msg}"
        self.chat_messages.append({"role": "assistant", "content": error_content})
        self._append_message("assistant", error_content)
        self.chat_status.setText("❌ Agent 出错")

    # ==================== 停止按钮 ====================

    def _stop_agent(self):
        """用户点击停止按钮"""
        if self._agent_worker:
            self._agent_engine.stop()
            self._agent_worker = None

        if self._current_step_panel:
            self._current_step_panel.setVisible(False)
            self._current_step_panel = None

    # ==================== 确认卡片 ====================

    def _show_confirm_card(self, task_plan: dict):
        """在对话区域展示任务确认卡片"""
        goal = task_plan.get("goal", "")
        steps = task_plan.get("steps", [])
        confirmation = task_plan.get("confirmation", "")

        card = ConfirmCardWidget(goal, steps, confirmation)
        card.setFixedWidth(self.message_list_widget.width() - 32)

        row = QWidget()
        row.setStyleSheet("background-color: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 2, 8, 2)
        row_layout.addStretch()
        row_layout.addWidget(card)
        row_layout.addStretch()

        count = self.message_list_layout.count()
        self.message_list_layout.insertWidget(count - 1, row)

        # 保存待执行任务
        self._pending_task = task_plan

        # 保存卡片引用以便清理
        self._confirm_card_row = row
        self._confirm_card = card

        card.confirmed.connect(self._on_task_confirmed)
        card.cancelled.connect(self._on_task_cancelled)

        self._set_generating_state(False)
        if hasattr(self, "_stop_btn"):
            self._stop_btn.setVisible(False)
        self.chat_status.setText("⏳ 等待确认...")

        QTimer.singleShot(50, self._scroll_to_bottom)

    def _on_task_confirmed(self):
        """用户确认执行任务"""
        # 清理确认卡片
        if hasattr(self, "_confirm_card_row") and self._confirm_card_row:
            self.message_list_layout.removeWidget(self._confirm_card_row)
            self._confirm_card_row.deleteLater()
            self._confirm_card_row = None
            self._confirm_card = None

        if not self._pending_task:
            return

        task_plan = self._pending_task
        self._pending_task = None
        steps = task_plan.get("steps", [])

        # 直接执行步骤（跳过意图分析，因为已经分析过了）
        self._execute_task_steps(task_plan)

    def _on_task_cancelled(self):
        """用户取消任务"""
        if hasattr(self, "_confirm_card_row") and self._confirm_card_row:
            self.message_list_layout.removeWidget(self._confirm_card_row)
            self._confirm_card_row.deleteLater()
            self._confirm_card_row = None
            self._confirm_card = None

        self._pending_task = None
        self.chat_status.setText("已取消任务")

    def _execute_task_steps(self, task_plan: dict):
        """跳过意图分析，直接执行任务步骤"""
        from PySide6.QtCore import QTimer

        self._set_generating_state(True)
        if hasattr(self, "_stop_btn"):
            self._stop_btn.setVisible(True)

        self._current_status_row = None
        self._current_step_panel = None

        steps = task_plan.get("steps", [])
        goal = task_plan.get("goal", "")

        # 重置引擎状态
        self._agent_engine.state.stopped = False
        self._agent_engine.state.task_steps = steps

        # 插入状态气泡
        self._current_status_row = self._append_status_bubble("🚀 执行任务...")

        # 启动执行线程
        class ExecuteStepsWorker(QThread):
            status_update = Signal(str)
            step_update = Signal(dict)
            result_ready = Signal(dict)
            error = Signal(str)

            def __init__(self, engine, task_plan, user_message, history, parent=None):
                super().__init__(parent)
                self.engine = engine
                self.task_plan = task_plan
                self.user_message = user_message
                self.history = history

            def run(self):
                try:
                    self.engine.on_status_update = lambda s: self.status_update.emit(s)
                    self.engine.on_step_update = lambda d: self.step_update.emit(d)
                    result = self.engine.process_message(self.user_message, self.history)
                    self.result_ready.emit(result)
                except Exception as e:
                    self.error.emit(str(e))

        # 为了复用 process_message 但跳过意图分析，我们构造一个"已确认"的快捷路径
        # 直接调用引擎的执行逻辑
        self._run_direct_execution(task_plan, goal)

    def _run_direct_execution(self, task_plan: dict, goal: str):
        """直接执行已确认的任务步骤（跳过意图分析 LLM 调用）"""
        steps = task_plan.get("steps", [])

        self._set_generating_state(True)
        if hasattr(self, "_stop_btn"):
            self._stop_btn.setVisible(True)

        class DirectExecWorker(QThread):
            status_update = Signal(str)
            step_update = Signal(dict)
            result_ready = Signal(dict)
            error = Signal(str)

            def __init__(self, engine, steps, goal, parent=None):
                super().__init__(parent)
                self.engine = engine
                self.steps = steps
                self.goal = goal

            def run(self):
                try:
                    self.engine.on_status_update = lambda s: self.status_update.emit(s)
                    self.engine.on_step_update = lambda d: self.step_update.emit(d)

                    # 直接执行步骤（跳过意图分析）
                    self.engine.state.mode = AgentEngine.__mro__[0].__bases__[0].__bases__[0] if False else None
                    # 简化：直接调用引擎的内部方法
                    import time
                    self.engine.state.stopped = False
                    self.engine.state.task_steps = self.steps

                    all_results = []
                    total_steps = len(self.steps)
                    collected_sources = []

                    for i, step_info in enumerate(self.steps):
                        if self.engine.state.stopped:
                            self.result_ready.emit({
                                "type": "agent",
                                "content": "任务已被用户停止。",
                                "task_plan": {"goal": self.goal, "steps": self.steps},
                                "stopped": True,
                                "sources": collected_sources,
                            })
                            return

                        tool_name = step_info.get("tool", "")
                        params = step_info.get("params", {})
                        action_desc = step_info.get("action", f"步骤{i+1}")

                        self.step_update.emit({
                            "type": "step_start",
                            "step_index": i,
                            "total_steps": total_steps,
                            "action": action_desc,
                            "tool": tool_name,
                            "params": params,
                        })

                        if tool_name in ("web_search", "搜索"):
                            query = params.get("query", "")
                            self.status_update.emit(f"🔍 搜索: {query}")
                        elif tool_name in ("web_scrape", "抓取"):
                            url = params.get("url", "")
                            display_url = url if len(url) <= 60 else url[:57] + "..."
                            self.status_update.emit(f"🌐 抓取: {display_url}")
                        else:
                            self.status_update.emit(f"📋 {action_desc}...")

                        step_start = time.time()
                        result = self.engine._execute_tool(tool_name, params)
                        elapsed = time.time() - step_start

                        if result.success and tool_name in ("web_search", "搜索"):
                            data = result.data or {}
                            results_list = data.get("results", [])
                            self.status_update.emit(f"✅ 搜索完成: 找到 {len(results_list)} 条结果")
                            for item in results_list:
                                collected_sources.append({
                                    "title": item.get("title", ""),
                                    "url": item.get("url", ""),
                                    "snippet": item.get("snippet", ""),
                                })

                        all_results.append({
                            "step": i + 1,
                            "tool": tool_name,
                            "action": action_desc,
                            "success": result.success,
                            "result": result.data if result.success else None,
                            "error": result.error if not result.success else None,
                            "elapsed": round(elapsed, 1),
                        })

                        self.step_update.emit({
                            "type": "step_complete",
                            "step_index": i,
                            "total_steps": total_steps,
                            "action": action_desc,
                            "success": result.success,
                            "elapsed": round(elapsed, 1),
                        })

                    self.status_update.emit("📝 生成报告...")
                    report = self.engine._generate_final_report(self.goal, all_results)

                    self.result_ready.emit({
                        "type": "agent",
                        "content": report,
                        "task_plan": {"goal": self.goal, "steps": self.steps},
                        "sources": collected_sources,
                    })
                except Exception as e:
                    self.error.emit(str(e))

        self._agent_worker = DirectExecWorker(
            engine=self._agent_engine,
            steps=steps,
            goal=goal,
            parent=self,
        )
        self._agent_worker.status_update.connect(self._on_agent_status)
        self._agent_worker.step_update.connect(self._on_agent_step)
        self._agent_worker.result_ready.connect(self._on_agent_result)
        self._agent_worker.error.connect(self._on_agent_error)
        self._agent_worker.start()

    # ==================== 来源引用 ====================

    def _append_source_card(self, sources: list):
        """在对话区域追加来源引用卡片"""
        card = SourceCardWidget(sources)
        card.setFixedWidth(self.message_list_widget.width() - 32)

        row = QWidget()
        row.setStyleSheet("background-color: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 2, 8, 2)
        row_layout.addStretch()
        row_layout.addWidget(card)
        row_layout.addStretch()

        count = self.message_list_layout.count()
        self.message_list_layout.insertWidget(count - 1, row)
        QTimer.singleShot(50, self._scroll_to_bottom)

    # ==================== 重写生成状态 ====================

    def _set_generating_state(self, is_generating: bool):
        """重写以同时控制停止按钮"""
        super()._set_generating_state(is_generating)
        if hasattr(self, "_stop_btn"):
            self._stop_btn.setEnabled(is_generating)

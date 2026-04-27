"""
文本对话 Tab 组件。
"""
import re
from typing import Callable, Dict, Any, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QTextEdit, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QScrollArea, QMessageBox
)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtCore import Qt

from ..components.common import GenerationThread


class ChatTabWidget(QScrollArea):
    """文本对话 Tab（多轮）"""

    def __init__(
        self,
        client_getter: Callable[[], Any],
        check_client_func: Callable[[], bool],
        get_show_thinking_func: Callable[[], bool] = lambda: False,
        parent=None
    ):
        super().__init__(parent)
        self.client_getter = client_getter
        self.check_client_func = check_client_func
        self.get_show_thinking_func = get_show_thinking_func
        self.chat_messages: List[Dict[str, str]] = []
        self.generation_thread = None
        self._build_ui()

    def _build_ui(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_params_group())

        layout.addWidget(QLabel("System 提示词（可选）:"))
        self.chat_system_prompt = QTextEdit()
        self.chat_system_prompt.setPlaceholderText("例如：你是一个专业、简洁的 AI 助手。")
        self.chat_system_prompt.setMaximumHeight(70)
        layout.addWidget(self.chat_system_prompt)

        layout.addWidget(QLabel("对话历史:"))
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setPlaceholderText("对话内容会显示在这里...")
        self.chat_history.setMinimumHeight(280)
        layout.addWidget(self.chat_history)

        layout.addWidget(QLabel("输入内容:"))
        self.chat_input = QTextEdit()
        self.chat_input.setPlaceholderText("输入消息后点击发送；支持 Ctrl+Enter 快速发送")
        self.chat_input.setMaximumHeight(110)
        layout.addWidget(self.chat_input)

        layout.addLayout(self._create_action_layout())

        self.chat_status = QLabel("")
        self.chat_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.chat_status)

        layout.addStretch()
        self.setWidget(widget)

        self.setWidgetResizable(True)
        self._init_send_shortcuts()

    def _create_params_group(self) -> QGroupBox:
        params_group = QGroupBox("对话参数")
        params_layout = QFormLayout()

        self.chat_model = QComboBox()
        self.chat_model.addItems([
            "MiniMax-M2.7",
            "MiniMax-M2.7-highspeed",
            "MiniMax-M2.5",
            "MiniMax-M2.1"
        ])
        params_layout.addRow("模型:", self.chat_model)

        self.chat_max_tokens = QSpinBox()
        self.chat_max_tokens.setRange(1, 2048)
        self.chat_max_tokens.setValue(512)
        params_layout.addRow("最大回复Token:", self.chat_max_tokens)

        self.chat_temperature = QDoubleSpinBox()
        self.chat_temperature.setRange(0.01, 1.0)
        self.chat_temperature.setSingleStep(0.05)
        self.chat_temperature.setValue(0.7)
        params_layout.addRow("温度:", self.chat_temperature)

        self.chat_top_p = QDoubleSpinBox()
        self.chat_top_p.setRange(0.01, 1.0)
        self.chat_top_p.setSingleStep(0.05)
        self.chat_top_p.setValue(0.95)
        params_layout.addRow("Top P:", self.chat_top_p)

        params_group.setLayout(params_layout)
        return params_group

    def _create_action_layout(self) -> QHBoxLayout:
        btn_layout = QHBoxLayout()
        self.chat_send_btn = QPushButton("📨 发送")
        self.chat_send_btn.clicked.connect(self.send_chat_message)
        btn_layout.addWidget(self.chat_send_btn)

        self.chat_clear_btn = QPushButton("🧹 清空历史")
        self.chat_clear_btn.clicked.connect(self.clear_chat_history)
        btn_layout.addWidget(self.chat_clear_btn)
        btn_layout.addStretch()
        return btn_layout

    def _init_send_shortcuts(self):
        self._send_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.chat_input)
        self._send_shortcut.activated.connect(self.send_chat_message)
        self._send_shortcut2 = QShortcut(QKeySequence("Ctrl+Enter"), self.chat_input)
        self._send_shortcut2.activated.connect(self.send_chat_message)

    def _append_chat_message(self, role: str, content: str):
        role_map = {
            "user": "你",
            "assistant": "助手",
            "system": "系统"
        }
        title = role_map.get(role, role)
        self.chat_history.append(f"[{title}]")
        self.chat_history.append(content)
        self.chat_history.append("")

    @staticmethod
    def _strip_thinking_content(text: str) -> str:
        """去除模型返回中的思考片段，避免展示给用户。"""
        if not text:
            return ""
        cleaned = re.sub(r"<think\b[^>]*>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"</?think\b[^>]*>", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def send_chat_message(self):
        """发送文本对话消息"""
        if not self.check_client_func():
            return

        user_text = self.chat_input.toPlainText().strip()
        if not user_text:
            QMessageBox.warning(self, "警告", "请输入对话内容")
            return

        self.chat_send_btn.setEnabled(False)
        self.chat_status.setText("正在生成回复...")

        user_msg = {"role": "user", "content": user_text}
        self.chat_messages.append(user_msg)
        self._append_chat_message("user", user_text)
        self.chat_input.clear()

        system_prompt = self.chat_system_prompt.toPlainText().strip()
        request_messages = []
        if system_prompt:
            request_messages.append({"role": "system", "content": system_prompt})
        request_messages.extend(self.chat_messages)

        def do_chat():
            client = self.client_getter()
            return client.chat_completions(
                messages=request_messages,
                model=self.chat_model.currentText(),
                stream=False,
                max_completion_tokens=self.chat_max_tokens.value(),
                temperature=self.chat_temperature.value(),
                top_p=self.chat_top_p.value(),
                timeout=120
            )

        self.generation_thread = GenerationThread(do_chat)
        self.generation_thread.finished.connect(self.on_chat_finished)
        self.generation_thread.error.connect(self.on_chat_error)
        self.generation_thread.start()

    def on_chat_finished(self, result):
        """文本对话完成"""
        self.chat_send_btn.setEnabled(True)

        choices = result.get("choices", [])
        assistant_text = ""
        if choices:
            message = choices[0].get("message", {})
            raw_content = message.get("content", "")
            if self.get_show_thinking_func():
                assistant_text = raw_content.strip()
            else:
                assistant_text = self._strip_thinking_content(raw_content)

        if assistant_text:
            self.chat_messages.append({"role": "assistant", "content": assistant_text})
            self._append_chat_message("assistant", assistant_text)
            usage = result.get("usage", {})
            total_tokens = usage.get("total_tokens")
            if total_tokens is not None:
                self.chat_status.setText(f"✓ 回复完成（总 Token: {total_tokens}）")
            else:
                self.chat_status.setText("✓ 回复完成")
        else:
            self.chat_status.setText("✗ 未获取到有效回复")

    def on_chat_error(self, error_msg: str):
        """文本对话错误"""
        self.chat_send_btn.setEnabled(True)
        self.chat_status.setText("✗ 对话失败")
        QMessageBox.critical(self, "错误", f"对话失败: {error_msg}")

    def clear_chat_history(self):
        """清空文本对话历史"""
        self.chat_messages = []
        self.chat_history.clear()
        self.chat_status.setText("已清空对话历史")

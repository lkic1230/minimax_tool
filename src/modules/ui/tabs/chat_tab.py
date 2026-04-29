"""
文本对话 Tab 组件（气泡式聊天 UI）。
"""
import re
from typing import Callable, Dict, Any, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QTextEdit, QLineEdit, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QScrollArea, QMessageBox, QSplitter, QDialog
)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtCore import Qt, QTimer

from ..components.common import GenerationThread
from ..components.chat_message_widget import (
    MessageBubbleWidget, create_message_row
)
from ..components.chat_history_manager import ChatHistoryManager
from ..components.chat_history_dialog import ChatHistoryDialog
from ...core.constants import (
    CHAT_MODELS,
    CHAT_MAX_TOKENS_MIN,
    CHAT_MAX_TOKENS_MAX,
    CHAT_MAX_TOKENS_DEFAULT,
    CHAT_TEMPERATURE_MIN,
    CHAT_TEMPERATURE_MAX,
    CHAT_TEMPERATURE_DEFAULT,
    CHAT_TOP_P_MIN,
    CHAT_TOP_P_MAX,
    CHAT_TOP_P_DEFAULT,
    CHAT_SAMPLING_PRESETS,
    CHAT_SAMPLING_CUSTOM_LABEL,
)


class ChatTabWidget(QWidget):
    """文本对话 Tab（多轮气泡式）"""

    # ==================== 工具栏 ====================

    def _build_toolbar(self, parent_layout):
        """构建顶部工具栏（新对话 / 保存 / 历史）。"""
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 6, 8, 6)

        # ---- 左侧：新对话按钮 + 当前对话标题 ----
        self.new_chat_btn = QPushButton("➕ 新对话")
        self.new_chat_btn.setFixedHeight(30)
        self.new_chat_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #43a047; }
        """)
        self.new_chat_btn.clicked.connect(self._new_conversation)
        toolbar_layout.addWidget(self.new_chat_btn)

        # 当前对话标题
        self.conv_title_label = QLabel("未保存的对话")
        self.conv_title_label.setStyleSheet("color: #888; font-size: 12px; padding-left: 8px;")
        toolbar_layout.addWidget(self.conv_title_label)

        toolbar_layout.addStretch()

        # ---- 右侧：保存 / 历史按钮 ----
        self.save_btn = QPushButton("💾 保存")
        self.save_btn.setFixedHeight(30)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #1976d2; }
        """)
        self.save_btn.clicked.connect(self._save_conversation)
        toolbar_layout.addWidget(self.save_btn)

        self.history_btn = QPushButton("📂 历史")
        self.history_btn.setFixedHeight(30)
        self.history_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #f57c00; }
        """)
        self.history_btn.clicked.connect(self._show_history)
        toolbar_layout.addWidget(self.history_btn)

        parent_layout.addWidget(toolbar)

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
        self._current_conv_id: str | None = None  # 当前已保存的对话 ID
        self._current_conv_title: str | None = None
        self._is_dirty = False
        self._suspend_dirty_tracking = False
        self._is_generating = False
        self._history_manager = ChatHistoryManager()
        self._build_ui()

    def _build_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # ===== 顶部工具栏：新对话 / 保存 / 历史 =====
        self._build_toolbar(outer_layout)

        # ===== 上部：参数区（可折叠） =====
        params_group = QGroupBox("对话参数")
        params_layout = QVBoxLayout(params_group)
        params_layout.setContentsMargins(8, 8, 8, 8)
        params_layout.setSpacing(6)
        top_row = QHBoxLayout()
        bottom_row = QHBoxLayout()

        self.chat_model = QComboBox()
        self.chat_model.addItems(CHAT_MODELS)
        top_row.addWidget(QLabel("模型:"))
        top_row.addWidget(self.chat_model)

        top_row.addWidget(QLabel("Token:"))
        self.chat_max_tokens = QSpinBox()
        self.chat_max_tokens.setRange(CHAT_MAX_TOKENS_MIN, CHAT_MAX_TOKENS_MAX)
        self.chat_max_tokens.setValue(CHAT_MAX_TOKENS_DEFAULT)
        self.chat_max_tokens.setFixedWidth(80)
        top_row.addWidget(self.chat_max_tokens)

        top_row.addWidget(QLabel("风格:"))
        self.sampling_preset_combo = QComboBox()
        self.sampling_preset_combo.setFixedWidth(120)
        self.sampling_preset_combo.addItems([name for name, _, _ in CHAT_SAMPLING_PRESETS] + [CHAT_SAMPLING_CUSTOM_LABEL])
        top_row.addWidget(self.sampling_preset_combo)

        top_row.addWidget(QLabel("温度:"))
        self.chat_temperature = QDoubleSpinBox()
        self.chat_temperature.setRange(CHAT_TEMPERATURE_MIN, CHAT_TEMPERATURE_MAX)
        self.chat_temperature.setSingleStep(0.05)
        self.chat_temperature.setValue(CHAT_TEMPERATURE_DEFAULT)
        self.chat_temperature.setFixedWidth(70)
        top_row.addWidget(self.chat_temperature)

        top_row.addWidget(QLabel("TopP:"))
        self.chat_top_p = QDoubleSpinBox()
        self.chat_top_p.setRange(CHAT_TOP_P_MIN, CHAT_TOP_P_MAX)
        self.chat_top_p.setSingleStep(0.05)
        self.chat_top_p.setValue(CHAT_TOP_P_DEFAULT)
        self.chat_top_p.setFixedWidth(70)
        top_row.addWidget(self.chat_top_p)
        self.sampling_preset_combo.currentTextChanged.connect(self._on_sampling_preset_changed)
        self._on_sampling_preset_changed(self.sampling_preset_combo.currentText())
        top_row.addStretch()

        sys_label = QLabel("系统提示词:")
        bottom_row.addWidget(sys_label)
        self.chat_system_prompt = QLineEdit()
        self.chat_system_prompt.setPlaceholderText("可选：例如“请用中文回答，先给结论再给步骤”")
        bottom_row.addWidget(self.chat_system_prompt, 1)

        self.chat_clear_btn = QPushButton("清空当前对话")
        self.chat_clear_btn.setToolTip("清空当前会话中的所有消息，不会删除历史记录")
        self.chat_clear_btn.setFixedWidth(110)
        self.chat_clear_btn.clicked.connect(self.clear_chat_history)
        bottom_row.addWidget(self.chat_clear_btn)

        params_layout.addLayout(top_row)
        params_layout.addLayout(bottom_row)

        outer_layout.addWidget(params_group)

        # ===== 中部：消息区 + 输入区（上下分割） =====
        splitter = QSplitter(Qt.Vertical)

        # --- 消息列表（QScrollArea） ---
        self.message_scroll = QScrollArea()
        self.message_scroll.setWidgetResizable(True)
        self.message_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.message_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #e8e8e8;
            }
        """)

        self.message_list_widget = QWidget()
        self.message_list_widget.setStyleSheet("background-color: #e8e8e8;")
        self.message_list_layout = QVBoxLayout(self.message_list_widget)
        self.message_list_layout.setContentsMargins(4, 8, 4, 8)
        self.message_list_layout.setSpacing(4)
        self.message_list_layout.addStretch()  # 底部弹性空间

        self.message_scroll.setWidget(self.message_list_widget)
        splitter.addWidget(self.message_scroll)

        # --- 输入区 ---
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        input_layout.setContentsMargins(8, 4, 8, 4)
        input_layout.setSpacing(4)

        self.chat_input = QTextEdit()
        self.chat_input.setPlaceholderText("输入消息后点击发送；支持 Ctrl+Enter 快速发送")
        self.chat_input.setMinimumHeight(60)
        self.chat_input.setMaximumHeight(120)
        self.chat_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 8px;
                padding: 8px;
                font-size: 13px;
            }
        """)
        input_layout.addWidget(self.chat_input)

        btn_layout = QHBoxLayout()
        self.chat_status = QLabel("")
        self.chat_status.setStyleSheet("color: #666; font-size: 12px;")
        btn_layout.addWidget(self.chat_status)
        btn_layout.addStretch()

        self.chat_send_btn = QPushButton("发送")
        self.chat_send_btn.setFixedWidth(80)
        self.chat_send_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #a5d6a7;
            }
            QPushButton:hover {
                background-color: #43a047;
            }
        """)
        self.chat_send_btn.clicked.connect(self.send_chat_message)
        btn_layout.addWidget(self.chat_send_btn)
        input_layout.addLayout(btn_layout)

        splitter.addWidget(input_widget)

        # 分割比例：消息区占大部分
        splitter.setSizes([700, 160])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        outer_layout.addWidget(splitter, 1)

        # 快捷键
        self._send_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.chat_input)
        self._send_shortcut.activated.connect(self.send_chat_message)
        self._send_shortcut2 = QShortcut(QKeySequence("Ctrl+Enter"), self.chat_input)
        self._send_shortcut2.activated.connect(self.send_chat_message)

        # 参数变更也应标记为“有未保存修改”
        self.chat_model.currentTextChanged.connect(self._mark_conversation_dirty)
        self.chat_max_tokens.valueChanged.connect(self._mark_conversation_dirty)
        self.chat_temperature.valueChanged.connect(self._mark_conversation_dirty)
        self.chat_top_p.valueChanged.connect(self._mark_conversation_dirty)
        self.chat_system_prompt.textChanged.connect(self._mark_conversation_dirty)

    def _refresh_conversation_title_label(self):
        """根据当前保存/脏状态刷新标题显示。"""
        if self._current_conv_title:
            suffix = " *" if self._is_dirty else ""
            self.conv_title_label.setText(f"📁 {self._current_conv_title}{suffix}")
            color = "#ff9800" if self._is_dirty else "#4caf50"
            self.conv_title_label.setStyleSheet(f"color: {color}; font-size: 12px; padding-left: 8px;")
            return
        self.conv_title_label.setText("未保存的对话")
        self.conv_title_label.setStyleSheet("color: #888; font-size: 12px; padding-left: 8px;")

    def _mark_conversation_dirty(self, *_args):
        """标记当前会话有未保存修改。"""
        if self._suspend_dirty_tracking:
            return
        self._is_dirty = True
        self._refresh_conversation_title_label()

    def _mark_conversation_clean(self):
        """标记当前会话已保存。"""
        self._is_dirty = False
        self._refresh_conversation_title_label()

    def _auto_save_current_conversation(self) -> bool:
        """对已保存会话执行静默覆盖保存（不弹框）。"""
        if not self._current_conv_id:
            return False
        title = (self._current_conv_title or "").strip()
        if not title:
            return False
        try:
            self._history_manager.save(
                conv_id=self._current_conv_id,
                title=title,
                messages=self.chat_messages,
                model=self.chat_model.currentText(),
                max_tokens=self.chat_max_tokens.value(),
                temperature=self.chat_temperature.value(),
                top_p=self.chat_top_p.value(),
                system_prompt=self.chat_system_prompt.text().strip(),
            )
            self._mark_conversation_clean()
            return True
        except Exception:
            return False

    def _scroll_to_bottom(self):
        """滚动消息区到底部。"""
        sb = self.message_scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_generating_state(self, is_generating: bool):
        """统一控制生成中的 UI 交互状态，避免并发修改会话。"""
        self._is_generating = is_generating
        self.chat_send_btn.setEnabled(not is_generating)
        self.chat_input.setEnabled(not is_generating)
        self.new_chat_btn.setEnabled(not is_generating)
        self.save_btn.setEnabled(not is_generating)
        self.history_btn.setEnabled(not is_generating)
        self.chat_clear_btn.setEnabled(not is_generating)

    @staticmethod
    def _strip_thinking_content(text: str) -> str:
        """去除模型返回中的思考片段，避免展示给用户。"""
        if not text:
            return ""

        fence_pattern = r"(```[\s\S]*?```|~~~[\s\S]*?~~~)"
        parts = re.split(fence_pattern, text)

        cleaned_parts = []
        for part in parts:
            if not part:
                continue
            if re.fullmatch(fence_pattern, part):
                cleaned_parts.append(part)
                continue

            cleaned = re.sub(r"<think\b[^>]*>[\s\S]*?</think\s*>", "", part, flags=re.IGNORECASE)
            cleaned = re.sub(r"</?think\b[^>]*>", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
            cleaned_parts.append(cleaned)

        return "".join(cleaned_parts).strip()

    def _on_sampling_preset_changed(self, preset_name: str):
        """切换采样预设：预设值只读，自定义可手输。"""
        presets = {name: (temp, top_p) for name, temp, top_p in CHAT_SAMPLING_PRESETS}
        if preset_name == CHAT_SAMPLING_CUSTOM_LABEL:
            self.chat_temperature.setEnabled(True)
            self.chat_top_p.setEnabled(True)
            return

        values = presets.get(preset_name)
        if values:
            temp, top_p = values
            self.chat_temperature.setValue(temp)
            self.chat_top_p.setValue(top_p)
        self.chat_temperature.setEnabled(False)
        self.chat_top_p.setEnabled(False)

    def _sync_sampling_preset_from_values(self):
        """根据当前温度/TopP 自动选择对应预设，匹配不到则切到自定义。"""
        temp = round(self.chat_temperature.value(), 2)
        top_p = round(self.chat_top_p.value(), 2)
        presets = {name: (temp_v, top_p_v) for name, temp_v, top_p_v in CHAT_SAMPLING_PRESETS}
        for name, values in presets.items():
            if values == (temp, top_p):
                self.sampling_preset_combo.setCurrentText(name)
                return
        self.sampling_preset_combo.setCurrentText(CHAT_SAMPLING_CUSTOM_LABEL)

    # ==================== 发送逻辑 ====================

    def send_chat_message(self):
        """发送文本对话消息"""
        if not self.check_client_func():
            return
        if self._is_generating:
            return

        user_text = self.chat_input.toPlainText().strip()
        if not user_text:
            return

        self._set_generating_state(True)
        self.chat_status.setText("正在生成回复...")

        user_msg = {"role": "user", "content": user_text}
        self.chat_messages.append(user_msg)
        self._mark_conversation_dirty()
        self._append_message("user", user_text)
        self.chat_input.clear()

        system_prompt = self.chat_system_prompt.text().strip()
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
        if self.sender() is not self.generation_thread:
            return
        self.generation_thread = None
        self._set_generating_state(False)

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
            self._mark_conversation_dirty()
            # 从 API 返回中取模型名显示在气泡底部
            model_name = result.get("model", self.chat_model.currentText())
            self._append_message("assistant", assistant_text, author=model_name)
            usage = result.get("usage", {})
            total_tokens = usage.get("total_tokens")
            if total_tokens is not None:
                self.chat_status.setText(f"回复完成 (Token: {total_tokens})")
            else:
                self.chat_status.setText("回复完成")
            if self._auto_save_current_conversation():
                self.chat_status.setText(f"{self.chat_status.text()} · 已自动保存")
        else:
            self.chat_status.setText("未获取到有效回复")

    def on_chat_error(self, error_msg: str):
        """文本对话错误"""
        if self.sender() is not self.generation_thread:
            return
        self.generation_thread = None
        self._set_generating_state(False)
        self.chat_status.setText("对话失败")
        QMessageBox.critical(self, "错误", f"对话失败: {error_msg}")

    def clear_chat_history(self):
        """清空文本对话历史"""
        if self._is_generating:
            QMessageBox.information(self, "提示", "正在生成回复，请稍后再清空对话。")
            return
        self.chat_messages = []
        self._current_conv_id = None
        self._current_conv_title = None
        self._mark_conversation_clean()
        # 移除所有消息行，保留底部 stretch
        while self.message_list_layout.count() > 1:
            item = self.message_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.chat_status.setText("已清空对话历史")

    # ==================== 对话历史管理 ====================

    def _new_conversation(self):
        """新建对话（先提示保存）。"""
        if self._is_generating:
            QMessageBox.information(self, "提示", "正在生成回复，请稍后再新建对话。")
            return
        if self.chat_messages and self._is_dirty:
            reply = QMessageBox.question(
                self, "新对话",
                "当前对话尚未保存，是否先保存再开始新对话？",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if reply == QMessageBox.Save:
                # 保存失败或用户取消输入标题时，不应清空当前对话
                if not self._save_conversation():
                    return
            elif reply == QMessageBox.Cancel:
                return
        self.clear_chat_history()

    def _save_conversation(self):
        """保存当前对话到缓存目录。"""
        if not self.chat_messages:
            QMessageBox.information(self, "提示", "当前没有对话内容可以保存。")
            return False

        title = (self._current_conv_title or "").strip()
        # 首次保存时才要求输入标题；后续保存默认覆盖当前会话
        if not title:
            title, ok = self._get_conversation_title(default_title="")
            if not ok or not title:
                return False

        try:
            conv_id = self._history_manager.save(
                conv_id=self._current_conv_id,
                title=title,
                messages=self.chat_messages,
                model=self.chat_model.currentText(),
                max_tokens=self.chat_max_tokens.value(),
                temperature=self.chat_temperature.value(),
                top_p=self.chat_top_p.value(),
                system_prompt=self.chat_system_prompt.text().strip(),
            )
            self._current_conv_id = conv_id
            self._current_conv_title = title
            self._mark_conversation_clean()
            self.chat_status.setText(f"对话已保存: {title}")
            return True
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存对话失败: {e}")
            return False

    def _get_conversation_title(self, default_title: str = "") -> tuple[str, bool]:
        """弹窗让用户输入对话标题，返回（标题, 确认）。"""
        from PySide6.QtWidgets import QInputDialog
        # 默认优先使用当前会话标题；若没有则自动从首条用户消息生成
        default_title = (default_title or "").strip()
        if not default_title:
            for msg in self.chat_messages:
                if msg.get("role") == "user":
                    default_title = msg["content"][:40].strip()
                    if len(msg["content"]) > 40:
                        default_title += "..."
                    break
        if not default_title:
            default_title = "新对话"

        title, ok = QInputDialog.getText(
            self, "保存对话", "请输入对话标题：", text=default_title
        )
        return title.strip() if title else "", ok

    def _show_history(self):
        """展示历史对话弹窗，支持加载和删除。"""
        if self._is_generating:
            QMessageBox.information(self, "提示", "正在生成回复，请稍后再加载历史。")
            return
        dialog = ChatHistoryDialog(self._history_manager, self)
        if dialog.exec() == QDialog.Accepted and dialog.selected_id:
            self._load_conversation(dialog.selected_id)

    def _load_conversation(self, conv_id: str):
        """从缓存加载指定对话并渲染到 UI。"""
        data = self._history_manager.load(conv_id)
        if not data:
            QMessageBox.warning(self, "加载失败", "找不到该对话记录。")
            return

        # 确认是否覆盖当前对话
        if self.chat_messages:
            reply = QMessageBox.question(
                self, "加载对话",
                "加载历史对话将清空当前对话，是否继续？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # 恢复参数（加载过程中不应触发 dirty）
        self._suspend_dirty_tracking = True
        try:
            model = data.get("model", self.chat_model.itemText(0))
            idx = self.chat_model.findText(model)
            if idx >= 0:
                self.chat_model.setCurrentIndex(idx)
            self.chat_max_tokens.setValue(data.get("max_tokens", CHAT_MAX_TOKENS_DEFAULT))
            self.chat_temperature.setValue(data.get("temperature", CHAT_TEMPERATURE_DEFAULT))
            self.chat_top_p.setValue(data.get("top_p", CHAT_TOP_P_DEFAULT))
            self.chat_system_prompt.setText(data.get("system_prompt", ""))
            self._sync_sampling_preset_from_values()
        finally:
            self._suspend_dirty_tracking = False

        # 渲染消息到 UI
        self.chat_messages = data.get("messages", [])
        self._current_conv_id = conv_id
        self._current_conv_title = data.get("title", "").strip() or "未命名"

        # 清空 UI 消息并重新渲染
        while self.message_list_layout.count() > 1:
            item = self.message_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for msg in self.chat_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                self._append_message("user", content, author="我")
            elif role == "assistant":
                # 加载时无法知道原模型名，用保存时的 model 字段
                self._append_message("assistant", content, author=data.get("model", ""))
            # system 消息不单独渲染，由参数区 system prompt 恢复

        self._mark_conversation_clean()
        self.chat_status.setText(f"已加载对话: {data.get('title', '')}")

    def _append_message(self, role: str, content: str, author: str = None):
        """向消息列表追加一条气泡消息。"""
        bubble = MessageBubbleWidget(role, content, author=author)
        row = create_message_row(bubble)

        # 插入到底部 stretch 之前
        count = self.message_list_layout.count()
        self.message_list_layout.insertWidget(count - 1, row)

        # 延迟滚动到底部
        QTimer.singleShot(50, self._scroll_to_bottom)

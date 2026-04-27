"""
配置 Tab 组件（self-contained Widget）。
"""
import os
from typing import Callable

from PySide6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QGroupBox, QLineEdit, QPushButton, QLabel,
    QHBoxLayout, QMessageBox, QFileDialog, QCheckBox, QApplication
)
from PySide6.QtCore import Qt


class ConfigTabWidget(QScrollArea):
    """配置 Tab（self-contained）"""

    def __init__(
        self,
        config_manager,
        on_api_key_saved: Callable[[], None],
        on_output_dir_changed: Callable[[], None],
        get_default_outputs_dir: Callable[[], str],
        parent=None
    ):
        super().__init__(parent)
        self.config_manager = config_manager
        self.on_api_key_saved = on_api_key_saved
        self.on_output_dir_changed = on_output_dir_changed
        self.get_default_outputs_dir = get_default_outputs_dir
        self._build_ui()

    def _build_ui(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_api_key_group())
        layout.addWidget(self._create_output_group())
        layout.addWidget(self._create_chat_display_group())
        layout.addWidget(self._create_security_group())

        layout.setAlignment(Qt.AlignTop)
        self.setWidget(widget)
        self.setWidgetResizable(True)

    @staticmethod
    def _make_group(title: str, content_layout) -> QGroupBox:
        group = QGroupBox(title)
        group.setLayout(content_layout)
        return group

    @staticmethod
    def _make_button(
        text: str,
        on_click,
        style: str = "",
        tooltip: str = ""
    ) -> QPushButton:
        btn = QPushButton(text)
        if style:
            btn.setStyleSheet(style)
        if tooltip:
            btn.setToolTip(tooltip)
        btn.clicked.connect(on_click)
        return btn

    def _create_api_key_group(self) -> QGroupBox:
        key_layout = QVBoxLayout()

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("输入 MiniMax API 密钥")
        key_layout.addWidget(self.api_key_input)

        key_btn_layout = QHBoxLayout()
        self.save_key_btn = self._make_button("💾 保存密钥", self._save_api_key)
        key_btn_layout.addWidget(self.save_key_btn)

        self.delete_key_btn = self._make_button(
            "🗑️ 删除密钥",
            self._delete_api_key,
            style="color: #ff5555;",
        )
        key_btn_layout.addWidget(self.delete_key_btn)

        key_btn_layout.addStretch()
        key_layout.addLayout(key_btn_layout)

        self.api_key_hint_label = QLabel("")
        self.api_key_hint_label.setStyleSheet("color: #888; font-size: 12px;")
        key_layout.addWidget(self.api_key_hint_label)

        self.api_key_status_label = QLabel("")
        self._refresh_api_key_status()
        key_layout.addWidget(self.api_key_status_label)
        return self._make_group("API 密钥", key_layout)

    def _create_output_group(self) -> QGroupBox:
        output_layout = QVBoxLayout()

        output_path_layout = QHBoxLayout()
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setText(self.config_manager.get_output_dir())
        output_path_layout.addWidget(self.output_dir_input)

        select_dir_btn = self._make_button("📁 浏览", self._select_output_dir)
        output_path_layout.addWidget(select_dir_btn)
        output_layout.addLayout(output_path_layout)

        output_btn_layout = QHBoxLayout()
        save_output_btn = self._make_button("💾 保存", self._save_output_dir)
        output_btn_layout.addWidget(save_output_btn)

        reset_output_btn = self._make_button("↩️ 恢复默认", self._reset_output_dir)
        output_btn_layout.addWidget(reset_output_btn)

        open_output_btn = self._make_button("📂 打开文件夹", self._open_output_dir)
        output_btn_layout.addWidget(open_output_btn)

        output_btn_layout.addStretch()
        output_layout.addLayout(output_btn_layout)
        output_layout.addWidget(QLabel(f"默认目录: {self.get_default_outputs_dir()}"))
        return self._make_group("输出目录", output_layout)

    def _create_chat_display_group(self) -> QGroupBox:
        chat_display_layout = QVBoxLayout()

        self.show_thinking_checkbox = QCheckBox("在文本对话中显示模型思考过程（<think>）")
        self.show_thinking_checkbox.setChecked(self.config_manager.get_show_thinking())
        self.show_thinking_checkbox.stateChanged.connect(self._save_show_thinking)
        chat_display_layout.addWidget(self.show_thinking_checkbox)

        chat_display_tip = QLabel("建议默认关闭，仅在调试或开发排查时开启。")
        chat_display_tip.setStyleSheet("color: #888; font-size: 12px;")
        chat_display_layout.addWidget(chat_display_tip)
        return self._make_group("对话显示", chat_display_layout)

    def _create_security_group(self) -> QGroupBox:
        security_layout = QVBoxLayout()

        security_layout.addWidget(QLabel(
            "共享计算机时，建议在使用完毕后清理本地缓存的 API 密钥和配置，\n"
            "避免 API Key 泄露。"
        ))

        security_info_layout = QHBoxLayout()
        security_info_layout.addWidget(QLabel("配置目录:"))
        config_dir_label = QLabel(f"{self.config_manager.config_dir}")
        config_dir_label.setStyleSheet("color: #888; font-size: 12px;")
        config_dir_label.setWordWrap(True)
        security_info_layout.addWidget(config_dir_label, 1)
        security_layout.addLayout(security_info_layout)

        clear_cache_btn = self._make_button(
            "🧹 清除缓存",
            self._clear_cache,
            tooltip="清除缓存目录中的所有临时文件",
        )
        security_layout.addWidget(clear_cache_btn)

        clear_all_btn = self._make_button(
            "⚠️ 清除所有数据（API 密钥 + 配置 + 缓存）",
            self._clear_all_data,
            style="color: #ff5555; font-weight: bold;",
            tooltip="删除本地存储的 API 密钥、加密配置和所有缓存",
        )
        security_layout.addWidget(clear_all_btn)
        return self._make_group("安全与清理", security_layout)

    # ==================== API 密钥操作 ====================

    def _refresh_api_key_status(self):
        if self.config_manager.has_api_key():
            masked = self.config_manager._mask_api_key(self.config_manager.get_api_key())
            self.api_key_status_label.setText(f"✓ 已配置: {masked}")
            self.api_key_status_label.setStyleSheet("color: #4caf50;")
        else:
            self.api_key_status_label.setText("✗ 未配置 API 密钥")
            self.api_key_status_label.setStyleSheet("color: #ff9800;")

    def _save_api_key(self):
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "警告", "请输入 API 密钥")
            return

        if self.config_manager.set_api_key(api_key):
            self._set_api_key_hint("正在校验 API 密钥，请稍候...", "#888")
            self._set_api_key_buttons_enabled(False)
            QApplication.processEvents()
            self.on_api_key_saved()
            self._set_api_key_buttons_enabled(True)
            self.api_key_input.clear()
            self._refresh_api_key_status()
        else:
            QMessageBox.warning(self, "失败", "保存失败")

    def _delete_api_key(self):
        if not self.config_manager.has_api_key():
            QMessageBox.information(self, "提示", "当前未配置 API 密钥")
            return

        reply = QMessageBox.warning(
            self, "确认删除",
            "确定要删除本地存储的 API 密钥吗？\n\n"
            "删除后将无法使用生成功能，需重新输入密钥。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        if self.config_manager.delete_api_key():
            self._set_api_key_hint("API 密钥已删除。", "#ff9800")
            self._refresh_api_key_status()
            self.on_api_key_saved()  # 通知主窗口重置客户端
            QMessageBox.information(self, "成功", "API 密钥已删除")
        else:
            QMessageBox.warning(self, "失败", "删除失败")

    def _set_api_key_hint(self, text: str, color: str = "#888"):
        self.api_key_hint_label.setText(text)
        self.api_key_hint_label.setStyleSheet(f"color: {color}; font-size: 12px;")

    def _set_api_key_buttons_enabled(self, enabled: bool):
        self.save_key_btn.setEnabled(enabled)
        self.delete_key_btn.setEnabled(enabled)

    # ==================== 输出目录操作 ====================

    def _save_output_dir(self):
        output_dir = self.output_dir_input.text().strip()
        if self.config_manager.set_output_dir(output_dir):
            QMessageBox.information(self, "成功", "输出目录已保存")
            self.on_output_dir_changed()
        else:
            QMessageBox.warning(self, "失败", "保存失败")

    def _reset_output_dir(self):
        default_dir = str(self.get_default_outputs_dir())
        self.output_dir_input.setText(default_dir)
        if self.config_manager.set_output_dir(default_dir):
            QMessageBox.information(self, "成功", f"已恢复默认目录: {default_dir}")
            self.on_output_dir_changed()

    def _select_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择输出目录", self.output_dir_input.text()
        )
        if dir_path:
            self.output_dir_input.setText(dir_path)

    def _open_output_dir(self):
        output_dir = self.config_manager.get_output_dir()
        if os.path.isdir(output_dir):
            os.startfile(output_dir)
        else:
            QMessageBox.warning(self, "提示", f"输出目录不存在: {output_dir}")

    def _save_show_thinking(self, state):
        show_thinking = (state != 0)
        if not self.config_manager.set_show_thinking(show_thinking):
            self.show_thinking_checkbox.blockSignals(True)
            self.show_thinking_checkbox.setChecked(not show_thinking)
            self.show_thinking_checkbox.blockSignals(False)
            QMessageBox.warning(self, "失败", "保存对话显示设置失败")

    # ==================== 安全清理操作 ====================

    def _clear_cache(self):
        reply = QMessageBox.question(
            self, "确认清除缓存",
            "确定要清除所有缓存文件吗？\n\n"
            "这将删除缓存目录中的所有临时文件。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        if self.config_manager.clear_cache():
            QMessageBox.information(self, "成功", "缓存已清除")
        else:
            QMessageBox.warning(self, "失败", "清除缓存失败")

    def _clear_all_data(self):
        reply = QMessageBox.warning(
            self, "⚠️ 确认清除所有数据",
            "此操作将删除以下所有本地数据：\n\n"
            "• API 密钥\n"
            "• 加密配置文件\n"
            "• 加密密钥\n"
            "• 所有缓存文件\n\n"
            "此操作不可撤销！确定要继续吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        result = self.config_manager.clear_all_data()
        self._refresh_api_key_status()
        self.on_api_key_saved()  # 通知主窗口重置客户端

        details = []
        if result["config_deleted"]:
            details.append("• 配置文件已删除")
        if result["key_deleted"]:
            details.append("• 加密密钥已删除")
        if result["cache_cleared"]:
            details.append("• 缓存已清除")

        QMessageBox.information(
            self, "清除完成",
            "已清除以下数据：\n\n" + "\n".join(details) + "\n\n"
            "API 密钥已从本地移除，工具已恢复为未配置状态。"
        )

    # ==================== 外部接口 ====================

    def update_api_key_warning(self, text: str, color: str):
        """由主窗口调用，更新 API 密钥状态提示"""
        self._set_api_key_hint(text, color)

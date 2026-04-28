"""
对话历史记录弹窗：展示历史列表，支持加载和删除。
"""
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QWidget, QAbstractItemView,
    QMessageBox, QLineEdit, QInputDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class ChatHistoryDialog(QDialog):
    """对话历史弹窗。"""

    def __init__(self, history_manager, parent=None):
        super().__init__(parent)
        self.history_manager = history_manager
        self.selected_id: str | None = None
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        self.setWindowTitle("对话历史")
        self.setMinimumSize(500, 400)
        self.resize(500, 450)

        layout = QVBoxLayout(self)

        # 标题栏
        title = QLabel("选择要加载的对话，或删除不需要的记录")
        title.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(title)

        # 搜索栏
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索标题或模型（实时过滤）")
        self.search_input.textChanged.connect(self._refresh_list)
        layout.addWidget(self.search_input)

        # 列表
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.itemDoubleClicked.connect(self._on_load)
        self.list_widget.itemClicked.connect(self._on_select)
        layout.addWidget(self.list_widget)

        # 底部按钮栏
        btn_layout = QHBoxLayout()

        self.load_btn = QPushButton("加载选中")
        self.load_btn.setEnabled(False)
        self.load_btn.clicked.connect(self._on_load)
        btn_layout.addWidget(self.load_btn)

        self.delete_btn = QPushButton("删除")
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet("QPushButton { color: #e53935; }")
        self.delete_btn.clicked.connect(self._on_delete)
        btn_layout.addWidget(self.delete_btn)

        self.rename_btn = QPushButton("重命名")
        self.rename_btn.setEnabled(False)
        self.rename_btn.clicked.connect(self._on_rename)
        btn_layout.addWidget(self.rename_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _refresh_list(self):
        """刷新列表。"""
        self.list_widget.clear()
        entries = self.history_manager.list_all()
        keyword = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""
        for entry in entries:
            title_str = entry.get("title", "未命名")
            model_str = entry.get("model", "")
            if keyword and keyword not in title_str.lower() and keyword not in model_str.lower():
                continue

            item = QListWidgetItem()
            item.setData(Qt.UserRole, entry["id"])

            # 格式化时间
            updated = entry.get("updated_at", "")
            try:
                dt = datetime.fromisoformat(updated)
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                time_str = updated

            msg_count = int(entry.get("message_count", 0))

            # 自定义显示文本
            item.setText(f"  {title_str}\n  ⏱ {time_str}  |  {model_str}  |  {msg_count} 条消息")
            item.setToolTip(title_str)

            self.list_widget.addItem(item)

        if not entries:
            self.list_widget.setItemWidget(
                QListWidgetItem(self.list_widget),
                QLabel("暂无保存的对话")
            )

    def _on_select(self, item):
        """选中某一项。"""
        self.selected_id = item.data(Qt.UserRole)
        self.load_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.rename_btn.setEnabled(True)

    def _on_load(self):
        """加载选中的对话。"""
        if not self.selected_id:
            return
        self.accept()

    def _on_delete(self):
        """删除选中的对话。"""
        if not self.selected_id:
            return
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除这条对话记录吗？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.history_manager.delete(self.selected_id)
            self.selected_id = None
            self.load_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.rename_btn.setEnabled(False)
            self._refresh_list()

    def _on_rename(self):
        """重命名选中的对话。"""
        if not self.selected_id:
            return
        item = self.list_widget.currentItem()
        current_title = item.toolTip().strip() if item else ""
        title, ok = QInputDialog.getText(
            self, "重命名对话", "请输入新标题：", text=current_title
        )
        new_title = title.strip() if title else ""
        if not ok or not new_title:
            return
        if not self.history_manager.rename(self.selected_id, new_title):
            QMessageBox.warning(self, "重命名失败", "无法重命名该对话，请重试。")
            return
        self._refresh_list()

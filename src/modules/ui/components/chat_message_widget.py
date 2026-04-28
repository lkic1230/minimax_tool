"""
聊天气泡组件。
"""
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
    QApplication
)
from PySide6.QtCore import Qt, QTimer


# ==================== 样式常量 ====================

_USER_BUBBLE_STYLE = """
    QWidget#userBubble {
        background-color: #dcf8c6;
        border-radius: 12px;
    }
    QWidget#userBubble QLabel {
        background-color: transparent;
        color: #1a1a1a;
    }
    QWidget#userBubble QLabel#bubbleContent {
        color: #1a1a1a;
        font-size: 13px;
    }
    QWidget#userBubble QLabel#bubbleTimestamp {
        color: #999;
        font-size: 11px;
        padding-top: 2px;
    }
"""

_ASSISTANT_BUBBLE_STYLE = """
    QWidget#assistantBubble {
        background-color: #ffffff;
        border-radius: 12px;
        border: 1px solid #e0e0e0;
    }
    QWidget#assistantBubble QLabel {
        background-color: transparent;
        color: #1a1a1a;
    }
    QWidget#assistantBubble QLabel#bubbleContent {
        color: #1a1a1a;
        font-size: 13px;
    }
    QWidget#assistantBubble QLabel#bubbleTimestamp {
        color: #999;
        font-size: 11px;
        padding-top: 2px;
    }
"""

_SYSTEM_BUBBLE_STYLE = """
    QWidget#systemBubble {
        background-color: #f0f0f0;
        border-radius: 6px;
    }
    QWidget#systemBubble QLabel {
        background-color: transparent;
        color: #1a1a1a;
    }
    QWidget#systemBubble QLabel#bubbleContent {
        color: #1a1a1a;
        font-size: 13px;
    }
    QWidget#systemBubble QLabel#bubbleTimestamp {
        color: #999;
        font-size: 11px;
        padding-top: 2px;
    }
"""

_BUBBLE_MAX_WIDTH_RATIO = 0.75


# ==================== 气泡组件 ====================

class MessageBubbleWidget(QWidget):
    """单条聊天气泡（支持 user / assistant / system 三种角色）。"""

    def __init__(self, role: str, content: str, timestamp: str = None,
                 author: str = None, parent=None):
        super().__init__(parent)
        self.role = role
        self.setObjectName(f"{role}Bubble")
        # 自定义 QWidget 需要此属性才能渲染 QSS 背景
        self.setAttribute(Qt.WA_StyledBackground, True)

        # 作者名：user 默认 "我"，assistant 需外部传入模型名
        if author:
            display_author = author
        elif role == "user":
            display_author = "我"
        else:
            display_author = ""

        # 样式
        if role == "user":
            self.setStyleSheet(_USER_BUBBLE_STYLE)
        elif role == "assistant":
            self.setStyleSheet(_ASSISTANT_BUBBLE_STYLE)
        else:
            self.setStyleSheet(_SYSTEM_BUBBLE_STYLE)

        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        # 内容标签
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        content_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        content_label.setObjectName("bubbleContent")
        layout.addWidget(content_label)

        # 底部栏：时间 · 作者
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 2, 0, 0)
        bottom_row.setSpacing(4)

        ts_text = timestamp or datetime.now().strftime("%H:%M")
        ts_label = QLabel(ts_text)
        ts_label.setObjectName("bubbleTimestamp")
        bottom_row.addWidget(ts_label)

        if display_author:
            sep_label = QLabel("·")
            sep_label.setObjectName("bubbleTimestamp")
            bottom_row.addWidget(sep_label)

            author_label = QLabel(display_author)
            author_label.setObjectName("bubbleTimestamp")
            bottom_row.addWidget(author_label)

        # user 靠右，assistant 靠左
        if role == "user":
            bottom_row.addStretch()
        else:
            bottom_row.insertStretch(0)

        layout.addLayout(bottom_row)

        # 气泡宽度约束
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self._apply_max_width()

    def _apply_max_width(self):
        """限制气泡最大宽度为父容器宽度的 75%。"""
        parent_widget = self.parentWidget()
        if parent_widget:
            max_w = int(parent_widget.width() * _BUBBLE_MAX_WIDTH_RATIO)
            self.setMaximumWidth(max(max_w, 200))
        else:
            self.setMaximumWidth(600)

    def resizeEvent(self, event):
        """父容器 resize 时更新最大宽度。"""
        super().resizeEvent(event)
        self._apply_max_width()


# ==================== 消息包裹器（控制对齐） ====================

def create_message_row(bubble: MessageBubbleWidget) -> QWidget:
    """
    创建一条消息的行容器。
    - user: 气泡靠右
    - assistant: 气泡靠左
    - system: 气泡居中
    """
    row = QWidget()
    row.setObjectName("messageRow")
    row.setAttribute(Qt.WA_StyledBackground, True)
    row.setStyleSheet("QWidget#messageRow { background-color: transparent; }")
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(8, 2, 8, 2)
    row_layout.setSpacing(0)

    if bubble.role == "user":
        row_layout.addStretch()
        row_layout.addWidget(bubble)
        # 右侧留一点边距
        spacer = QWidget()
        spacer.setFixedWidth(8)
        row_layout.addWidget(spacer)
    elif bubble.role == "assistant":
        spacer = QWidget()
        spacer.setFixedWidth(8)
        row_layout.addWidget(spacer)
        row_layout.addWidget(bubble)
        row_layout.addStretch()
    else:
        row_layout.addStretch()
        row_layout.addWidget(bubble)
        row_layout.addStretch()

    return row

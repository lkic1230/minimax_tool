"""
聊天气泡组件（支持 Markdown 渲染 + 双模式复制）。
"""
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
    QTextEdit, QMenu, QApplication
)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QCursor


# ==================== 样式常量 ====================

_USER_BUBBLE_STYLE = """
    QWidget#userBubble {
        background-color: #dcf8c6;
        border-radius: 12px;
    }
    QWidget#userBubble QTextEdit {
        background-color: transparent;
        color: #1a1a1a;
        border: none;
        padding: 0;
    }
    QWidget#userBubble QLabel {
        background-color: transparent;
        color: #1a1a1a;
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
    QWidget#assistantBubble QTextEdit {
        background-color: transparent;
        color: #1a1a1a;
        border: none;
        padding: 0;
    }
    QWidget#assistantBubble QLabel {
        background-color: transparent;
        color: #1a1a1a;
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
    QWidget#systemBubble QTextEdit {
        background-color: transparent;
        color: #1a1a1a;
        border: none;
        padding: 0;
    }
    QWidget#systemBubble QLabel {
        background-color: transparent;
        color: #1a1a1a;
    }
    QWidget#systemBubble QLabel#bubbleTimestamp {
        color: #999;
        font-size: 11px;
        padding-top: 2px;
    }
"""

_BUBBLE_MAX_WIDTH_RATIO = 0.86


# ==================== Markdown 内容编辑框（只读 + 双模式复制） ====================

def _resolve_markdown_copy_payload(
    copy_raw: bool,
    raw_content: str,
    selected_text: str,
    plain_text: str,
) -> str:
    """根据复制模式返回应写入剪贴板的内容。"""
    if copy_raw:
        return raw_content
    if selected_text:
        # QTextCursor 选中文本中的换行会变为 U+2029，需要转换回常规换行。
        return selected_text.replace("\u2029", "\n")
    return plain_text


from PySide6.QtWidgets import QTextEdit, QTextBrowser, QWidget
from PySide6.QtGui import QFont, QTextCursor, QMouseEvent


class _MarkdownTextEdit(QTextBrowser):
    """
    只读文本编辑框，支持 Markdown 渲染和双模式复制。
    继承 QTextBrowser 以支持链接点击。
    - assistant/system: 渲染 Markdown 显示，复制时可选原文/纯文本
    - user: 纯文本显示，直接复制
    """

    def __init__(self, raw_content: str, is_markdown: bool = False, parent=None):
        super().__init__(parent)
        self._raw_content = raw_content
        self._is_markdown = is_markdown

        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        self.setOpenExternalLinks(True)  # 允许点击外部链接
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.setFrameShape(QTextEdit.NoFrame)
        self.setStyleSheet(
            "QTextEdit { background-color: transparent; border: none; padding: 0; }"
            "QTextEdit QScrollBar { width: 0; height: 0; }"
        )
        self.document().setDocumentMargin(0)

        if is_markdown:
            self.setMarkdown(raw_content)
        else:
            # 将 URL 转为蓝色可点击链接
            html_content = self._make_linkable(raw_content)
            self.setHtml(html_content)
        self._update_height()

    def _make_linkable(self, text: str) -> str:
        """将 URL 转为蓝色可点击链接"""
        import re
        url_pattern = re.compile(r'(https?://[^\s\<\>\"\'\)]+)')
        # 给链接添加蓝色样式
        return url_pattern.sub(r'<a href="\1" style="color:#1976d2;text-decoration:underline;">\1</a>', text)

    def _update_height(self):
        """根据文档内容与当前宽度动态更新高度，避免短文本气泡过高。"""
        viewport_w = max(self.viewport().width(), 1)
        self.document().setTextWidth(viewport_w)
        doc_h = int(self.document().size().height())
        min_h = self.fontMetrics().height()
        self.setFixedHeight(max(doc_h, min_h) + 2)

    def preferred_width(self, min_width: int, max_width: int) -> int:
        """根据文本内容估算更合理的显示宽度。"""
        plain = (self.toPlainText() or "").replace("\t", "    ")
        lines = plain.splitlines() or [plain]
        fm = self.fontMetrics()
        longest = 0
        for line in lines:
            # 对极长单行进行上限截断，避免异常字符串导致宽度估算过大。
            sample = line[:240]
            longest = max(longest, fm.horizontalAdvance(sample))
        estimated = longest + 24
        return max(min_width, min(max_width, estimated))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_height()

    def wheelEvent(self, event):
        """禁用气泡内部滚轮滚动，交由外层消息区域处理。"""
        event.ignore()

    def contextMenuEvent(self, event):
        """自定义右键菜单，提供双模式复制。"""
        menu = QMenu(self)

        if self._is_markdown:
            copy_raw_action = menu.addAction("复制 Markdown 原文")
            copy_text_action = menu.addAction("复制纯文本")
            action = menu.exec(QCursor.pos())
            if action == copy_raw_action:
                payload = _resolve_markdown_copy_payload(
                    copy_raw=True,
                    raw_content=self._raw_content,
                    selected_text=self.textCursor().selectedText(),
                    plain_text=self.toPlainText(),
                )
                QApplication.clipboard().setText(payload)
            elif action == copy_text_action:
                payload = _resolve_markdown_copy_payload(
                    copy_raw=False,
                    raw_content=self._raw_content,
                    selected_text=self.textCursor().selectedText(),
                    plain_text=self.toPlainText(),
                )
                QApplication.clipboard().setText(payload)
        else:
            # 纯文本：使用标准菜单
            menu = self.createStandardContextMenu()
            menu.exec(QCursor.pos())


# ==================== 气泡组件 ====================

class MessageBubbleWidget(QWidget):
    """单条聊天气泡（支持 user / assistant / system 三种角色）。"""

    def __init__(self, role: str, content: str, timestamp: str = None,
                 author: str = None, parent=None):
        super().__init__(parent)
        self.role = role
        self.setObjectName(f"{role}Bubble")
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

        # 内容编辑框（Markdown 或纯文本）
        is_markdown = (role in ("assistant", "system"))
        self._content_edit = _MarkdownTextEdit(content, is_markdown=is_markdown)
        self._content_edit.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self._content_edit.setObjectName("bubbleContent")
        layout.addWidget(self._content_edit)

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
        self._observed_parent = None
        self._apply_max_width()

    def _bind_parent_resize_event(self):
        parent_widget = self.parentWidget()
        if self._observed_parent is parent_widget:
            return
        if self._observed_parent:
            self._observed_parent.removeEventFilter(self)
        self._observed_parent = parent_widget
        if self._observed_parent:
            self._observed_parent.installEventFilter(self)

    def _apply_max_width(self):
        """限制气泡最大宽度为父容器宽度的比例并随窗口变化自适应。"""
        self._bind_parent_resize_event()
        parent_widget = self.parentWidget()
        if parent_widget:
            max_w = int(parent_widget.width() * _BUBBLE_MAX_WIDTH_RATIO)
            self.setMaximumWidth(max(max_w, 260))
        else:
            self.setMaximumWidth(760)
        if hasattr(self, "_content_edit"):
            content_max = max(self.maximumWidth() - 20, 120)
            preferred = self._content_edit.preferred_width(min_width=120, max_width=content_max)
            self._content_edit.setFixedWidth(preferred)

    def resizeEvent(self, event):
        """自身尺寸变化时更新最大宽度。"""
        super().resizeEvent(event)
        self._apply_max_width()

    def eventFilter(self, watched, event):
        """监听父容器变化，保证窗口调整大小时气泡宽度及时更新。"""
        if watched is self._observed_parent and event.type() in (QEvent.Resize, QEvent.Show):
            self._apply_max_width()
        return super().eventFilter(watched, event)


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

    # 绑定到行容器后再计算一次宽度，避免初次创建时父级尚未就绪导致宽度偏窄。
    bubble._apply_max_width()

    return row

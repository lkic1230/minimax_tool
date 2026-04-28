"""
图像生成 Tab 组件（self-contained Widget）。
"""
import os
from typing import Callable, Any, Optional

from PySide6.QtCore import Qt, QEvent, QTimer, QPoint, QRectF, Signal
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QComboBox,
    QSpinBox, QCheckBox, QLineEdit, QLabel, QPushButton, QTextEdit, QTabWidget,
    QScrollArea, QSlider, QSizePolicy, QFileDialog, QMessageBox
)

from ..components.common import GenerationThread
from ...core.constants import IMAGE_MODELS, IMAGE_ASPECT_RATIOS, IMAGE_STYLES


class MiniMapWidget(QWidget):
    """图像预览小地图：显示整图和当前可视区域，并支持点击跳转。"""

    navigateRequested = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(180, 120)
        self._pixmap: Optional[QPixmap] = None
        self._image_rect = QRectF()
        self._view_rect = QRectF()

    def update_state(
        self,
        pixmap: Optional[QPixmap],
        content_width: int,
        content_height: int,
        viewport_width: int,
        viewport_height: int,
        scroll_x: int,
        scroll_y: int,
    ):
        self._pixmap = pixmap
        if not pixmap or pixmap.isNull() or content_width <= 0 or content_height <= 0:
            self._image_rect = QRectF()
            self._view_rect = QRectF()
            self.hide()
            self.update()
            return

        margin = 6.0
        avail_w = max(1.0, self.width() - margin * 2)
        avail_h = max(1.0, self.height() - margin * 2)
        scale = min(avail_w / content_width, avail_h / content_height)
        draw_w = max(1.0, content_width * scale)
        draw_h = max(1.0, content_height * scale)
        draw_x = (self.width() - draw_w) / 2.0
        draw_y = (self.height() - draw_h) / 2.0
        self._image_rect = QRectF(draw_x, draw_y, draw_w, draw_h)

        view_w = min(content_width, max(1, viewport_width))
        view_h = min(content_height, max(1, viewport_height))
        view_x = min(max(0, scroll_x), max(0, content_width - view_w))
        view_y = min(max(0, scroll_y), max(0, content_height - view_h))
        self._view_rect = QRectF(
            draw_x + (view_x / content_width) * draw_w,
            draw_y + (view_y / content_height) * draw_h,
            max(1.0, (view_w / content_width) * draw_w),
            max(1.0, (view_h / content_height) * draw_h),
        )
        self.show()
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(32, 32, 32, 200))

        if not self._pixmap or self._pixmap.isNull() or self._image_rect.isEmpty():
            painter.setPen(QColor(120, 120, 120))
            painter.drawText(self.rect(), Qt.AlignCenter, "小地图")
            return

        painter.drawPixmap(self._image_rect, self._pixmap, QRectF(self._pixmap.rect()))
        painter.setPen(QPen(QColor(220, 220, 220), 1))
        painter.drawRect(self._image_rect)
        painter.setPen(QPen(QColor(76, 175, 80), 2))
        painter.drawRect(self._view_rect)

    def mousePressEvent(self, event):
        if self._image_rect.isEmpty():
            return
        x = event.position().x()
        y = event.position().y()
        if not self._image_rect.contains(x, y):
            return
        nx = (x - self._image_rect.left()) / self._image_rect.width()
        ny = (y - self._image_rect.top()) / self._image_rect.height()
        self.navigateRequested.emit(float(nx), float(ny))


class ImageTabWidget(QWidget):
    """图像生成 Tab（self-contained）"""

    def __init__(
        self,
        client_getter: Callable[[], Any],
        check_client_func: Callable[[], bool],
        parent=None
    ):
        super().__init__(parent)
        self.client_getter = client_getter
        self.check_client_func = check_client_func
        self.generation_thread = None
        self._drag_start: Optional[QPoint] = None
        self._original_preview_pixmap: Optional[QPixmap] = None
        self._pending_scale_value = 100
        self._last_applied_scale_value = 100
        self._zoom_anchor_original: Optional[tuple[float, float]] = None
        self._zoom_anchor_viewport: Optional[QPoint] = None
        self._scale_timer = QTimer(self)
        self._scale_timer.setSingleShot(True)
        self._scale_timer.timeout.connect(self._apply_pending_scale)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        left_scroll = self._create_left_scroll()
        right_widget = self._create_right_panel()
        layout.addWidget(left_scroll, 1)
        layout.addWidget(right_widget, 2)

    def _create_left_scroll(self) -> QScrollArea:
        left_widget = self._create_left_panel()
        left_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setWidget(left_widget)
        return left_scroll

    def _create_left_panel(self) -> QWidget:
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(self._create_mode_group())
        left_layout.addWidget(self._create_params_group())
        left_layout.addWidget(self._create_generate_button())
        left_layout.addWidget(self._create_status_label())
        left_layout.addWidget(self._create_path_label())
        left_layout.addWidget(self._create_open_path_button())
        left_layout.addWidget(self._create_open_output_button())
        left_layout.addStretch()
        return left_widget

    def _create_mode_group(self) -> QGroupBox:
        self.image_mode_group = QGroupBox("生成模式")
        mode_layout = QVBoxLayout()
        self.image_mode_tabs = QTabWidget()
        self.image_mode_tabs.addTab(self._create_t2i_panel(), "📝 文生图")
        self.image_mode_tabs.addTab(self._create_i2i_panel(), "🖼️ 图生图")
        self.image_mode_tabs.currentChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.image_mode_tabs)
        self.image_mode_group.setLayout(mode_layout)
        self._on_mode_changed(self.image_mode_tabs.currentIndex())
        return self.image_mode_group

    def _create_params_group(self) -> QGroupBox:
        params_group = QGroupBox("参数设置")
        params_layout = QFormLayout()

        self.image_model = QComboBox()
        self.image_model.addItems(IMAGE_MODELS)
        params_layout.addRow("模型:", self.image_model)

        self.image_count = QSpinBox()
        self.image_count.setRange(1, 9)
        self.image_count.setValue(1)
        params_layout.addRow("数量:", self.image_count)

        self.image_ratio = QComboBox()
        self.image_ratio.addItems(IMAGE_ASPECT_RATIOS)
        params_layout.addRow("宽高比:", self.image_ratio)

        self.image_style = QComboBox()
        self.image_style.addItems(IMAGE_STYLES)
        params_layout.addRow("画风:", self.image_style)

        self.image_watermark = QCheckBox("添加水印")
        params_layout.addRow("水印:", self.image_watermark)

        seed_layout = QHBoxLayout()
        self.image_seed = QLineEdit()
        self.image_seed.setPlaceholderText("留空使用随机种子")
        seed_layout.addWidget(self.image_seed)
        seed_layout.addWidget(QLabel("  留空则随机"))
        params_layout.addRow("种子:", seed_layout)

        params_group.setLayout(params_layout)
        return params_group

    def _create_generate_button(self) -> QPushButton:
        self.image_generate_btn = QPushButton("🖼️ 生成图像")
        self.image_generate_btn.clicked.connect(self.generate_image)
        return self.image_generate_btn

    def _create_status_label(self) -> QLabel:
        self.image_status = QLabel("")
        self.image_status.setAlignment(Qt.AlignCenter)
        return self.image_status

    def _create_path_label(self) -> QLabel:
        self.image_path = QLabel("")
        self.image_path.setWordWrap(True)
        self.image_path.setStyleSheet("color: #888; font-size: 12px;")
        return self.image_path

    def _create_open_path_button(self) -> QPushButton:
        self.image_open_path_btn = QPushButton("📂 打开保存路径")
        self.image_open_path_btn.clicked.connect(self._open_image_path)
        self.image_open_path_btn.setEnabled(False)
        return self.image_open_path_btn

    def _create_open_output_button(self) -> QPushButton:
        open_output_btn = QPushButton("📂 打开输出文件夹")
        open_output_btn.clicked.connect(self._open_output_dir)
        return open_output_btn

    def _create_right_panel(self) -> QWidget:
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addLayout(self._create_scale_layout())
        right_layout.addWidget(self._create_preview_container(), 1)
        mini_row = QHBoxLayout()
        mini_row.addStretch()
        mini_row.addWidget(self._create_minimap_widget())
        right_layout.addLayout(mini_row)
        right_layout.addWidget(self._create_info_label())
        return right_widget

    def _create_scale_layout(self) -> QHBoxLayout:
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("缩放:"))
        self.image_scale_slider = QSlider(Qt.Horizontal)
        self.image_scale_slider.setRange(10, 400)
        self.image_scale_slider.setValue(100)
        self.image_scale_slider.setTickPosition(QSlider.TicksBelow)
        self.image_scale_slider.setTickInterval(50)
        self.image_scale_slider.setMaximumWidth(200)
        self.image_scale_slider.valueChanged.connect(self._on_scale_changed)
        scale_layout.addWidget(self.image_scale_slider)
        self.image_scale_label = QLabel("100%")
        scale_layout.addWidget(self.image_scale_label)
        scale_layout.addStretch()

        fit_btn = QPushButton("自适应")
        fit_btn.clicked.connect(self._fit_image)
        scale_layout.addWidget(fit_btn)
        return scale_layout

    def _create_preview_container(self) -> QScrollArea:
        self.image_preview_container = QScrollArea()
        self.image_preview_container.setWidgetResizable(False)
        self.image_preview_container.setAlignment(Qt.AlignCenter)
        self.image_preview_container.setMinimumSize(400, 300)
        self.image_preview_container.setStyleSheet("border: 1px solid #555; background: #2a2a2a;")

        self.image_preview_label = QLabel()
        self.image_preview_label.setAlignment(Qt.AlignCenter)
        self.image_preview_label.setText("生成的图片将显示在这里\n\n支持鼠标滚轮缩放，拖拽移动图片")
        self.image_preview_label.setStyleSheet("color: #666; font-size: 14px;")
        self.image_preview_label.setMinimumSize(400, 300)
        self.image_preview_label.setCursor(Qt.OpenHandCursor)
        self.image_preview_label.installEventFilter(self)
        self.image_preview_container.viewport().installEventFilter(self)
        self.image_preview_container.horizontalScrollBar().valueChanged.connect(self._update_minimap)
        self.image_preview_container.verticalScrollBar().valueChanged.connect(self._update_minimap)

        self.image_preview_container.setWidget(self.image_preview_label)
        return self.image_preview_container

    def _create_minimap_widget(self) -> QWidget:
        self.image_minimap = MiniMapWidget(self)
        self.image_minimap.setToolTip("小地图：点击可跳转到对应区域")
        self.image_minimap.navigateRequested.connect(self._on_minimap_navigate)
        self.image_minimap.hide()
        return self.image_minimap

    def _create_info_label(self) -> QLabel:
        self.image_info = QLabel("")
        self.image_info.setStyleSheet("color: #4caf50; font-size: 12px;")
        return self.image_info

    # ==================== 子面板构建 ====================

    def _create_t2i_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("图像描述:"))
        self.image_prompt = QTextEdit()
        self.image_prompt.setPlaceholderText("描述你想要的图像内容...")
        self.image_prompt.setMaximumHeight(80)
        layout.addWidget(self.image_prompt)
        return panel

    def _create_i2i_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)

        layout.addWidget(QLabel("参考图片（保持主体特征）:"))
        ref_group = QGroupBox("上传参考图")
        ref_layout = QVBoxLayout()

        ref_path_layout = QHBoxLayout()
        self.image_ref_path = QLineEdit()
        self.image_ref_path.setReadOnly(True)
        self.image_ref_path.setPlaceholderText("选择参考图片（支持 JPG/PNG/WebP）")
        ref_path_layout.addWidget(self.image_ref_path)

        select_ref_btn = QPushButton("📷 选择图片")
        select_ref_btn.clicked.connect(self._select_image_ref)
        ref_path_layout.addWidget(select_ref_btn)
        ref_layout.addLayout(ref_path_layout)

        self.image_ref_preview = QLabel("")
        self.image_ref_preview.setAlignment(Qt.AlignCenter)
        self.image_ref_preview.setMaximumHeight(100)
        self.image_ref_preview.setStyleSheet("border: 1px solid #555; background: #2a2a2a;")
        ref_layout.addWidget(self.image_ref_preview)

        ref_group.setLayout(ref_layout)
        layout.addWidget(ref_group)

        layout.addWidget(QLabel("图像描述:"))
        self.image_prompt_ref = QTextEdit()
        self.image_prompt_ref.setPlaceholderText("描述你想要的新图片内容...")
        self.image_prompt_ref.setMaximumHeight(80)
        layout.addWidget(self.image_prompt_ref)

        return panel

    # ==================== 事件处理 ====================

    def eventFilter(self, obj, event):
        """图片拖拽/滚轮事件过滤器"""
        if obj == self.image_preview_container.viewport() and event.type() == QEvent.Resize:
            self._update_minimap()
            return False
        if obj == self.image_preview_label:
            if event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    self._drag_start = event.position().toPoint()
                    self.image_preview_label.setCursor(Qt.ClosedHandCursor)
                return True
            if event.type() == QEvent.MouseMove:
                if self._drag_start is not None and (event.buttons() & Qt.LeftButton):
                    delta = event.position().toPoint() - self._drag_start
                    hbar = self.image_preview_container.horizontalScrollBar()
                    vbar = self.image_preview_container.verticalScrollBar()
                    hbar.setValue(hbar.value() - delta.x())
                    vbar.setValue(vbar.value() - delta.y())
                    self._drag_start = event.position().toPoint()
                return True
            if event.type() == QEvent.MouseButtonRelease:
                if event.button() == Qt.LeftButton:
                    self._drag_start = None
                    self.image_preview_label.setCursor(Qt.OpenHandCursor)
                return True
            if event.type() == QEvent.Wheel:
                delta = event.angleDelta().y()
                if self._original_preview_pixmap and not self._original_preview_pixmap.isNull():
                    viewport = self.image_preview_container.viewport()
                    cursor_vp = viewport.mapFromGlobal(event.globalPosition().toPoint())
                    hbar = self.image_preview_container.horizontalScrollBar()
                    vbar = self.image_preview_container.verticalScrollBar()
                    old_factor = max(0.1, self._last_applied_scale_value / 100.0)
                    self._zoom_anchor_original = (
                        (hbar.value() + cursor_vp.x()) / old_factor,
                        (vbar.value() + cursor_vp.y()) / old_factor,
                    )
                    self._zoom_anchor_viewport = cursor_vp

                step = 20
                if event.modifiers() & Qt.ControlModifier:
                    step = 10
                if event.modifiers() & Qt.ShiftModifier:
                    step = 40
                if delta > 0:
                    self.image_scale_slider.setValue(self.image_scale_slider.value() + step)
                else:
                    self.image_scale_slider.setValue(self.image_scale_slider.value() - step)
                return True
            if event.type() == QEvent.MouseButtonDblClick:
                self._fit_image()
                return True
        return super().eventFilter(obj, event)

    def _on_mode_changed(self, _index):
        current_panel = self.image_mode_tabs.currentWidget()
        if not current_panel:
            return
        panel_hint = current_panel.sizeHint().height()
        tab_bar_hint = self.image_mode_tabs.tabBar().sizeHint().height()
        margins = self.image_mode_group.layout().contentsMargins()
        tabs_height = panel_hint + tab_bar_hint + 12
        group_height = tabs_height + margins.top() + margins.bottom()
        self.image_mode_tabs.setMaximumHeight(tabs_height)
        self.image_mode_group.setMaximumHeight(group_height)
        self.image_mode_tabs.updateGeometry()
        self.image_mode_group.updateGeometry()

    def _on_scale_changed(self, value):
        self.image_scale_label.setText(f"{value}%")
        if self._original_preview_pixmap and not self._original_preview_pixmap.isNull():
            if self._zoom_anchor_original is None:
                viewport = self.image_preview_container.viewport()
                center_x = viewport.width() // 2
                center_y = viewport.height() // 2
                hbar = self.image_preview_container.horizontalScrollBar()
                vbar = self.image_preview_container.verticalScrollBar()
                old_factor = max(0.1, self._last_applied_scale_value / 100.0)
                self._zoom_anchor_original = (
                    (hbar.value() + center_x) / old_factor,
                    (vbar.value() + center_y) / old_factor,
                )
                self._zoom_anchor_viewport = QPoint(center_x, center_y)
        self._pending_scale_value = value
        # 合并短时间内的高频缩放事件，降低卡顿
        self._scale_timer.start(16)

    def _apply_pending_scale(self):
        if not self._original_preview_pixmap or self._original_preview_pixmap.isNull():
            return
        self._render_preview_at_scale(self._pending_scale_value)

    def _render_preview_at_scale(self, scale_value: int):
        if not self._original_preview_pixmap or self._original_preview_pixmap.isNull():
            return
        factor = max(0.1, scale_value / 100.0)
        source_size = self._original_preview_pixmap.size()
        target_size = source_size * factor
        scaled = self._original_preview_pixmap.scaled(
            target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.image_preview_label.setPixmap(scaled)
        self.image_preview_label.adjustSize()
        hbar = self.image_preview_container.horizontalScrollBar()
        vbar = self.image_preview_container.verticalScrollBar()
        if self._zoom_anchor_original and self._zoom_anchor_viewport:
            orig_x, orig_y = self._zoom_anchor_original
            vp = self._zoom_anchor_viewport
            hbar.setValue(int(orig_x * factor - vp.x()))
            vbar.setValue(int(orig_y * factor - vp.y()))
        self._last_applied_scale_value = scale_value
        self._zoom_anchor_original = None
        self._zoom_anchor_viewport = None
        self._update_minimap()

    def _on_minimap_navigate(self, nx: float, ny: float):
        if not self.image_preview_label.pixmap():
            return
        pix = self.image_preview_label.pixmap()
        if not pix:
            return
        content_w = max(1, pix.width())
        content_h = max(1, pix.height())
        viewport = self.image_preview_container.viewport().size()
        hbar = self.image_preview_container.horizontalScrollBar()
        vbar = self.image_preview_container.verticalScrollBar()
        target_x = int(nx * content_w - viewport.width() / 2)
        target_y = int(ny * content_h - viewport.height() / 2)
        hbar.setValue(max(hbar.minimum(), min(hbar.maximum(), target_x)))
        vbar.setValue(max(vbar.minimum(), min(vbar.maximum(), target_y)))
        self._update_minimap()

    def _update_minimap(self):
        if not hasattr(self, "image_minimap"):
            return
        if not self._original_preview_pixmap or self._original_preview_pixmap.isNull():
            self.image_minimap.update_state(None, 0, 0, 0, 0, 0, 0)
            return
        displayed = self.image_preview_label.pixmap()
        if not displayed:
            self.image_minimap.update_state(None, 0, 0, 0, 0, 0, 0)
            return
        viewport = self.image_preview_container.viewport().size()
        hbar = self.image_preview_container.horizontalScrollBar()
        vbar = self.image_preview_container.verticalScrollBar()
        self.image_minimap.update_state(
            pixmap=self._original_preview_pixmap,
            content_width=max(1, displayed.width()),
            content_height=max(1, displayed.height()),
            viewport_width=viewport.width(),
            viewport_height=viewport.height(),
            scroll_x=hbar.value(),
            scroll_y=vbar.value(),
        )

    def _fit_image(self):
        if not self._original_preview_pixmap or self._original_preview_pixmap.isNull():
            self.image_scale_slider.setValue(100)
            return
        viewport_size = self.image_preview_container.viewport().size()
        src_size = self._original_preview_pixmap.size()
        if src_size.width() <= 0 or src_size.height() <= 0:
            self.image_scale_slider.setValue(100)
            return
        fit_ratio = min(
            viewport_size.width() / src_size.width(),
            viewport_size.height() / src_size.height(),
        )
        fit_percent = int(round(fit_ratio * 100))
        fit_percent = max(self.image_scale_slider.minimum(), min(self.image_scale_slider.maximum(), fit_percent))
        prev_value = self.image_scale_slider.value()
        self.image_scale_slider.setValue(fit_percent)
        # 若数值未变化，valueChanged 不会触发，需手动刷新新图渲染
        if prev_value == fit_percent:
            self._pending_scale_value = fit_percent
            self._apply_pending_scale()

    def _select_image_ref(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择参考图片", "", "图片文件 (*.png *.jpg *.jpeg *.webp)"
        )
        if filepath:
            self.image_ref_path.setText(filepath)
            pixmap = QPixmap(filepath).scaled(200, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_ref_preview.setPixmap(pixmap)

    def _open_image_path(self):
        path = self.image_path.text()
        if path and os.path.exists(path):
            os.startfile(os.path.dirname(path))

    def _open_output_dir(self):
        client = self.client_getter()
        if client:
            output_dir = str(client.output_dir)
            if os.path.isdir(output_dir):
                os.startfile(output_dir)
                return
        QMessageBox.warning(self, "提示", "无法获取输出目录，请先在「配置」页面设置 API 密钥")

    def _update_preview(self, filepath):
        if os.path.exists(filepath):
            pixmap = QPixmap(filepath)
            if not pixmap.isNull():
                self._original_preview_pixmap = pixmap
                self._zoom_anchor_original = None
                self._zoom_anchor_viewport = None
                # 新图默认执行一次自适应，避免只显示局部
                self._fit_image()
                self.image_info.setText(f"文件名: {os.path.basename(filepath)}")
                self.image_path.setText(filepath)
                self.image_open_path_btn.setEnabled(True)

    # ==================== 参数映射 ====================

    def _get_style(self):
        style_text = self.image_style.currentText()
        if style_text == "无" or not style_text:
            return None
        style_type = {"漫画": "漫画", "元气": "元气", "中世纪": "中世纪", "水彩": "水彩"}.get(style_text)
        if style_type:
            return {"style_type": style_type, "style_weight": 0.8}
        return None

    # ==================== 生成逻辑 ====================

    def generate_image(self):
        import base64

        if not self.check_client_func():
            return

        if self.image_mode_tabs.currentIndex() == 0:
            prompt = self.image_prompt.toPlainText().strip()
            if not prompt:
                QMessageBox.warning(self, "警告", "请输入图像描述")
                return
            subject_reference = None
        else:
            prompt = self.image_prompt_ref.toPlainText().strip()
            ref_path = self.image_ref_path.text().strip()
            if not ref_path:
                QMessageBox.warning(self, "警告", "请先选择参考图片")
                return
            with open(ref_path, "rb") as f:
                img_base64 = base64.b64encode(f.read()).decode()
            subject_reference = [{"type": "character", "image_file": img_base64}]

        self.image_generate_btn.setEnabled(False)
        self.image_status.setText("正在生成...")

        style = self._get_style()
        watermark = self.image_watermark.isChecked()
        seed_text = self.image_seed.text().strip()
        seed = int(seed_text) if seed_text.isdigit() else None

        def do_generate():
            client = self.client_getter()
            return client.generate_image(
                prompt=prompt,
                model=self.image_model.currentText(),
                n=self.image_count.value(),
                aspect_ratio=self.image_ratio.currentText(),
                style=style,
                subject_reference=subject_reference,
                seed=seed,
                watermark=watermark,
            )

        self.generation_thread = GenerationThread(do_generate)
        self.generation_thread.finished.connect(self._on_finished)
        self.generation_thread.error.connect(self._on_error)
        self.generation_thread.start()

    def _on_finished(self, result):
        self.image_generate_btn.setEnabled(True)
        saved_paths = result.get("saved_paths", [])
        if saved_paths:
            self.image_status.setText(f"✓ 生成成功 ({len(saved_paths)} 张)")
            last_path = saved_paths[-1]
            self._update_preview(last_path)
            self.image_path.setText(last_path)
        else:
            self.image_status.setText("✗ 生成失败")

    def _on_error(self, error_msg: str):
        self.image_generate_btn.setEnabled(True)
        self.image_status.setText("✗ 生成失败")
        QMessageBox.critical(self, "错误", f"图像生成失败: {error_msg}")

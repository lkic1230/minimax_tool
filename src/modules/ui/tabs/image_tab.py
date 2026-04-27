"""
图像生成 Tab 组件（self-contained Widget）。
"""
import os
from typing import Callable, Any

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QComboBox,
    QSpinBox, QCheckBox, QLineEdit, QLabel, QPushButton, QTextEdit, QTabWidget,
    QScrollArea, QSlider, QSizePolicy, QFileDialog, QMessageBox
)

from ..components.common import GenerationThread


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
        self._drag_start = None
        self._drag_pos = None
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
        self.image_model.addItems(["image-01", "image-01-live"])
        params_layout.addRow("模型:", self.image_model)

        self.image_count = QSpinBox()
        self.image_count.setRange(1, 9)
        self.image_count.setValue(1)
        params_layout.addRow("数量:", self.image_count)

        self.image_ratio = QComboBox()
        self.image_ratio.addItems(["1:1", "16:9", "4:3", "3:2", "2:3", "3:4", "9:16", "21:9"])
        params_layout.addRow("宽高比:", self.image_ratio)

        self.image_style = QComboBox()
        self.image_style.addItems(["无", "漫画", "元气", "中世纪", "水彩"])
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
        right_layout.addWidget(self._create_preview_container())
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
        self.image_preview_container.setWidgetResizable(True)
        self.image_preview_container.setAlignment(Qt.AlignCenter)
        self.image_preview_container.setMinimumSize(400, 300)
        self.image_preview_container.setStyleSheet("border: 1px solid #555; background: #2a2a2a;")

        self.image_preview_label = QLabel()
        self.image_preview_label.setAlignment(Qt.AlignCenter)
        self.image_preview_label.setText("生成的图片将显示在这里\n\n支持鼠标滚轮缩放，拖拽移动图片")
        self.image_preview_label.setStyleSheet("color: #666; font-size: 14px;")
        self.image_preview_label.setMinimumSize(400, 300)
        self.image_preview_label.installEventFilter(self)

        self.image_preview_container.setWidget(self.image_preview_label)
        return self.image_preview_container

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
        if obj == self.image_preview_label:
            if event.type() == QEvent.MouseButtonPress:
                self._drag_start = event.pos()
                self._drag_pos = self.image_preview_label.pos()
                return True
            if event.type() == QEvent.MouseMove:
                if self._drag_start is not None:
                    delta = event.pos() - self._drag_start
                    new_pos = self._drag_pos + delta
                    container = self.image_preview_container
                    label = self.image_preview_label
                    max_x = (container.width() - label.width()) // 2 + 50
                    max_y = (container.height() - label.height()) // 2 + 50
                    new_pos.setX(max(-max_x, min(max_x, new_pos.x())))
                    new_pos.setY(max(-max_y, min(max_y, new_pos.y())))
                    label.move(new_pos)
                return True
            if event.type() == QEvent.Wheel:
                delta = event.angleDelta().y()
                if delta > 0:
                    self.image_scale_slider.setValue(self.image_scale_slider.value() + 20)
                else:
                    self.image_scale_slider.setValue(self.image_scale_slider.value() - 20)
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
        pixmap = self.image_preview_label.pixmap()
        if pixmap:
            scaled = pixmap.scaled(
                pixmap.size() * value / 100, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.image_preview_label.setPixmap(scaled)

    def _fit_image(self):
        self.image_scale_slider.setValue(100)

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
                scale = self.image_scale_slider.value()
                scaled = pixmap.scaled(
                    pixmap.size() * scale / 100, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.image_preview_label.setPixmap(scaled)
                self.image_preview_label.adjustSize()
                self.image_preview_label.move(0, 0)
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

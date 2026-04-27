"""
视频生成 Tab 组件（self-contained Widget）。
"""
from typing import Callable, Any

from PySide6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QTextEdit,
    QGroupBox, QLineEdit, QPushButton, QFormLayout, QProgressBar,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QTimer

from ..components.common import GenerationThread


class VideoTabWidget(QScrollArea):
    """视频生成 Tab（self-contained）"""

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
        self.video_task_id = ""
        self.video_querying = False

        self.video_poll_timer = QTimer(self)
        self.video_poll_timer.setInterval(4000)
        self.video_poll_timer.timeout.connect(self._query_video_auto)

        self._build_ui()

    def _build_ui(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_mode_selector())
        layout.addWidget(self._create_prompt_label())
        layout.addWidget(self._create_prompt_input())
        layout.addWidget(self._create_image_group())
        layout.addWidget(self._create_params_group())
        layout.addLayout(self._create_action_layout())
        layout.addWidget(self._create_status_label())
        layout.addWidget(self._create_loading_bar())
        layout.addStretch()

        layout.setAlignment(Qt.AlignTop)
        self.setWidget(widget)
        self.setWidgetResizable(True)

        self._on_mode_changed(0)

    def _create_mode_selector(self) -> QComboBox:
        self.video_mode = QComboBox()
        self.video_mode.addItems(["文生视频", "图生视频"])
        self.video_mode.currentIndexChanged.connect(self._on_mode_changed)
        return self.video_mode

    def _create_prompt_label(self) -> QLabel:
        self.video_prompt_label = QLabel("视频描述:")
        return self.video_prompt_label

    def _create_prompt_input(self) -> QTextEdit:
        self.video_prompt = QTextEdit()
        self.video_prompt.setPlaceholderText("描述视频场景... 可使用运镜指令如[推进]、[左移]、[拉远]")
        self.video_prompt.setMaximumHeight(100)
        return self.video_prompt

    def _create_image_group(self) -> QGroupBox:
        self.video_image_group = QGroupBox("起始帧图片")
        image_layout = QVBoxLayout()
        self.video_image_path = QLineEdit()
        self.video_image_path.setReadOnly(True)
        image_layout.addWidget(self.video_image_path)

        img_btn_layout = QHBoxLayout()
        select_img_btn = QPushButton("📷 选择图片")
        select_img_btn.clicked.connect(self._select_video_image)
        img_btn_layout.addWidget(select_img_btn)
        img_btn_layout.addStretch()
        image_layout.addLayout(img_btn_layout)
        self.video_image_group.setLayout(image_layout)
        return self.video_image_group

    def _create_params_group(self) -> QGroupBox:
        params_group = QGroupBox("参数设置")
        params_layout = QFormLayout()

        self.video_model = QComboBox()
        self.video_model.addItems([
            "MiniMax-Hailuo-2.3", "MiniMax-Hailuo-02",
            "MiniMax-Hailuo-2.3-Fast"
        ])
        params_layout.addRow("模型:", self.video_model)

        self.video_duration = QComboBox()
        self.video_duration.addItems(["6", "10"])
        params_layout.addRow("时长:", self.video_duration)

        self.video_resolution = QComboBox()
        self.video_resolution.addItems(["512P", "720P", "768P", "1080P"])
        params_layout.addRow("分辨率:", self.video_resolution)

        params_group.setLayout(params_layout)
        return params_group

    def _create_action_layout(self) -> QHBoxLayout:
        btn_layout = QHBoxLayout()
        self.video_generate_btn = QPushButton("🎬 生成视频")
        self.video_generate_btn.clicked.connect(self.generate_video)
        btn_layout.addWidget(self.video_generate_btn)

        self.video_query_btn = QPushButton("🔍 查询状态")
        self.video_query_btn.clicked.connect(self._query_video_manual)
        self.video_query_btn.setEnabled(False)
        btn_layout.addWidget(self.video_query_btn)

        self.video_download_btn = QPushButton("⬇️ 下载")
        self.video_download_btn.clicked.connect(self._download_video)
        self.video_download_btn.setEnabled(False)
        btn_layout.addWidget(self.video_download_btn)
        return btn_layout

    def _create_status_label(self) -> QLabel:
        self.video_status = QLabel("")
        self.video_status.setAlignment(Qt.AlignCenter)
        return self.video_status

    def _create_loading_bar(self) -> QProgressBar:
        self.video_loading = QProgressBar()
        self.video_loading.setRange(0, 0)
        self.video_loading.setVisible(False)
        return self.video_loading

    # ==================== 状态管理 ====================

    def _set_loading(self, loading: bool, status_text: str = None):
        self.video_loading.setVisible(loading)
        if status_text is not None:
            self.video_status.setText(status_text)

    # ==================== 事件处理 ====================

    def _on_mode_changed(self, index):
        is_i2v = (index == 1)
        self.video_prompt_label.setText("视频描述（图生视频可选）:" if is_i2v else "视频描述:")
        self.video_prompt.setPlaceholderText(
            "可选：补充描述镜头运动、风格或节奏..."
            if is_i2v else
            "描述视频场景... 可使用运镜指令如[推进]、[左移]、[拉远]"
        )
        self.video_prompt.setVisible(True)
        self.video_image_group.setVisible(is_i2v)

    def _select_video_image(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "图片文件 (*.png *.jpg *.jpeg *.webp)"
        )
        if filepath:
            self.video_image_path.setText(filepath)

    # ==================== 生成逻辑 ====================

    def generate_video(self):
        if not self.check_client_func():
            return

        prompt = self.video_prompt.toPlainText().strip()
        image_path = self.video_image_path.text().strip() if self.video_mode.currentIndex() == 1 else ""

        if self.video_mode.currentIndex() == 0 and not prompt:
            QMessageBox.warning(self, "警告", "请输入视频描述")
            return
        if self.video_mode.currentIndex() == 1 and not image_path:
            QMessageBox.warning(self, "警告", "请选择起始帧图片")
            return

        self.video_generate_btn.setEnabled(False)
        self._set_loading(True, "正在生成...")
        self.video_query_btn.setEnabled(False)
        self.video_download_btn.setEnabled(False)
        self.video_poll_timer.stop()

        if self.video_mode.currentIndex() == 0:
            def do_generate():
                client = self.client_getter()
                return client.generate_video(
                    prompt=prompt,
                    model=self.video_model.currentText(),
                    duration=int(self.video_duration.currentText()),
                    resolution=self.video_resolution.currentText(),
                )
        else:
            def do_generate():
                client = self.client_getter()
                return client.generate_video_from_image(
                    image=image_path,
                    prompt=self.video_prompt.toPlainText(),
                    model=self.video_model.currentText(),
                    duration=int(self.video_duration.currentText()),
                    resolution=self.video_resolution.currentText(),
                )

        self.generation_thread = GenerationThread(do_generate)
        self.generation_thread.finished.connect(self._on_generate_finished)
        self.generation_thread.error.connect(self._on_error)
        self.generation_thread.start()

    def _on_generate_finished(self, result):
        self.video_generate_btn.setEnabled(True)
        task_id = result.get("id") or result.get("task_id")
        if task_id:
            self.video_task_id = task_id
            self._set_loading(True, f"✓ 任务已提交: {task_id}，正在自动查询状态...")
            self.video_query_btn.setEnabled(True)
            self.video_download_btn.setEnabled(False)
            self.video_poll_timer.start()
        else:
            self._set_loading(False, "✗ 生成失败")

    # ==================== 查询逻辑 ====================

    def _query_video_manual(self):
        self._query_video_task(manual=True)

    def _query_video_auto(self):
        self._query_video_task(manual=False)

    def _query_video_task(self, manual=False):
        if not self.video_task_id or self.video_querying:
            return

        self.video_querying = True
        if manual:
            self.video_query_btn.setEnabled(False)
            self._set_loading(True, "正在查询...")

        def do_query():
            client = self.client_getter()
            return client.query_video_task(self.video_task_id)

        self.generation_thread = GenerationThread(do_query)
        self.generation_thread.finished.connect(
            lambda result, is_manual=manual: self._on_query_finished(result, is_manual)
        )
        self.generation_thread.error.connect(
            lambda err, is_manual=manual: self._on_query_error(err, is_manual)
        )
        self.generation_thread.start()

    def _on_query_finished(self, result, manual):
        data = result.get("data", {})
        status = result.get("status") or data.get("status") or data.get("task_status") or "unknown"
        status_text = str(status).lower()

        if any(s in status_text for s in ["success", "succeeded", "completed", "finished", "done"]):
            self.video_poll_timer.stop()
            self._set_loading(False, "✓ 视频已生成完成，可下载")
            self.video_download_btn.setEnabled(True)
        elif any(s in status_text for s in ["fail", "failed", "error"]):
            self.video_poll_timer.stop()
            self._set_loading(False, f"✗ 任务失败: {status}")
            self.video_download_btn.setEnabled(False)
        else:
            polling_text = "（自动轮询中）" if self.video_poll_timer.isActive() else ""
            self._set_loading(True, f"状态: {status} {polling_text}".strip())
            self.video_download_btn.setEnabled(False)

        self.video_querying = False
        if manual:
            self.video_query_btn.setEnabled(True)

    def _on_query_error(self, error_msg, manual):
        if manual:
            self._set_loading(False, f"查询失败: {error_msg}")
            self.video_query_btn.setEnabled(True)
        self.video_querying = False

    # ==================== 下载逻辑 ====================

    def _download_video(self):
        if not self.video_task_id:
            return

        default_name = f"video_{self.video_task_id[:8]}.mp4"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存视频", default_name, "视频文件 (*.mp4)"
        )
        if not save_path:
            return

        self.video_download_btn.setEnabled(False)
        self._set_loading(True, "正在下载...")

        def do_download():
            client = self.client_getter()
            return client.download_video(self.video_task_id, save_path)

        self.generation_thread = GenerationThread(do_download)
        self.generation_thread.finished.connect(self._on_download_finished)
        self.generation_thread.error.connect(self._on_error)
        self.generation_thread.start()

    def _on_download_finished(self, result):
        self.video_download_btn.setEnabled(True)
        if result.get("saved_path"):
            QMessageBox.information(self, "成功", f"视频已保存到:\n{result.get('saved_path')}")
            self._set_loading(False, "✓ 下载完成")
        else:
            self._set_loading(False, "✗ 下载失败")

    # ==================== 错误处理 ====================

    def _on_error(self, error_msg: str):
        self.video_poll_timer.stop()
        self._set_loading(False)
        self.video_generate_btn.setEnabled(True)
        self.video_query_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", f"操作失败: {error_msg}")

    def cleanup(self):
        """销毁前停止定时器"""
        self.video_poll_timer.stop()

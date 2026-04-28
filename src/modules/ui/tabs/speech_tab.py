"""
语音生成 Tab 组件（self-contained Widget）。
"""
from typing import Callable, Any

import os

from PySide6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QGroupBox, QFormLayout,
    QComboBox, QDoubleSpinBox, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt

from ..components.common import AudioPlayer, GenerationThread
from ...core.constants import (
    SPEECH_MODELS,
    SPEECH_VOICES,
    SPEECH_EMOTIONS,
    SPEECH_EMOTION_API_MAP,
)


class SpeechTabWidget(QScrollArea):
    """语音生成 Tab（self-contained）"""

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
        self._build_ui()

    def _build_ui(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("文本内容:"))
        layout.addWidget(self._create_text_input())
        layout.addWidget(self._create_params_group())
        layout.addWidget(self._create_generate_button())
        layout.addWidget(self._create_status_label())
        layout.addWidget(self._create_player())
        layout.addWidget(self._create_path_label())
        layout.addLayout(self._create_output_dir_layout())

        layout.setAlignment(Qt.AlignTop)
        self.setWidget(widget)
        self.setWidgetResizable(True)

    def _create_text_input(self) -> QTextEdit:
        self.speech_text = QTextEdit()
        self.speech_text.setPlaceholderText("输入要转换的文本内容...")
        self.speech_text.setMaximumHeight(120)
        return self.speech_text

    def _create_params_group(self) -> QGroupBox:
        params_group = QGroupBox("参数设置")
        params_layout = QFormLayout()

        self.speech_model = QComboBox()
        self.speech_model.addItems(SPEECH_MODELS)
        params_layout.addRow("模型:", self.speech_model)

        self.speech_voice = QComboBox()
        self.speech_voice.addItems(SPEECH_VOICES)
        params_layout.addRow("音色:", self.speech_voice)

        self.speech_speed = QDoubleSpinBox()
        self.speech_speed.setRange(0.5, 2.0)
        self.speech_speed.setValue(1.0)
        self.speech_speed.setSingleStep(0.1)
        params_layout.addRow("语速:", self.speech_speed)

        self.speech_emotion = QComboBox()
        self.speech_emotion.addItems(SPEECH_EMOTIONS)
        params_layout.addRow("情感:", self.speech_emotion)

        params_group.setLayout(params_layout)
        return params_group

    def _create_generate_button(self) -> QPushButton:
        self.speech_generate_btn = QPushButton("🎤 生成语音")
        self.speech_generate_btn.clicked.connect(self.generate_speech)
        return self.speech_generate_btn

    def _create_status_label(self) -> QLabel:
        self.speech_status = QLabel("")
        self.speech_status.setAlignment(Qt.AlignCenter)
        return self.speech_status

    def _create_player(self) -> AudioPlayer:
        self.speech_player = AudioPlayer()
        return self.speech_player

    def _create_path_label(self) -> QLabel:
        self.speech_path = QLabel("")
        self.speech_path.setWordWrap(True)
        return self.speech_path

    def _create_output_dir_layout(self) -> QHBoxLayout:
        output_dir_layout = QHBoxLayout()
        self.speech_output_dir_label = QLabel("")
        self.speech_output_dir_label.setStyleSheet("color: #888; font-size: 12px;")
        self.speech_output_dir_label.setWordWrap(True)
        output_dir_layout.addWidget(self.speech_output_dir_label, 1)

        open_output_btn = QPushButton("📂 打开输出文件夹")
        open_output_btn.setFixedWidth(140)
        open_output_btn.clicked.connect(self._open_output_dir)
        output_dir_layout.addWidget(open_output_btn)
        return output_dir_layout

    # ==================== 参数映射 ====================

    @staticmethod
    def _emotion_to_api(text: str) -> str:
        return SPEECH_EMOTION_API_MAP.get(text, "neutral")

    # ==================== 生成逻辑 ====================

    def generate_speech(self):
        if not self.check_client_func():
            return

        text = self.speech_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "警告", "请输入文本内容")
            return

        self.speech_generate_btn.setEnabled(False)
        self.speech_status.setText("正在生成...")

        def do_generate():
            client = self.client_getter()
            return client.generate_speech(
                text=text,
                model=self.speech_model.currentText(),
                voice_id=self.speech_voice.currentText(),
                speed=self.speech_speed.value(),
                emotion=self._emotion_to_api(self.speech_emotion.currentText()),
            )

        self.generation_thread = GenerationThread(do_generate)
        self.generation_thread.finished.connect(self._on_finished)
        self.generation_thread.error.connect(self._on_error)
        self.generation_thread.start()

    def _on_finished(self, result):
        self.speech_generate_btn.setEnabled(True)
        if result.get("saved_path"):
            path = result["saved_path"]
            self.speech_status.setText("✓ 生成成功")
            self.speech_path.setText(f"保存路径: {path}")
            self.speech_player.load_file(path)
        else:
            self.speech_status.setText("✗ 生成失败")

    def _on_error(self, error_msg: str):
        self.speech_generate_btn.setEnabled(True)
        self.speech_status.setText("✗ 生成失败")
        QMessageBox.critical(self, "错误", f"语音生成失败: {error_msg}")

    def _open_output_dir(self):
        client = self.client_getter()
        if client:
            output_dir = str(client.output_dir)
            if os.path.isdir(output_dir):
                os.startfile(output_dir)
                return
        QMessageBox.warning(self, "提示", "无法获取输出目录，请先在「配置」页面设置 API 密钥")

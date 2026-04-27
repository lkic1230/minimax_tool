"""
音乐生成 Tab 组件（self-contained Widget）。
"""
import os
import base64
from typing import Callable, Any

from PySide6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QTabWidget, QLabel,
    QTextEdit, QLineEdit, QComboBox, QFormLayout, QCheckBox, QPushButton,
    QProgressBar, QFileDialog, QMessageBox, QApplication
)
from PySide6.QtCore import Qt

from ..components.common import AudioPlayer, GenerationThread


class MusicTabWidget(QScrollArea):
    """音乐生成 Tab（self-contained）"""

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
        self._cover_feature_id = None
        self._cover_formatted_lyrics = ""
        self._prev_original_mode_index = 0
        self._build_ui()

    def _build_ui(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_mode_group())
        layout.addWidget(self._create_status_label())
        layout.addWidget(self._create_loading_bar())
        layout.addWidget(self._create_player())
        layout.addWidget(self._create_path_label())
        layout.addLayout(self._create_output_dir_layout())

        layout.setAlignment(Qt.AlignTop)
        self.setWidget(widget)
        self.setWidgetResizable(True)

    def _create_mode_group(self) -> QGroupBox:
        mode_group = QGroupBox("生成模式")
        mode_layout = QVBoxLayout()
        self.music_mode_tabs = QTabWidget()
        self.music_mode_tabs.addTab(self._create_original_panel(), "🎼 原创音乐")
        self.music_mode_tabs.addTab(self._create_cover_panel(), "🎤 翻唱音乐")
        self.music_mode_tabs.addTab(self._create_lyrics_panel(), "✍️ 歌词生成")
        mode_layout.addWidget(self.music_mode_tabs)
        mode_group.setLayout(mode_layout)
        return mode_group

    def _create_status_label(self) -> QLabel:
        self.music_status = QLabel("")
        self.music_status.setAlignment(Qt.AlignCenter)
        return self.music_status

    def _create_loading_bar(self) -> QProgressBar:
        self.music_loading = QProgressBar()
        self.music_loading.setRange(0, 0)
        self.music_loading.setVisible(False)
        return self.music_loading

    def _create_player(self) -> AudioPlayer:
        self.music_player = AudioPlayer()
        return self.music_player

    def _create_path_label(self) -> QLabel:
        self.music_path = QLabel("")
        self.music_path.setWordWrap(True)
        return self.music_path

    def _create_output_dir_layout(self) -> QHBoxLayout:
        output_dir_layout = QHBoxLayout()
        self.music_output_dir_label = QLabel("")
        self.music_output_dir_label.setStyleSheet("color: #888; font-size: 12px;")
        self.music_output_dir_label.setWordWrap(True)
        output_dir_layout.addWidget(self.music_output_dir_label, 1)

        open_output_btn = QPushButton("📂 打开输出文件夹")
        open_output_btn.setFixedWidth(140)
        open_output_btn.clicked.connect(self._open_output_dir)
        output_dir_layout.addWidget(open_output_btn)
        return output_dir_layout

    # ==================== 状态管理 ====================

    def _set_loading(self, loading: bool, status_text: str = None):
        self.music_loading.setVisible(loading)
        if status_text is not None:
            self.music_status.setText(status_text)

    # ==================== 参数映射 ====================

    @staticmethod
    def _lyrics_mode_to_api(text: str) -> str:
        return {"完整歌曲": "write_full_song", "编辑续写": "edit"}.get(text, "write_full_song")

    # ==================== 原创音乐面板 ====================

    def _create_original_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignTop)

        layout.addWidget(QLabel("音乐描述:"))
        self.original_prompt = QTextEdit()
        self.original_prompt.setPlaceholderText("描述音乐的风格、情绪、场景...")
        self.original_prompt.setMaximumHeight(80)
        layout.addWidget(self.original_prompt)

        layout.addWidget(QLabel("歌曲标题（可选）:"))
        self.original_title = QLineEdit()
        self.original_title.setPlaceholderText("输入歌曲标题")
        layout.addWidget(self.original_title)

        layout.addWidget(self._create_original_params_group())
        layout.addWidget(self._create_original_lyrics_group())

        self.original_generate_btn = QPushButton("🎵 生成原创音乐")
        self.original_generate_btn.clicked.connect(self._generate_original_music)
        layout.addWidget(self.original_generate_btn)
        layout.addStretch()
        return panel

    def _create_original_params_group(self) -> QGroupBox:
        params_group = QGroupBox("参数设置")
        params_layout = QFormLayout()

        self.original_model = QComboBox()
        self.original_model.addItems(["music-2.6", "music-2.6-free"])
        params_layout.addRow("模型:", self.original_model)

        self.original_is_instrumental = QComboBox()
        self.original_is_instrumental.addItems(["歌曲（有歌词）", "纯音乐"])
        self.original_is_instrumental.currentIndexChanged.connect(self._on_original_mode_changed)
        params_layout.addRow("模式:", self.original_is_instrumental)

        params_group.setLayout(params_layout)
        return params_group

    def _create_original_lyrics_group(self) -> QGroupBox:
        self.original_lyrics_group = QGroupBox("歌词")
        lyrics_layout = QVBoxLayout()

        lyrics_btn_layout = QHBoxLayout()
        self.original_auto_lyrics = QCheckBox("自动生成歌词")
        self.original_auto_lyrics.stateChanged.connect(self._on_auto_lyrics_changed)
        lyrics_btn_layout.addWidget(self.original_auto_lyrics)

        generate_lyrics_btn = QPushButton("✍️ AI生成歌词")
        generate_lyrics_btn.clicked.connect(self._generate_lyrics_for_original)
        lyrics_btn_layout.addWidget(generate_lyrics_btn)
        lyrics_btn_layout.addStretch()
        lyrics_layout.addLayout(lyrics_btn_layout)

        self.original_lyrics = QTextEdit()
        self.original_lyrics.setPlaceholderText("输入歌词，每行一句，用换行分隔")
        self.original_lyrics.setMaximumHeight(120)
        lyrics_layout.addWidget(self.original_lyrics)
        self.original_lyrics_group.setLayout(lyrics_layout)
        return self.original_lyrics_group

    # ==================== 翻唱面板 ====================

    def _create_cover_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)

        layout.addWidget(QLabel("参考音频:"))
        layout.addWidget(self._create_cover_upload_group())

        layout.addWidget(QLabel("音乐描述（描述想要的风格）:"))
        self.cover_prompt = QTextEdit()
        self.cover_prompt.setPlaceholderText("描述翻唱版本的风格、情绪...")
        self.cover_prompt.setMaximumHeight(80)
        layout.addWidget(self.cover_prompt)

        layout.addWidget(self._create_cover_params_group())
        layout.addWidget(self._create_cover_lyrics_group())

        self.cover_generate_btn = QPushButton("🎵 生成翻唱音乐")
        self.cover_generate_btn.clicked.connect(self._generate_cover_music)
        layout.addWidget(self.cover_generate_btn)
        return panel

    def _create_cover_upload_group(self) -> QGroupBox:
        cover_group = QGroupBox("上传参考音频")
        cover_layout = QVBoxLayout()

        audio_path_layout = QHBoxLayout()
        self.cover_audio_path = QLineEdit()
        self.cover_audio_path.setReadOnly(True)
        self.cover_audio_path.setPlaceholderText("选择参考音频文件（MP3/WAV/OGG）")
        audio_path_layout.addWidget(self.cover_audio_path)

        select_audio_btn = QPushButton("📂 选择")
        select_audio_btn.clicked.connect(self._select_cover_audio)
        audio_path_layout.addWidget(select_audio_btn)
        cover_layout.addLayout(audio_path_layout)

        self.cover_two_step = QCheckBox("使用两步翻唱（先提取特征，再生成）")
        cover_layout.addWidget(self.cover_two_step)

        self.cover_feature_info = QLabel("")
        self.cover_feature_info.setWordWrap(True)
        self.cover_feature_info.setStyleSheet("color: #888; padding: 5px;")
        cover_layout.addWidget(self.cover_feature_info)

        preprocess_btn = QPushButton("🔍 提取音频特征")
        preprocess_btn.clicked.connect(self._preprocess_cover_audio)
        cover_layout.addWidget(preprocess_btn)

        cover_group.setLayout(cover_layout)
        return cover_group

    def _create_cover_params_group(self) -> QGroupBox:
        params_group = QGroupBox("参数设置")
        params_layout = QFormLayout()
        self.cover_model = QComboBox()
        self.cover_model.addItems(["music-cover", "music-cover-free"])
        params_layout.addRow("模型:", self.cover_model)
        params_group.setLayout(params_layout)
        return params_group

    def _create_cover_lyrics_group(self) -> QGroupBox:
        self.cover_lyrics_group = QGroupBox("歌词（可选）")
        cover_lyrics_layout = QVBoxLayout()
        self.cover_lyrics = QTextEdit()
        self.cover_lyrics.setPlaceholderText("输入自定义歌词，不填则自动从参考音频提取")
        self.cover_lyrics.setMaximumHeight(80)
        cover_lyrics_layout.addWidget(self.cover_lyrics)
        self.cover_lyrics_group.setLayout(cover_lyrics_layout)
        return self.cover_lyrics_group

    # ==================== 歌词面板 ====================

    def _create_lyrics_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(self._create_lyrics_mode_group())

        layout.addWidget(QLabel("歌曲标题（可选）:"))
        self.lyrics_title = QLineEdit()
        self.lyrics_title.setPlaceholderText("输入歌曲标题，生成结果会保持此标题")
        layout.addWidget(self.lyrics_title)

        layout.addWidget(QLabel("歌曲描述:"))
        self.lyrics_prompt = QTextEdit()
        self.lyrics_prompt.setPlaceholderText("描述歌曲的主题、风格、情绪...")
        self.lyrics_prompt.setMaximumHeight(80)
        layout.addWidget(self.lyrics_prompt)

        layout.addWidget(self._create_lyrics_edit_group())

        self.lyrics_generate_btn = QPushButton("✍️ 生成歌词")
        self.lyrics_generate_btn.clicked.connect(self._generate_lyrics_only)
        layout.addWidget(self.lyrics_generate_btn)

        layout.addWidget(self._create_lyrics_result_group())
        self._on_lyrics_mode_changed(self.lyrics_mode.currentIndex())
        return panel

    def _create_lyrics_mode_group(self) -> QGroupBox:
        lyrics_mode_group = QGroupBox("生成模式")
        lyrics_mode_layout = QFormLayout()
        self.lyrics_mode = QComboBox()
        self.lyrics_mode.addItems(["完整歌曲", "编辑续写"])
        self.lyrics_mode.currentIndexChanged.connect(self._on_lyrics_mode_changed)
        lyrics_mode_layout.addRow("模式:", self.lyrics_mode)
        lyrics_mode_group.setLayout(lyrics_mode_layout)
        return lyrics_mode_group

    def _create_lyrics_edit_group(self) -> QGroupBox:
        self.lyrics_edit_group = QGroupBox("现有歌词（用于续写/修改）")
        lyrics_edit_layout = QVBoxLayout()
        self.lyrics_edit_input = QTextEdit()
        self.lyrics_edit_input.setPlaceholderText("输入现有歌词，用于续写或修改")
        self.lyrics_edit_input.setMaximumHeight(100)
        lyrics_edit_layout.addWidget(self.lyrics_edit_input)
        self.lyrics_edit_group.setLayout(lyrics_edit_layout)
        return self.lyrics_edit_group

    def _create_lyrics_result_group(self) -> QGroupBox:
        result_group = QGroupBox("生成结果")
        result_layout = QVBoxLayout()

        self.lyrics_result_title = QLabel("")
        self.lyrics_result_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        result_layout.addWidget(self.lyrics_result_title)

        self.lyrics_result_tags = QLabel("")
        self.lyrics_result_tags.setStyleSheet("color: #4caf50;")
        result_layout.addWidget(self.lyrics_result_tags)

        self.lyrics_result = QTextEdit()
        self.lyrics_result.setReadOnly(True)
        self.lyrics_result.setMaximumHeight(200)
        result_layout.addWidget(self.lyrics_result)

        copy_btn = QPushButton("📋 复制歌词")
        copy_btn.clicked.connect(self._copy_lyrics)
        result_layout.addWidget(copy_btn)

        result_group.setLayout(result_layout)
        return result_group

    # ==================== 交互事件 ====================

    def _on_original_mode_changed(self, _index):
        is_instrumental = (self.original_is_instrumental.currentText() == "纯音乐")
        has_lyrics = bool(self.original_lyrics.toPlainText().strip())

        if is_instrumental and has_lyrics:
            reply = QMessageBox.question(
                self, "确认切换",
                '切换到\u201c纯音乐\u201d会清空当前歌词，是否继续？',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                self.original_is_instrumental.blockSignals(True)
                self.original_is_instrumental.setCurrentIndex(self._prev_original_mode_index)
                self.original_is_instrumental.blockSignals(False)
                return

        self.original_lyrics_group.setVisible(not is_instrumental)
        if is_instrumental:
            self.original_lyrics.clear()
        self._prev_original_mode_index = self.original_is_instrumental.currentIndex()

    def _on_auto_lyrics_changed(self, state):
        checked = (state != 0)
        has_lyrics = bool(self.original_lyrics.toPlainText().strip())

        if checked and has_lyrics:
            reply = QMessageBox.question(
                self, "确认操作",
                '启用\u201c自动生成歌词\u201d会清空当前手写歌词，是否继续？',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                self.original_auto_lyrics.blockSignals(True)
                self.original_auto_lyrics.setChecked(False)
                self.original_auto_lyrics.blockSignals(False)
                self.original_lyrics.setEnabled(True)
                return

        self.original_lyrics.setEnabled(not checked)
        if checked:
            self.original_lyrics.clear()

    def _on_lyrics_mode_changed(self, _index):
        is_edit = (self.lyrics_mode.currentText() == "编辑续写")
        self.lyrics_edit_group.setVisible(is_edit)
        self.lyrics_prompt.setVisible(not is_edit)

    def _select_cover_audio(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择音频文件", "", "音频文件 (*.mp3 *.wav *.ogg)"
        )
        if filepath:
            self.cover_audio_path.setText(filepath)
            self.cover_feature_info.setText("")

    def _copy_lyrics(self):
        lyrics = self.lyrics_result.toPlainText()
        if lyrics:
            QApplication.clipboard().setText(lyrics)
            QMessageBox.information(self, "成功", "歌词已复制到剪贴板")

    # ==================== 翻唱预处理 ====================

    def _preprocess_cover_audio(self):
        if not self.check_client_func():
            return

        audio_path = self.cover_audio_path.text().strip()
        if not audio_path:
            QMessageBox.warning(self, "警告", "请先选择参考音频文件")
            return

        self.cover_generate_btn.setEnabled(False)
        self.cover_feature_info.setText("正在提取音频特征...")

        def do_preprocess():
            with open(audio_path, "rb") as f:
                audio_base64 = base64.b64encode(f.read()).decode()
            client = self.client_getter()
            return client.cover_preprocess(audio_base64=audio_base64)

        self.generation_thread = GenerationThread(do_preprocess)
        self.generation_thread.finished.connect(self._on_cover_preprocess_finished)
        self.generation_thread.error.connect(self._on_cover_preprocess_error)
        self.generation_thread.start()

    def _on_cover_preprocess_finished(self, result):
        self.cover_generate_btn.setEnabled(True)
        cover_feature_id = result.get("cover_feature_id")
        formatted_lyrics = result.get("formatted_lyrics", "")

        if cover_feature_id:
            self.cover_feature_info.setText(
                f"✓ 特征提取成功！ID: {cover_feature_id[:20]}...\n"
                f"歌词: {formatted_lyrics[:100]}..." if formatted_lyrics else f"✓ 特征ID: {cover_feature_id[:20]}..."
            )
            self._cover_feature_id = cover_feature_id
            self._cover_formatted_lyrics = formatted_lyrics
        else:
            self.cover_feature_info.setText("✗ 特征提取失败")

    def _on_cover_preprocess_error(self, error_msg):
        self.cover_generate_btn.setEnabled(True)
        self.cover_feature_info.setText(f"✗ 错误: {error_msg}")

    # ==================== 歌词生成 ====================

    def _generate_lyrics_for_original(self):
        """为原创音乐生成歌词"""
        if not self.check_client_func():
            return

        prompt = self.original_prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "警告", "请输入音乐描述")
            return

        title = self.original_title.text().strip()

        self.original_generate_btn.setEnabled(False)
        self.music_status.setText("正在生成歌词...")

        def do_generate():
            client = self.client_getter()
            return client.generate_lyrics(
                mode="write_full_song", prompt=prompt, title=title
            )

        self.generation_thread = GenerationThread(do_generate)
        self.generation_thread.finished.connect(self._on_original_lyrics_generated)
        self.generation_thread.error.connect(self._on_error)
        self.generation_thread.start()

    def _on_original_lyrics_generated(self, result):
        self.original_generate_btn.setEnabled(True)
        lyrics = result.get("lyrics")
        if lyrics:
            self.original_lyrics.setPlainText(lyrics)
            self.music_status.setText("✓ 歌词生成成功")
        else:
            self.music_status.setText("✗ 歌词生成失败")

    def _generate_lyrics_only(self):
        """仅生成歌词"""
        if not self.check_client_func():
            return

        mode = self._lyrics_mode_to_api(self.lyrics_mode.currentText())
        prompt = self.lyrics_prompt.toPlainText().strip()
        lyrics_input = self.lyrics_edit_input.toPlainText().strip() if mode == "edit" else None
        title = self.lyrics_title.text().strip() or None

        if mode == "write_full_song" and not prompt:
            QMessageBox.warning(self, "警告", "请输入歌曲描述")
            return

        if mode == "edit" and not lyrics_input:
            QMessageBox.warning(self, "警告", "请输入现有歌词")
            return

        self.lyrics_generate_btn.setEnabled(False)
        self._set_loading(True, "正在生成歌词...")

        def do_generate():
            kwargs = {"mode": mode}
            if mode == "write_full_song":
                kwargs["prompt"] = prompt
            else:
                kwargs["lyrics"] = lyrics_input
            if title:
                kwargs["title"] = title
            client = self.client_getter()
            return client.generate_lyrics(**kwargs)

        self.generation_thread = GenerationThread(do_generate)
        self.generation_thread.finished.connect(self._on_lyrics_generated)
        self.generation_thread.error.connect(self._on_error)
        self.generation_thread.start()

    def _on_lyrics_generated(self, result):
        self.lyrics_generate_btn.setEnabled(True)

        song_title = result.get("song_title", "")
        style_tags = result.get("style_tags", [])
        lyrics = result.get("lyrics", "")

        if lyrics:
            self.lyrics_result_title.setText(song_title if song_title else "生成的歌词")
            self.lyrics_result_tags.setText(f"风格标签: {', '.join(style_tags)}" if style_tags else "")
            self.lyrics_result.setPlainText(lyrics)
            self._set_loading(False, "✓ 歌词生成成功")
        else:
            self._set_loading(False, "✗ 歌词生成失败")
            base_resp = result.get("base_resp", {})
            if base_resp.get("status_code") != 0:
                self._set_loading(False, f"✗ {base_resp.get('status_msg', '生成失败')}")

    # ==================== 音乐生成 ====================

    def _generate_original_music(self):
        if not self.check_client_func():
            return

        prompt = self.original_prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "警告", "请输入音乐描述")
            return

        is_instrumental = (self.original_is_instrumental.currentText() == "纯音乐")

        self.original_generate_btn.setEnabled(False)
        self._set_loading(True, "正在生成原创音乐（可能需要30-120秒）...")

        kwargs = {
            "prompt": prompt,
            "model": self.original_model.currentText(),
            "is_instrumental": is_instrumental,
        }

        if not is_instrumental:
            if self.original_auto_lyrics.isChecked():
                kwargs["lyrics_optimizer"] = True
            else:
                lyrics = self.original_lyrics.toPlainText().strip() or None
                if lyrics:
                    kwargs["lyrics"] = lyrics

        def do_generate():
            client = self.client_getter()
            return client.generate_music(**kwargs)

        self.generation_thread = GenerationThread(do_generate)
        self.generation_thread.finished.connect(self._on_music_finished)
        self.generation_thread.error.connect(self._on_error)
        self.generation_thread.start()

    def _generate_cover_music(self):
        if not self.check_client_func():
            return

        prompt = self.cover_prompt.toPlainText().strip()
        audio_path = self.cover_audio_path.text().strip()

        if not prompt:
            QMessageBox.warning(self, "警告", "请输入翻唱风格描述")
            return

        if not audio_path:
            QMessageBox.warning(self, "警告", "请先选择参考音频文件")
            return

        self.cover_generate_btn.setEnabled(False)
        self._set_loading(True, "正在生成翻唱音乐（可能需要30-120秒）...")

        def do_generate():
            kwargs = {
                "prompt": prompt,
                "model": self.cover_model.currentText(),
            }

            if self.cover_two_step.isChecked():
                if not self._cover_feature_id:
                    raise ValueError('请先点击\u201c提取音频特征\u201d，或关闭\u201c两步翻唱\u201d选项')
                kwargs["cover_feature_id"] = self._cover_feature_id
            else:
                with open(audio_path, "rb") as f:
                    kwargs["audio_base64"] = base64.b64encode(f.read()).decode()

            lyrics = self.cover_lyrics.toPlainText().strip()
            if lyrics:
                kwargs["lyrics"] = lyrics

            client = self.client_getter()
            return client.generate_music(**kwargs)

        self.generation_thread = GenerationThread(do_generate)
        self.generation_thread.finished.connect(self._on_music_finished)
        self.generation_thread.error.connect(self._on_cover_error)
        self.generation_thread.start()

    def _on_music_finished(self, result):
        try:
            self.original_generate_btn.setEnabled(True)
        except AttributeError:
            pass
        try:
            self.cover_generate_btn.setEnabled(True)
        except AttributeError:
            pass

        if result.get("saved_path"):
            path = result["saved_path"]
            self._set_loading(False, "✓ 生成成功")
            self.music_path.setText(f"保存路径: {path}")
            self.music_player.load_file(path)
        else:
            self._set_loading(False, "✗ 生成失败")

    def _on_cover_error(self, error_msg):
        self._set_loading(False)
        try:
            self.cover_generate_btn.setEnabled(True)
        except AttributeError:
            pass
        QMessageBox.critical(self, "错误", f"生成失败: {error_msg}")

    # ==================== 通用错误 ====================

    def _on_error(self, error_msg: str):
        self._set_loading(False)
        try:
            self.original_generate_btn.setEnabled(True)
        except AttributeError:
            pass
        try:
            self.cover_generate_btn.setEnabled(True)
            self.lyrics_generate_btn.setEnabled(True)
        except AttributeError:
            pass
        QMessageBox.critical(self, "错误", f"操作失败: {error_msg}")

    def _open_output_dir(self):
        client = self.client_getter()
        if client:
            output_dir = str(client.output_dir)
            if os.path.isdir(output_dir):
                os.startfile(output_dir)
                return
        QMessageBox.warning(self, "提示", "无法获取输出目录，请先在「配置」页面设置 API 密钥")

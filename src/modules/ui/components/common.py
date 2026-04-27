"""
Qt UI 通用组件：异步任务线程、音频播放器。
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QProgressBar
from PySide6.QtCore import Qt, QThread, Signal, QUrl

try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    HAS_MULTIMEDIA = True
except ImportError:
    HAS_MULTIMEDIA = False


class GenerationThread(QThread):
    """异步生成线程"""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class AudioPlayer(QWidget):
    """音频播放器组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        if not HAS_MULTIMEDIA:
            self.layout = QVBoxLayout(self)
            self.label = QLabel("音频播放需要 PySide6.Multimedia")
            self.label.setAlignment(Qt.AlignCenter)
            self.layout.addWidget(self.label)
            return

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self.layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        self.play_btn = QPushButton("▶ 播放")
        self.play_btn.clicked.connect(self.toggle_play)
        controls.addWidget(self.play_btn)

        self.time_label = QLabel("00:00 / 00:00")
        controls.addWidget(self.time_label)
        controls.addStretch()
        self.layout.addLayout(controls)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.layout.addWidget(self.progress)

        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)

        self.is_playing = False

    def load_file(self, filepath):
        """加载音频文件"""
        if not HAS_MULTIMEDIA:
            return
        self.player.setSource(QUrl.fromLocalFile(filepath))
        self.play_btn.setText("▶ 播放")
        self.is_playing = False

    def toggle_play(self):
        """播放/暂停切换"""
        if not HAS_MULTIMEDIA:
            return
        if self.is_playing:
            self.player.pause()
            self.play_btn.setText("▶ 播放")
        else:
            self.player.play()
            self.play_btn.setText("⏸ 暂停")
        self.is_playing = not self.is_playing

    def position_changed(self, position):
        """播放位置改变"""
        self.progress.setValue(position)

    def duration_changed(self, duration):
        """总时长改变"""
        self.progress.setMaximum(duration)
        self.time_label.setText(f"00:00 / {self._format_time(duration)}")

    def _format_time(self, ms):
        """格式化时间"""
        seconds = int(ms / 1000)
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"


# -*- coding: utf-8 -*-
"""
MiniMax Qt 桌面应用 - 主窗口（纯宿主，仅负责组装和 client/config 生命周期）
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTabWidget
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

# 处理相对/绝对导入
try:
    from .modules.core import get_app_meta, get_config_manager, get_outputs_dir, ensure_dirs
except ImportError:
    from modules.core import get_app_meta, get_config_manager, get_outputs_dir, ensure_dirs

try:
    from .modules.api import MiniMaxClient
except ImportError:
    from modules.api import MiniMaxClient

try:
    from .modules.ui import tabs as ui_tabs
except ImportError:
    from modules.ui import tabs as ui_tabs


class MainWindow(QWidget):
    """主窗口 - 纯宿主，仅负责 client/config 生命周期和 Tab 组装"""

    def __init__(self):
        super().__init__()
        self.client = None
        self.app_meta = get_app_meta()

        # 初始化目录和配置
        ensure_dirs()
        self.config_manager = get_config_manager()
        self._init_client()

        self.setup_ui()

    def _init_client(self):
        """初始化 API 客户端"""
        api_key = self.config_manager.get_api_key()
        if not api_key:
            self.client = None
            return
        output_dir = self.config_manager.get_output_dir()
        self.client = MiniMaxClient(api_key, output_dir)

    def _check_client(self) -> bool:
        """检查客户端是否已初始化（供各 Tab 使用）"""
        if not self.client:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "警告", "请先在「配置」页面设置 API 密钥")
            return False
        return True

    def _get_client(self):
        """获取当前客户端实例（供各 Tab 使用）"""
        return self.client

    def setup_ui(self):
        """设置 UI"""
        self.setWindowTitle(f"{self.app_meta['display_name']} v{self.app_meta['version']}")
        self.setMinimumSize(900, 820)
        self.resize(900, 900)

        main_layout = QVBoxLayout(self)

        # 标题
        title = QLabel(f"🎵 {self.app_meta['display_name']}")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # API 密钥状态提示
        self.api_key_warning = QLabel("⚠️ 请先在「配置」页面设置 API 密钥")
        self.api_key_warning.setStyleSheet("color: #ff9800;")
        if self.config_manager.has_api_key():
            self.api_key_warning.setText(
                f"✓ API 密钥已配置: {self.config_manager._mask_api_key(self.config_manager.get_api_key())}"
            )
            self.api_key_warning.setStyleSheet("color: #4caf50;")
        main_layout.addWidget(self.api_key_warning)

        # Tab 控件
        self.tabs = QTabWidget()

        self.chat_tab = ui_tabs.EnhancedChatTabWidget(
            client_getter=self._get_client,
            check_client_func=self._check_client,
            get_show_thinking_func=self.config_manager.get_show_thinking,
        )
        self.tabs.addTab(self.chat_tab, "💬 文本对话")

        self.image_tab = ui_tabs.ImageTabWidget(
            client_getter=self._get_client,
            check_client_func=self._check_client,
        )
        self.tabs.addTab(self.image_tab, "🖼️ 图像生成")

        self.music_tab = ui_tabs.MusicTabWidget(
            client_getter=self._get_client,
            check_client_func=self._check_client,
        )
        self.tabs.addTab(self.music_tab, "🎵 音乐生成")

        self.speech_tab = ui_tabs.SpeechTabWidget(
            client_getter=self._get_client,
            check_client_func=self._check_client,
        )
        self.tabs.addTab(self.speech_tab, "🎤 语音生成")

        self.video_tab = ui_tabs.VideoTabWidget(
            client_getter=self._get_client,
            check_client_func=self._check_client,
        )
        self.tabs.addTab(self.video_tab, "🎬 视频生成")

        self.config_tab = ui_tabs.ConfigTabWidget(
            config_manager=self.config_manager,
            on_api_key_saved=self._on_api_key_saved,
            on_output_dir_changed=self._on_output_dir_changed,
            get_default_outputs_dir=lambda: str(get_outputs_dir()),
        )
        self.tabs.addTab(self.config_tab, "⚙️ 配置")

        main_layout.addWidget(self.tabs)

    # ==================== 配置回调 ====================

    def _on_api_key_saved(self):
        """API 密钥配置变更后的回调（保存/删除都会触发）"""
        self._init_client()
        if not self.client:
            self.api_key_warning.setText("⚠️ 请先在「配置」页面设置 API 密钥")
            self.api_key_warning.setStyleSheet("color: #ff9800;")
            if hasattr(self, "config_tab"):
                self.config_tab.update_api_key_warning("未配置 API 密钥。", "#ff9800")
            return

        from PySide6.QtWidgets import QMessageBox
        validation = self.client.validate_api_key()
        if validation.get("ok"):
            api_key = self.config_manager.get_api_key()
            QMessageBox.information(
                self, "成功",
                f"API 密钥已保存并校验通过\n{validation.get('message', '')}"
            )
            self.api_key_warning.setText(
                f"✓ API 密钥已配置: {self.config_manager._mask_api_key(api_key)}"
            )
            self.api_key_warning.setStyleSheet("color: #4caf50;")
            if hasattr(self, "config_tab"):
                self.config_tab.update_api_key_warning("API 密钥校验通过，可正常使用。", "#4caf50")
        else:
            QMessageBox.warning(
                self, "校验失败",
                f"API 密钥已保存，但校验未通过\n{validation.get('message', '未知错误')}"
            )
            self.api_key_warning.setText("⚠️ API 密钥已保存，但校验未通过，请检查后重试")
            self.api_key_warning.setStyleSheet("color: #ff9800;")
            if hasattr(self, "config_tab"):
                self.config_tab.update_api_key_warning("鉴权失败，请检查网络或 API 密钥。", "#ff9800")

    def _on_output_dir_changed(self):
        """输出目录变更后的回调"""
        self._init_client()

    def closeEvent(self, event):
        """关闭时清理资源"""
        self.video_tab.cleanup()
        super().closeEvent(event)

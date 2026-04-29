# -*- coding: utf-8 -*-
"""
MiniMax Qt 桌面应用 - 主入口
"""
import sys
import os

# 确保 src 目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from qt_main_window import MainWindow
from modules.core import get_app_meta


def main():
    """应用入口"""
    app_meta = get_app_meta()
    app = QApplication(sys.argv)

    # 设置应用信息
    app.setApplicationName(app_meta["display_name"])
    app.setApplicationVersion(app_meta["version"])
    app.setOrganizationName(app_meta["organization"])

    # 设置全局样式
    app.setStyle("Fusion")

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

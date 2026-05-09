# -*- coding: utf-8 -*-
"""
Intent Analysis Worker - 意图分析后台线程
"""
from PySide6.QtCore import QThread, Signal


class IntentAnalysisWorker(QThread):
    """意图分析工作线程"""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, agent_engine, user_message, conversation_history, parent=None):
        super().__init__(parent)
        self.agent_engine = agent_engine
        self.user_message = user_message
        self.conversation_history = conversation_history

    def run(self):
        try:
            # 调用引擎分析意图
            result = self.agent_engine.process_message(
                self.user_message,
                self.conversation_history
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
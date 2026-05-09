# -*- coding: utf-8 -*-
"""
Agent Chat Worker - 后台执行线程
"""
from PySide6.QtCore import QThread, Signal


class AgentChatWorker(QThread):
    """Agent 后台工作线程"""
    status_update = Signal(str)
    step_update = Signal(dict)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, agent_engine, user_message, conversation_history, parent=None):
        super().__init__(parent)
        self.agent_engine = agent_engine
        self.user_message = user_message
        self.conversation_history = conversation_history

    def run(self):
        try:
            # 设置回调
            self.agent_engine.on_status_update = lambda s: self.status_update.emit(s)
            self.agent_engine.on_step_update = lambda d: self.step_update.emit(d)
            
            # 处理消息
            result = self.agent_engine.process_message(
                self.user_message,
                self.conversation_history
            )
            
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(str(e))

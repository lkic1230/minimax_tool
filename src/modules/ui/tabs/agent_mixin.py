# -*- coding: utf-8 -*-
"""
Agent 增强 Mixin - 为 ChatTab 添加 Agent 能力

这个文件包含 Agent 功能扩展，可以混合到 ChatTabWidget 中
"""
from PySide6.QtWidgets import QLabel, QProgressBar, QScrollArea, QMessageBox, QTimer
from PySide6.QtCore import Qt, QThread, Signal


class AgentMixin:
    """
    Agent 增强 Mixin
    
    为 ChatTabWidget 添加 Agent 能力：
    - 自动识别任务类型
    - Agent 模式执行
    - 步骤状态展示
    """
    
    def _init_agent_mixin(self):
        """初始化 Agent 增强功能"""
        # Agent 状态
        self._is_agent_mode = False
        self._agent_worker = None
        
        # 创建 Agent 引擎（延迟初始化）
        self._agent_engine = None
        
        # 创建 Agent UI 组件
        self._create_agent_ui()
    
    def _create_agent_ui(self):
        """创建 Agent UI 组件（需要子类实现具体布局）"""
        # 子类应该在适当位置调用这些组件
        pass
    
    def _should_use_agent(self, message: str) -> bool:
        """判断是否使用 Agent 模式"""
        agent_keywords = [
            "调研", "研究", "查找", "搜索", "收集", "整理",
            "获取", "查询", "分析", "报告",
            "帮我", "给我", "能否", "可以帮我",
        ]
        for keyword in agent_keywords:
            if keyword in message:
                return True
        return False
    
    def _init_agent_engine(self):
        """初始化 Agent 引擎"""
        if self._agent_engine is not None:
            return
            
        from ...agent.agent_engine import AgentEngine
        from ...agent.tool_framework import ToolRegistry
        from ...tools.web_search import WebSearchTool
        from ...tools.web_scrape import WebScrapeTool
        from ...tools.file_ops import FileReadTool, FileWriteTool
        
        # 创建工具注册表
        registry = ToolRegistry()
        registry.register(WebSearchTool())
        registry.register(WebScrapeTool())
        registry.register(FileReadTool())
        registry.register(FileWriteTool())
        
        # 创建 Agent 引擎
        self._agent_engine = AgentEngine(
            client_getter=self.client_getter,
            tool_registry=registry
        )
    
    def _run_agent_mode(self, user_message: str):
        """运行 Agent 模式"""
        from .agent_chat_worker import AgentChatWorker
        
        self._is_agent_mode = True
        self._set_generating_state(True)
        
        # 显示 Agent UI
        if hasattr(self, '_agent_status_label'):
            self._agent_status_label.setVisible(True)
        if hasattr(self, '_agent_progress_bar'):
            self._agent_progress_bar.setVisible(True)
        if hasattr(self, '_agent_steps_area'):
            self._agent_steps_area.setVisible(True)
        
        # 更新状态
        if hasattr(self, 'chat_status'):
            self.chat_status.setText("🤖 Agent 正在分析任务...")
        
        # 初始化引擎
        self._init_agent_engine()
        
        # 创建工作线程
        self._agent_worker = AgentChatWorker(self._agent_engine, user_message, self.chat_messages)
        self._agent_worker.status_update.connect(self._on_agent_status)
        self._agent_worker.step_update.connect(self._on_agent_step)
        self._agent_worker.finished.connect(self._on_agent_finished)
        self._agent_worker.error.connect(self._on_agent_error)
        self._agent_worker.start()
    
    def _on_agent_status(self, status: str):
        """Agent 状态更新"""
        if hasattr(self, 'chat_status'):
            self.chat_status.setText(status)
        if hasattr(self, '_agent_progress_bar'):
            current = self._agent_progress_bar.value()
            if current < 90:
                self._agent_progress_bar.setValue(current + 15)
    
    def _on_agent_step(self, step_data: dict):
        """Agent 步骤更新"""
        if not hasattr(self, '_agent_steps_layout'):
            return
            
        step_type = step_data.get("type", "")
        
        if step_type == "plan":
            steps = step_data.get("steps", [])
            for i, step in enumerate(steps):
                label = QLabel(f"📋 步骤 {i+1}: {step.get('action', '执行')}")
                label.setStyleSheet("color: #1565c0; padding: 4px;")
                self._agent_steps_layout.addWidget(label)
                
        elif step_type == "step_start":
            step = step_data.get("step", 0)
            label = QLabel(f"⚙️ 执行中: 步骤 {step+1}")
            label.setStyleSheet("color: #ff9800; padding: 4px;")
            self._agent_steps_layout.addWidget(label)
            
        elif step_type == "step_complete":
            step = step_data.get("step", 0)
            label = QLabel(f"✅ 步骤 {step+1} 完成")
            label.setStyleSheet("color: #4caf50; padding: 4px;")
            self._agent_steps_layout.addWidget(label)
            
        elif step_type == "step_error":
            step = step_data.get("step", 0)
            error = step_data.get("error", "")
            label = QLabel(f"❌ 步骤 {step+1} 失败: {error}")
            label.setStyleSheet("color: #f44336; padding: 4px;")
            self._agent_steps_layout.addWidget(label)
    
    def _on_agent_finished(self, result: str):
        """Agent 完成"""
        self._is_agent_mode = False
        self._set_generating_state(False)
        
        # 隐藏 Agent UI
        if hasattr(self, '_agent_status_label'):
            self._agent_status_label.setVisible(False)
        if hasattr(self, '_agent_progress_bar'):
            self._agent_progress_bar.setVisible(False)
        
        # 添加回复
        if result:
            self.chat_messages.append({"role": "assistant", "content": result})
            self._mark_dirty()
            if hasattr(self, '_append_message'):
                model_name = "MiniMax-M2.7"
                self._append_message("assistant", result, author=model_name)
        
        if hasattr(self, 'chat_status'):
            self.chat_status.setText("✅ Agent 任务完成")
        
        # 延迟隐藏步骤区域
        if hasattr(self, '_agent_steps_area'):
            QTimer.singleShot(3000, lambda: self._agent_steps_area.setVisible(False))
    
    def _on_agent_error(self, error: str):
        """Agent 错误"""
        self._is_agent_mode = False
        self._set_generating_state(False)
        
        if hasattr(self, '_agent_status_label'):
            self._agent_status_label.setVisible(False)
        if hasattr(self, '_agent_progress_bar'):
            self._agent_progress_bar.setVisible(False)
        if hasattr(self, 'chat_status'):
            self.chat_status.setText("❌ Agent 执行失败")
        
        QMessageBox.critical(self, "错误", f"Agent 执行失败: {error}")
    
    def _stop_agent_task(self):
        """停止 Agent 任务"""
        if self._agent_worker and self._agent_worker.isRunning():
            self._agent_worker.terminate()
        self._is_agent_mode = False
        self._set_generating_state(False)
        
        if hasattr(self, '_agent_status_label'):
            self._agent_status_label.setVisible(False)
        if hasattr(self, '_agent_progress_bar'):
            self._agent_progress_bar.setVisible(False)
        if hasattr(self, 'chat_status'):
            self.chat_status.setText("⏹️ 已停止")

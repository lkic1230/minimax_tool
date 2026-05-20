"""
Agent Engine - AI 驱动的 Agent 核心引擎。

基于 Claude Code 三层架构设计：
- 意图解析层：理解用户输入，判断是否需要工具
- 任务规划层：自动拆解任务，确定工具调用顺序
- 工具执行层：执行工具，返回结果给 AI
"""
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum

from ..agent.tool_framework import ToolRegistry, ToolExecutor, ToolResult
from ..agent.task_manager import Task, TaskManager, TaskStatus, StepStatus


class AgentMode(Enum):
    """Agent 运行模式"""
    CHAT = "chat"           # 普通对话模式
    AGENT = "agent"        # Agent 任务模式


@dataclass
class ToolCall:
    """工具调用请求"""
    name: str
    arguments: Dict[str, Any]
    call_id: str = ""


@dataclass
class AgentState:
    """Agent 状态"""
    mode: AgentMode = AgentMode.CHAT
    current_task: Optional[Task] = None
    task_steps: List[Dict] = field(default_factory=list)
    awaiting_confirmation: bool = False
    confirmation_message: str = ""
    stopped: bool = False  # 用户主动停止标记


class AgentEngine:
    """
    Agent 核心引擎
    
    负责：
    1. 对话式任务输入
    2. AI 任务理解与拆解
    3. 自动工具调用循环
    4. 结果生成
    """

    def __init__(
        self,
        client_getter: Callable,  # 获取 API 客户端的函数
        tool_registry: ToolRegistry,
    ):
        self.client_getter = client_getter
        self.tool_registry = tool_registry
        self.tool_executor = ToolExecutor(tool_registry)
        self.task_manager = TaskManager()
        
        # 状态
        self.state = AgentState()
        
        # 回调
        self.on_status_update: Optional[Callable[[str], None]] = None
        self.on_step_update: Optional[Callable[[Dict], None]] = None
        self.on_result_ready: Optional[Callable[[str], None]] = None
        self.on_confirmation_request: Optional[Callable[[str], None]] = None

    # ==================== 核心接口 ====================

    def process_message(self, user_message: str, conversation_history: List[Dict]) -> Dict:
        """
        处理用户消息，返回结构化结果

        完整流程：
        1. LLM 分析用户意图
        2. 如果需要 Agent：执行任务计划 → 工具调用 → LLM 生成报告
        3. 如果不需要：直接返回 LLM 回复

        返回格式:
        {
            "type": "chat" | "agent",
            "content": "用户看到的最终回复",
            "task_plan": {...}  # 仅当 type=agent 时
        }
        """
        self.state.mode = AgentMode.AGENT

        # 第一步：LLM 分析意图
        intent_analysis = self._analyze_intent(user_message, conversation_history)

        if not intent_analysis.get("needs_agent", False):
            # 普通对话模式
            self.state.mode = AgentMode.CHAT
            return {
                "type": "chat",
                "content": intent_analysis.get("response", ""),
            }

        # 第二步：提取任务计划
        task_plan = intent_analysis.get("task_plan", {})
        steps = task_plan.get("steps", [])

        # 如果 LLM 没有返回有效步骤，构造默认搜索步骤
        if not steps:
            steps = [{"action": "搜索", "tool": "web_search", "params": {"query": user_message}}]
            task_plan = {"goal": user_message, "steps": steps}

        goal = task_plan.get("goal", user_message)
        self.state.task_steps = steps

        # 第三步：执行工具
        self._update_status("🚀 执行任务...")
        all_results = []
        total_steps = len(steps)
        collected_sources = []  # 收集所有来源用于最终展示

        for i, step_info in enumerate(steps):
            # 检查停止标记
            if self.state.stopped:
                self._update_status("⏹️ 已停止")
                return {
                    "type": "agent",
                    "content": "任务已被用户停止。",
                    "task_plan": task_plan,
                    "stopped": True,
                    "sources": collected_sources,
                }

            tool_name = step_info.get("tool", "")
            params = step_info.get("params", {})
            action_desc = step_info.get("action", f"步骤{i+1}")

            # 发出步骤开始事件
            if self.on_step_update:
                self.on_step_update({
                    "type": "step_start",
                    "step_index": i,
                    "total_steps": total_steps,
                    "action": action_desc,
                    "tool": tool_name,
                    "params": params,
                })

            # 在状态中显示具体的搜索内容
            if tool_name in ("web_search", "搜索"):
                query = params.get("query", "")
                self._update_status(f"🔍 搜索: {query}")
            elif tool_name in ("web_scrape", "抓取"):
                url = params.get("url", "")
                display_url = url if len(url) <= 60 else url[:57] + "..."
                self._update_status(f"🌐 抓取: {display_url}")
            elif tool_name in ("file_read", "读取文件"):
                path = params.get("path", params.get("file_path", ""))
                self._update_status(f"📄 读取文件: {path}")
            else:
                self._update_status(f"📋 {action_desc}...")

            step_start_time = time.time()
            result = self._execute_tool(tool_name, params)
            step_elapsed = time.time() - step_start_time

            # 搜索完成后在状态中显示结果数量摘要，并收集来源
            if result.success and tool_name in ("web_search", "搜索"):
                data = result.data or {}
                results_list = data.get("results", [])
                results_count = len(results_list)
                self._update_status(f"✅ 搜索完成: 找到 {results_count} 条结果")
                # 收集来源信息
                for item in results_list:
                    collected_sources.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("snippet", ""),
                    })

            all_results.append({
                "step": i + 1,
                "tool": tool_name,
                "action": action_desc,
                "success": result.success,
                "result": result.data if result.success else None,
                "error": result.error if not result.success else None,
                "elapsed": round(step_elapsed, 1),
            })

            # 发出步骤完成事件
            if self.on_step_update:
                self.on_step_update({
                    "type": "step_complete",
                    "step_index": i,
                    "total_steps": total_steps,
                    "action": action_desc,
                    "success": result.success,
                    "elapsed": round(step_elapsed, 1),
                })

        # 第四步：LLM 生成最终报告
        self._update_status("📝 生成报告...")
        report = self._generate_final_report(goal, all_results)

        return {
            "type": "agent",
            "content": report,
            "task_plan": task_plan,
            "sources": collected_sources,
        }
    
    def _analyze_intent(self, user_message: str, conversation_history: List[Dict]) -> Dict:
        """
        让 LLM 分析用户意图
        
        返回结构化分析结果：
        - needs_agent: 是否需要 Agent 模式
        - task_plan: 任务计划 (如果需要 Agent)
        - confirmation: 需要用户确认的内容
        - response: 普通回复内容 (如果不需要 Agent)
        """
        system_prompt = """你是一个意图分析助手。请分析用户输入，判断是否需要进入任务执行模式。

需要进入 Agent 模式的情况：用户想要调研、搜索、收集信息；用户想要完成一个具体任务；用户想要获取外部信息；用户想要分析、整理数据。

可以直接回复的情况：用户只是在聊天、问候；用户只是问简单问题；用户想要解释概念。

请返回以下格式的 JSON（直接返回 JSON，不要其他内容）：
{"needs_agent": true或false, "reason": "判断理由", "task_plan": {"goal": "任务目标", "steps": [{"action": "动作描述", "tool": "web_search 或 web_scrape", "params": {"参数": "值"}}]}, "confirmation": "需要用户确认的内容(可选)", "response": "如果是普通对话，直接回复用户的内容"}

重要：tool 字段只能使用以下两个工具名之一：web_search（联网搜索）、web_scrape（抓取网页）。禁止使用其他工具名。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请分析以下用户输入：{user_message}"}
        ]
        
        # 添加历史上下文（最近3条）
        if conversation_history:
            recent = conversation_history[-3:]
            for msg in recent:
                messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")[:200]})
        
        # 调用 LLM
        response = self._call_ai(messages)
        self._update_status("解析意图分析结果...")

        # 解析 JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            result = json.loads(json_match.group())
            return result

        # 解析失败，默认走普通对话（不吞异常，保留原始响应供调试）
        return {
            "needs_agent": False,
            "reason": f"JSON 解析失败，原始响应前200字符: {response[:200]}",
            "response": ""
        }


# ==================== 其他方法 ====================    # ==================== Chat 模式 ====================

    def _run_chat_mode(self, messages: List[Dict]) -> str:
        """普通对话模式"""
        self.state.mode = AgentMode.CHAT
        return self._call_ai(messages)

    # ==================== Agent 模式 ====================

    def _run_agent_mode(self, user_message: str, messages: List[Dict]) -> str:
        """Agent 任务模式"""
        self.state.mode = AgentMode.AGENT
        
        # 1. 理解任务，生成执行计划
        self._update_status("🤔 分析任务...")
        plan = self._generate_task_plan(user_message, messages)
        
        # 2. 显示计划，请求确认
        self.state.task_steps = plan.get("steps", [])
        if self.on_step_update:
            self.on_step_update({
                "type": "plan",
                "steps": self.state.task_steps,
                "goal": user_message
            })
        
        # 3. 执行循环
        self._update_status("🚀 开始执行...")
        return self._execute_task_loop(user_message, messages, plan)

    def _generate_task_plan(self, goal: str, messages: List[Dict]) -> Dict:
        """让 AI 生成任务计划"""
        # 构建系统提示
        system_prompt = """你是一个任务规划助手。用户的目标是：{goal}

请分析这个目标，并生成执行步骤。
返回 JSON 格式：
{{
    "analysis": "对目标的分析",
    "steps": [
        {{"step": 1, "action": "搜索", "tool": "web_search", "params": {{"query": "关键词"}}},
        {{"step": 2, "action": "抓取", "tool": "web_scrape", "params": {{"url": "url"}}}}
    ],
    "estimated_steps": 步骤数量
}}

只返回 JSON，不要其他内容。""".format(goal=goal)
        
        request_messages = [
            {"role": "system", "content": system_prompt}
        ] + messages
        
        response = self._call_ai(request_messages)
        
        # 解析 JSON
        try:
            # 尝试提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
    
    def execute_task_plan(self, task_plan: Dict) -> str:
        """执行任务计划"""
        steps = task_plan.get("steps", [])
        all_results = []

        for i, step_info in enumerate(steps):
            tool_name = step_info.get("tool", "")
            params = step_info.get("params", {})
            action_desc = step_info.get("action", f"步骤{i+1}")

            self._update_status(f"📋 步骤 {i+1}: {action_desc}")

            result = self._execute_tool(tool_name, params)

            all_results.append({
                "step": i + 1,
                "tool": tool_name,
                "action": action_desc,
                "success": result.success,
                "result": result.data if result.success else None,
                "error": result.error if not result.success else None,
            })

        # 生成报告
        return self._generate_final_report(task_plan.get("goal", ""), all_results)

    def _execute_task_loop(self, goal: str, messages: List[Dict], plan: Dict) -> str:
        """执行任务循环"""
        all_results = []
        
        for i, step_info in enumerate(self.state.task_steps):
            tool_name = step_info.get("tool", "")
            params = step_info.get("params", {})
            
            self._update_status(f"📋 步骤 {i+1}: {step_info.get('action', '执行中')}")
            
            # 更新步骤状态
            if self.on_step_update:
                self.on_step_update({
                    "type": "step_start",
                    "step": i,
                    "info": step_info
                })
            
            # 执行工具
            result = self._execute_tool(tool_name, params)
            
            if result.success:
                all_results.append({
                    "step": i + 1,
                    "tool": tool_name,
                    "result": result.data
                })
                
                if self.on_step_update:
                    self.on_step_update({
                        "type": "step_complete",
                        "step": i,
                        "result": result.data
                    })
            else:
                all_results.append({
                    "step": i + 1,
                    "tool": tool_name,
                    "error": result.error
                })
                
                if self.on_step_update:
                    self.on_step_update({
                        "type": "step_error",
                        "step": i,
                        "error": result.error
                    })
        
        # 4. 生成最终报告
        self._update_status("📝 生成报告...")
        return self._generate_final_report(goal, all_results)

    def _execute_tool(self, tool_name: str, params: Dict) -> ToolResult:
        """执行工具"""
        return self.tool_executor.execute(tool_name, params)

    def _generate_final_report(self, goal: str, results: List[Dict]) -> str:
        """让 LLM 基于工具执行结果生成最终报告"""
        # 构建详细的上下文，包含实际搜索结果内容
        context_parts = [f"用户目标：{goal}\n\n执行结果：\n"]

        for r in results:
            step_num = r["step"]
            action = r.get("action", f"步骤{step_num}")
            context_parts.append(f"--- {action} (步骤{step_num}) ---")

            if not r["success"]:
                context_parts.append(f"错误：{r['error']}\n")
                continue

            data = r.get("result") or {}
            # 处理搜索结果列表
            search_results = data.get("results", [])
            if search_results:
                for j, item in enumerate(search_results, 1):
                    title = item.get("title", "")
                    url = item.get("url", "")
                    snippet = item.get("snippet", "")
                    context_parts.append(f"  {j}. {title}")
                    if url:
                        context_parts.append(f"     链接：{url}")
                    if snippet:
                        context_parts.append(f"     摘要：{snippet}")
            else:
                # 非搜索结果，直接序列化
                context_parts.append(f"  数据：{json.dumps(data, ensure_ascii=False, indent=2)[:2000]}")
            context_parts.append("")

        context = "\n".join(context_parts)

        system_prompt = f"""你是一个专业的研究助手。请基于以下工具执行结果，为用户生成一份结构清晰、信息丰富的报告。

{context}

要求：
1. 围绕用户目标组织内容，不要机械罗列
2. 提炼关键信息和核心发现
3. 标注信息来源（如有链接）
4. 如果结果不足以回答用户问题，明确说明
5. 使用 Markdown 格式，保持简洁专业"""

        # 必须包含 user 消息，否则 API 可能拒绝
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "请基于以上搜索结果生成报告"}
        ]
        report = self._call_ai(messages)

        if self.on_result_ready:
            self.on_result_ready(report)

        return report

    # ==================== 底层调用 ====================

    def _call_ai(self, messages: List[Dict]) -> str:
        """调用 AI API（带超时保护）"""
        client = self.client_getter()
        if not client:
            raise RuntimeError("API 客户端未初始化")

        result = client.chat_completions(
            messages=messages,
            model="MiniMax-M2.7",
            stream=False,
            max_completion_tokens=4096,
            temperature=0.7,
            top_p=0.95,
            timeout=60,
        )

        choices = result.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""

    def _update_status(self, status: str):
        """更新状态"""
        if self.on_status_update:
            self.on_status_update(status)

    # ==================== 控制接口 ====================

    def stop(self):
        """停止当前任务"""
        self.state.stopped = True
        if self.state.current_task:
            self.task_manager.cancel_task(self.state.current_task.id)
            self.state.current_task = None
        self._update_status("⏹️ 已停止")

    def reset(self):
        """重置状态"""
        self.state = AgentState()

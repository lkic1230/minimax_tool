"""
Test AgentEngine - Agent 核心引擎测试。

Mock LLM 调用，测试意图分析、工具执行循环、stop/reset、step 回调、来源收集。
不依赖 Qt 和真实 API。
"""
import unittest
from unittest.mock import MagicMock, patch, PropertyMock
from src.modules.agent.agent_engine import (
    AgentEngine, AgentMode, AgentState, ToolCall,
)
from src.modules.agent.tool_framework import (
    BaseTool, ToolRegistry, ToolExecutor, ToolResult,
)


# ==================== Mock 工具 ====================

class MockSearchTool(BaseTool):
    """模拟搜索工具"""
    name = "web_search"
    description = "Mock search"

    def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "")
        return ToolResult(success=True, data={
            "results": [
                {"title": f"Result for {query}", "url": "https://example.com/1", "snippet": f"Snippet about {query}"},
                {"title": f"Result 2 for {query}", "url": "https://example.com/2", "snippet": f"Another snippet {query}"},
            ]
        })

    def validate(self, params) -> bool:
        return bool(params.get("query"))


class MockScrapeTool(BaseTool):
    """模拟抓取工具"""
    name = "web_scrape"
    description = "Mock scrape"

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, data={"content": "Page content here"})

    def validate(self, params) -> bool:
        return bool(params.get("url"))


class MockFailTool(BaseTool):
    """模拟失败工具"""
    name = "fail_tool"
    description = "Always fails"

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=False, error="Simulated failure")

    def validate(self, params) -> bool:
        return True


# ==================== Mock LLM Client ====================

def make_mock_client(response_text: str):
    """创建 mock API client"""
    mock_client = MagicMock()
    mock_client.chat_completions.return_value = {
        "choices": [{"message": {"content": response_text}}]
    }
    return mock_client


def make_engine(tool_registry: ToolRegistry, llm_response: str = "") -> AgentEngine:
    """创建带 mock client 的 engine"""
    mock_client = make_mock_client(llm_response)
    engine = AgentEngine(
        client_getter=lambda mc=mock_client: mc,
        tool_registry=tool_registry,
    )
    return engine


def make_registry(with_tools: bool = True) -> ToolRegistry:
    """创建带标准 mock 工具的 registry"""
    reg = ToolRegistry()
    if with_tools:
        reg.register(MockSearchTool())
        reg.register(MockScrapeTool())
        reg.register(MockFailTool())
    return reg


# 标准 agent 模式 LLM 响应模板（JSON 合法）
AGENT_PLAN_SINGLE = '{"needs_agent": true, "reason": "需要搜索", "task_plan": {"goal": "搜索", "steps": [{"action": "搜索测试", "tool": "web_search", "params": {"query": "test"}}]}}'
AGENT_PLAN_DOUBLE = '{"needs_agent": true, "reason": "需要搜索", "task_plan": {"goal": "搜索", "steps": [{"action": "搜索A", "tool": "web_search", "params": {"query": "alpha"}}, {"action": "搜索B", "tool": "web_search", "params": {"query": "beta"}}]}}'
AGENT_PLAN_SCRAPE = '{"needs_agent": true, "reason": "需要抓取", "task_plan": {"goal": "抓取", "steps": [{"action": "抓取页面", "tool": "web_scrape", "params": {"url": "https://example.com"}}]}}'
AGENT_PLAN_PYTHON = '{"needs_agent": true, "reason": "需要搜索", "task_plan": {"goal": "调研Python", "steps": [{"action": "搜索Python", "tool": "web_search", "params": {"query": "Python latest"}}]}}'


# ==================== Test Cases ====================

class TestAgentState(unittest.TestCase):
    """测试 AgentState 数据类"""

    def test_default_state(self):
        state = AgentState()
        self.assertEqual(state.mode, AgentMode.CHAT)
        self.assertIsNone(state.current_task)
        self.assertEqual(state.task_steps, [])
        self.assertFalse(state.awaiting_confirmation)
        self.assertEqual(state.confirmation_message, "")
        self.assertFalse(state.stopped)

    def test_stopped_flag(self):
        state = AgentState()
        state.stopped = True
        self.assertTrue(state.stopped)


class TestAgentEngineInit(unittest.TestCase):
    """测试 AgentEngine 初始化"""

    def test_init_sets_defaults(self):
        reg = make_registry()
        engine = make_engine(reg)
        self.assertIsNotNone(engine.tool_executor)
        self.assertIsNotNone(engine.task_manager)
        self.assertFalse(engine.state.stopped)
        self.assertIsNone(engine.on_status_update)
        self.assertIsNone(engine.on_step_update)

    def test_client_getter_called(self):
        reg = make_registry()
        mock_client = make_mock_client("")
        engine = AgentEngine(
            client_getter=lambda mc=mock_client: mc,
            tool_registry=reg,
        )
        result = engine._call_ai([{"role": "user", "content": "test"}])
        mock_client.chat_completions.assert_called_once()


class TestProcessMessageChatMode(unittest.TestCase):
    """测试 process_message - 普通对话模式"""

    def test_chat_mode_when_no_agent_needed(self):
        """LLM 判断不需要 Agent，直接返回对话"""
        reg = make_registry()
        llm_response = '{"needs_agent": false, "reason": "简单问候", "response": "你好！有什么可以帮你的吗？"}'
        engine = make_engine(reg, llm_response)

        result = engine.process_message("你好", [])

        self.assertEqual(result["type"], "chat")
        self.assertEqual(result["content"], "你好！有什么可以帮你的吗？")
        self.assertEqual(engine.state.mode, AgentMode.CHAT)

    def test_chat_mode_json_parse_failure(self):
        """LLM 返回无法解析的 JSON，应回退为对话模式"""
        reg = make_registry()
        engine = make_engine(reg, "这不是JSON，只是普通文本")

        result = engine.process_message("你好", [])

        self.assertEqual(result["type"], "chat")
        self.assertFalse(result["content"])  # 解析失败 response=""


class TestProcessMessageAgentMode(unittest.TestCase):
    """测试 process_message - Agent 任务模式"""

    def test_agent_mode_with_valid_plan(self):
        """LLM 返回有效任务计划，走 Agent 模式"""
        reg = make_registry()
        engine = make_engine(reg, AGENT_PLAN_PYTHON)

        result = engine.process_message("帮我调研Python最新动态", [])

        self.assertEqual(result["type"], "agent")
        self.assertIn("content", result)
        self.assertIn("sources", result)
        self.assertIsInstance(result["sources"], list)

    def test_agent_mode_empty_steps_fallback(self):
        """LLM 返回 needs_agent=true 但 steps 为空，应自动生成默认搜索步骤"""
        reg = make_registry()
        plan_response = '{"needs_agent": true, "reason": "需要搜索", "task_plan": {"goal": "调研Python", "steps": []}}'
        engine = make_engine(reg, plan_response)

        result = engine.process_message("调研Python", [])

        self.assertEqual(result["type"], "agent")
        self.assertGreater(len(result["sources"]), 0)

    def test_agent_mode_no_task_plan_key(self):
        """LLM 返回 needs_agent=true 但没有 task_plan 字段"""
        reg = make_registry()
        plan_response = '{"needs_agent": true, "reason": "需要搜索"}'
        engine = make_engine(reg, plan_response)

        result = engine.process_message("搜索信息", [])

        self.assertEqual(result["type"], "agent")
        self.assertGreater(len(result["sources"]), 0)


class TestStepCallbacks(unittest.TestCase):
    """测试步骤回调事件"""

    def test_step_start_and_complete_events(self):
        """验证 step_update 回调收到 step_start 和 step_complete 事件"""
        reg = make_registry()
        engine = make_engine(reg, AGENT_PLAN_SINGLE)

        events = []
        engine.on_step_update = lambda e: events.append(e)

        engine.process_message("搜索", [])

        types = [e["type"] for e in events]
        self.assertIn("step_start", types)
        self.assertIn("step_complete", types)

    def test_step_start_has_correct_fields(self):
        """step_start 事件包含必要字段"""
        reg = make_registry()
        engine = make_engine(reg, AGENT_PLAN_SINGLE)

        captured = {}
        engine.on_step_update = lambda e: captured.update(e) if e["type"] == "step_start" else None

        engine.process_message("搜索", [])

        self.assertEqual(captured["type"], "step_start")
        self.assertEqual(captured["step_index"], 0)
        self.assertEqual(captured["total_steps"], 1)
        self.assertIn("action", captured)
        self.assertIn("tool", captured)

    def test_step_complete_has_elapsed(self):
        """step_complete 事件包含 elapsed 耗时"""
        reg = make_registry()
        engine = make_engine(reg, AGENT_PLAN_SINGLE)

        complete_event = {}
        engine.on_step_update = lambda e: complete_event.update(e) if e["type"] == "step_complete" else None

        engine.process_message("搜索", [])

        self.assertEqual(complete_event["type"], "step_complete")
        self.assertIn("elapsed", complete_event)
        self.assertGreaterEqual(complete_event["elapsed"], 0)


class TestSourceCollection(unittest.TestCase):
    """测试来源收集"""

    def test_sources_collected_from_search(self):
        """搜索结果应被收集到 sources 列表"""
        reg = make_registry()
        engine = make_engine(reg, AGENT_PLAN_DOUBLE)

        result = engine.process_message("搜索两个东西", [])

        # 2 步搜索，每步 2 条结果 = 4 个来源
        self.assertEqual(len(result["sources"]), 4)
        for src in result["sources"]:
            self.assertIn("title", src)
            self.assertIn("url", src)
            self.assertIn("snippet", src)

    def test_sources_not_collected_from_non_search(self):
        """非搜索工具不应产生来源"""
        reg = make_registry()
        engine = make_engine(reg, AGENT_PLAN_SCRAPE)

        result = engine.process_message("抓取网页", [])

        self.assertEqual(len(result["sources"]), 0)


class TestStopMechanism(unittest.TestCase):
    """测试停止机制"""

    def test_stop_sets_flag(self):
        reg = make_registry()
        engine = make_engine(reg)

        engine.stop()
        self.assertTrue(engine.state.stopped)

    def test_stop_during_execution(self):
        """在工具执行过程中停止，应提前返回并带 stopped=True"""
        reg = make_registry()
        engine = make_engine(reg, AGENT_PLAN_DOUBLE)

        step_count = [0]
        def on_step(e):
            step_count[0] += 1
            if e["type"] == "step_complete" and step_count[0] >= 2:
                engine.stop()

        engine.on_step_update = on_step

        result = engine.process_message("搜索", [])

        self.assertEqual(result["type"], "agent")
        self.assertTrue(result["stopped"])
        self.assertIn("任务已被用户停止", result["content"])


class TestResetMechanism(unittest.TestCase):
    """测试重置机制"""

    def test_reset_clears_state(self):
        reg = make_registry()
        engine = make_engine(reg)
        engine.state.stopped = True
        engine.state.mode = AgentMode.AGENT

        engine.reset()

        self.assertFalse(engine.state.stopped)
        self.assertEqual(engine.state.mode, AgentMode.CHAT)


class TestStatusCallback(unittest.TestCase):
    """测试状态更新回调"""

    def test_status_update_called(self):
        reg = make_registry()
        engine = make_engine(reg)
        statuses = []
        engine.on_status_update = lambda s: statuses.append(s)

        engine._update_status("测试状态")
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0], "测试状态")

    def test_no_callback_no_error(self):
        """未设置回调时调用不应抛异常"""
        reg = make_registry()
        engine = make_engine(reg)
        engine._update_status("测试")  # 不应崩溃


class TestExecuteTaskPlan(unittest.TestCase):
    """测试 execute_task_plan 独立执行"""

    def test_execute_single_step(self):
        """执行单步任务计划，应返回报告字符串"""
        reg = make_registry()
        # execute_task_plan 内部调用 _generate_final_report -> _call_ai，
        # 需要 mock LLM 返回非空内容
        engine = make_engine(reg, "这是生成的报告内容")

        plan = {
            "goal": "搜索Python",
            "steps": [{"action": "搜索Python", "tool": "web_search", "params": {"query": "Python"}}]
        }

        report = engine.execute_task_plan(plan)
        self.assertIsInstance(report, str)
        self.assertTrue(len(report) > 0)

    def test_execute_with_failed_tool(self):
        """包含失败工具步骤的任务计划"""
        reg = make_registry()
        engine = make_engine(reg, "报告内容")

        plan = {
            "goal": "测试失败",
            "steps": [
                {"action": "搜索", "tool": "web_search", "params": {"query": "test"}},
                {"action": "失败步骤", "tool": "fail_tool", "params": {}},
            ]
        }

        report = engine.execute_task_plan(plan)
        self.assertIsInstance(report, str)
        self.assertTrue(len(report) > 0)


class TestAnalyzeIntent(unittest.TestCase):
    """测试意图分析"""

    def test_valid_json_response(self):
        """LLM 返回有效 JSON 应正确解析"""
        reg = make_registry()
        response = '{"needs_agent": true, "reason": "需要搜索", "task_plan": {"goal": "搜索", "steps": []}}'
        engine = make_engine(reg, response)

        result = engine._analyze_intent("搜索Python", [])
        self.assertTrue(result["needs_agent"])

    def test_malformed_json_fallback(self):
        """LLM 返回无效 JSON 应回退"""
        reg = make_registry()
        engine = make_engine(reg, "这不是JSON")

        result = engine._analyze_intent("测试", [])
        self.assertFalse(result["needs_agent"])
        self.assertIn("JSON 解析失败", result["reason"])

    def test_json_embedded_in_text(self):
        """LLM 返回文本中嵌入 JSON 也应正确提取"""
        reg = make_registry()
        response = '这是分析结果：\n```json\n{"needs_agent": false, "response": "直接回答"}\n```'
        engine = make_engine(reg, response)

        result = engine._analyze_intent("简单问题", [])
        self.assertFalse(result["needs_agent"])
        self.assertEqual(result["response"], "直接回答")


class TestCallAI(unittest.TestCase):
    """测试 _call_ai 底层调用"""

    def test_client_none_raises(self):
        """client_getter 返回 None 应抛 RuntimeError"""
        reg = make_registry()
        engine = AgentEngine(
            client_getter=lambda: None,
            tool_registry=reg,
        )
        with self.assertRaises(RuntimeError):
            engine._call_ai([{"role": "user", "content": "test"}])

    def test_empty_choices_returns_empty(self):
        """API 返回空 choices 应返回空字符串"""
        reg = make_registry()
        mock_client = MagicMock()
        mock_client.chat_completions.return_value = {"choices": []}
        engine = AgentEngine(
            client_getter=lambda mc=mock_client: mc,
            tool_registry=reg,
        )
        result = engine._call_ai([{"role": "user", "content": "test"}])
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()

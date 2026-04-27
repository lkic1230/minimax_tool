"""对话领域 API。"""
from typing import Any, Dict, List


class ChatDomainMixin:
    """文本对话相关方法。"""

    def chat_completions(
        self,
        messages: List[Dict[str, str]],
        model: str = "MiniMax-M2.7",
        stream: bool = False,
        max_completion_tokens: int = None,
        temperature: float = None,
        top_p: float = None,
        timeout: int = 120,
    ) -> Dict[str, Any]:
        supported_models = {"MiniMax-M2.7", "MiniMax-M2.7-highspeed", "MiniMax-M2.5", "MiniMax-M2.1"}
        if model not in supported_models:
            raise ValueError(f"不支持的对话模型: {model}")
        if not messages or not isinstance(messages, list):
            raise ValueError("messages 不能为空，且必须为列表")

        data = {"model": model, "messages": messages, "stream": stream}

        if max_completion_tokens is not None:
            if not (1 <= max_completion_tokens <= 2048):
                raise ValueError("max_completion_tokens 取值范围为 1-2048")
            data["max_completion_tokens"] = max_completion_tokens
        if temperature is not None:
            if not (0 < temperature <= 1):
                raise ValueError("temperature 取值范围为 (0, 1]")
            data["temperature"] = temperature
        if top_p is not None:
            if not (0 < top_p <= 1):
                raise ValueError("top_p 取值范围为 (0, 1]")
            data["top_p"] = top_p

        return self._post("/v1/chat/completions", data, timeout=timeout)


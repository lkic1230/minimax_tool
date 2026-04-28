"""对话领域 API。"""
from typing import Any, Dict, List

from ...core.constants import (
    CHAT_MODELS,
    CHAT_MODEL_DEFAULT,
    CHAT_MAX_TOKENS_MIN,
    CHAT_MAX_TOKENS_MAX,
)


class ChatDomainMixin:
    """文本对话相关方法。"""

    def chat_completions(
        self,
        messages: List[Dict[str, str]],
        model: str = CHAT_MODEL_DEFAULT,
        stream: bool = False,
        max_completion_tokens: int = None,
        temperature: float = None,
        top_p: float = None,
        timeout: int = 120,
    ) -> Dict[str, Any]:
        if model not in CHAT_MODELS:
            raise ValueError(f"不支持的对话模型: {model}")
        if not messages or not isinstance(messages, list):
            raise ValueError("messages 不能为空，且必须为列表")

        data = {"model": model, "messages": messages, "stream": stream}

        if max_completion_tokens is not None:
            if not (CHAT_MAX_TOKENS_MIN <= max_completion_tokens <= CHAT_MAX_TOKENS_MAX):
                raise ValueError(
                    f"max_completion_tokens 取值范围为 {CHAT_MAX_TOKENS_MIN}-{CHAT_MAX_TOKENS_MAX}"
                )
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

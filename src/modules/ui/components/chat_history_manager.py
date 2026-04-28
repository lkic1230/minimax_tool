"""
对话历史管理器：保存/加载/删除对话记录。
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


class ChatHistoryManager:
    """对话历史的 CRUD 管理器，存储在本地 JSON 文件中。"""

    def __init__(self, cache_dir: str = None):
        if cache_dir:
            self._dir = Path(cache_dir)
        else:
            self._dir = Path.home() / ".minimax_tool" / "chat_history"
        self._dir.mkdir(parents=True, exist_ok=True)

    # ==================== 核心操作 ====================

    def save(self, title: str, messages: List[Dict[str, str]],
             model: str, max_tokens: int, temperature: float,
             top_p: float, system_prompt: str = "",
             conv_id: Optional[str] = None) -> str:
        """
        保存一条对话记录，返回 conversation_id。
        传入 conv_id 时覆盖原记录，否则创建新记录。
        """
        conv_id = conv_id or str(uuid.uuid4())[:8]
        created_at = datetime.now().isoformat()
        old_entry = self.load(conv_id)
        if old_entry and old_entry.get("created_at"):
            created_at = old_entry["created_at"]
        entry = {
            "id": conv_id,
            "title": title or (messages[0]["content"][:30] + "..." if messages else "新对话"),
            "messages": messages,
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "system_prompt": system_prompt or "",
            "created_at": created_at,
            "updated_at": datetime.now().isoformat(),
        }
        path = self._conv_path(conv_id)
        path.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
        return conv_id

    def load(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 加载对话记录，找不到返回 None。"""
        path = self._conv_path(conversation_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return None

    def delete(self, conversation_id: str) -> bool:
        """删除指定对话记录，成功返回 True。"""
        path = self._conv_path(conversation_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def rename(self, conversation_id: str, new_title: str) -> bool:
        """重命名指定对话记录，成功返回 True。"""
        title = (new_title or "").strip()
        if not title:
            return False
        entry = self.load(conversation_id)
        if not entry:
            return False
        entry["title"] = title
        entry["updated_at"] = datetime.now().isoformat()
        path = self._conv_path(conversation_id)
        try:
            path.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
            return True
        except IOError:
            return False

    def list_all(self) -> List[Dict[str, Any]]:
        """
        返回所有对话记录列表，按 updated_at 倒序排列。
        只返回摘要信息（不含 messages），避免大文件开销。
        """
        entries = []
        for path in self._dir.glob("*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                # 剔除 messages 字段，仅保留摘要
                summary = {k: v for k, v in raw.items() if k != "messages"}
                summary["message_count"] = len(raw.get("messages", []))
                entries.append(summary)
            except (json.JSONDecodeError, IOError):
                continue
        entries.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return entries

    # ==================== 辅助 ====================

    def _conv_path(self, conv_id: str) -> Path:
        return self._dir / f"{conv_id}.json"

    def _generate_title(self, messages: List[Dict[str, str]]) -> str:
        """从第一条用户消息提取标题。"""
        for msg in messages:
            if msg.get("role") == "user":
                content = msg["content"].strip()
                return content[:40] + ("..." if len(content) > 40 else "")
        return "新对话"

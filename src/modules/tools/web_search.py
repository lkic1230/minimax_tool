"""
Web Search Tool - 联网搜索工具。

使用 duckduckgo_search 库进行真正的网页搜索（非 Instant Answer API）。
"""
from typing import Any, Dict, List

from ..agent.tool_framework import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    """联网搜索工具（DuckDuckGo）"""

    name = "web_search"
    description = "使用 DuckDuckGo 搜索引擎查询信息，返回结果列表和链接"

    parameters_schema = {
        "query": {"type": "string", "required": True, "description": "搜索关键词"},
        "max_results": {"type": "int", "default": 5, "description": "最大结果数"},
    }

    def validate(self, params: Dict[str, Any]) -> bool:
        """校验参数"""
        if "query" not in params or not params["query"]:
            return False
        return True

    def execute(self, **kwargs) -> ToolResult:
        """执行搜索"""
        query = kwargs.get("query", "")
        max_results = min(kwargs.get("max_results", 5), 10)

        try:
            results = self._search(query, max_results)
            return ToolResult(
                success=True,
                data={"results": results, "query": query, "count": len(results)},
                metadata={"engine": "duckduckgo", "max_results": max_results},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"搜索失败: {e}")

    def _search(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """使用 ddgs (DuckDuckGo Search) 执行真正的网页搜索"""
        from ddgs import DDGS

        results = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("href", ""),
                    "snippet": item.get("body", ""),
                })

        return results


class BraveSearchTool(BaseTool):
    """Brave Search API 工具 (可选)"""
    
    name = "brave_search"
    description = "使用 Brave Search API 进行搜索"
    
    parameters_schema = {
        "query": {"type": "string", "required": True},
        "api_key": {"type": "string", "required": True},
        "max_results": {"type": "int", "default": 5}
    }

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.api_url = "https://api.search.brave.com/res/v1/web/search"
        
    def validate(self, params: Dict[str, Any]) -> bool:
        if "query" not in params:
            return False
        if self.api_key and "api_key" not in params:
            params["api_key"] = self.api_key
        return True
        
    def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "")
        max_results = min(kwargs.get("max_results", 5), 20)
        api_key = kwargs.get("api_key", self.api_key)
        
        if not api_key:
            return ToolResult(success=False, error="需要 API key")
            
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": api_key
        }
        
        params = {
            "q": query,
            "count": max_results
        }
        
        try:
            response = requests.get(
                self.api_url,
                headers=headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("web", {}).get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", "")
                })
                
            return ToolResult(
                success=True,
                data={"results": results, "query": query},
                metadata={"engine": "brave"}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
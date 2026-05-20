"""
Web Search Tool - 联网搜索工具。

优先使用 Bing 搜索（国内可直接访问，无 API Key 要求）。
备用 DuckDuckGo（需要代理）。
"""
from typing import Any, Dict, List
import re
import requests

from ..agent.tool_framework import BaseTool, ToolResult


# 搜索结果解析器 - Bing 网页版
def _parse_bing_html(html: str, max_results: int) -> List[Dict[str, str]]:
    """从 Bing 搜索结果页面解析结果"""
    results = []
    # Bing 结果在 li 元素的 h2>a 中
    # 匹配: <li class="b_algo"><h2><a href="URL">标题</a>
    pattern = r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>.*?<h2>.*?<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
    matches = re.findall(pattern, html, re.DOTALL)
    for url, title in matches[:max_results]:
        url = url.split('&')[0]  # 去掉追踪参数
        title = re.sub(r'<[^>]+>', '', title)  # 去掉 HTML 标签
        title = title.strip()
        if url and title:
            results.append({
                "title": title,
                "url": url,
                "snippet": "",  # Bing 页面不直接提供 snippet，需要二次抓取
            })
    return results


class WebSearchTool(BaseTool):
    """联网搜索工具（优先 Bing，DuckDuckGo 备用）"""

    name = "web_search"
    description = "使用 Bing/DuckDuckGo 搜索引擎查询信息，返回结果列表和链接"

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

        # 先尝试 Bing
        try:
            results = self._search_bing(query, max_results)
            if results:
                return ToolResult(
                    success=True,
                    data={"results": results, "query": query, "count": len(results)},
                    metadata={"engine": "bing"},
                )
        except Exception as e:
            pass  # Bing 失败，继续尝试 DuckDuckGo

        # 备用：DuckDuckGo（仅当 Bing 失败时）
        try:
            results = self._search_duckduckgo(query, max_results)
            return ToolResult(
                success=True,
                data={"results": results, "query": query, "count": len(results)},
                metadata={"engine": "duckduckgo"},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"搜索失败: {e}")

    def _search_bing(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """使用 Bing 网页搜索"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        url = f"https://www.bing.com/search?q={requests.utils.quote(query)}&PC=U316"
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return _parse_bing_html(response.text, max_results)

    def _search_duckduckgo(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """使用 DuckDuckGo 搜索（备用）"""
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
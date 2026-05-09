"""
Web Scrape Tool - 网页抓取工具。

抓取指定 URL 的网页正文内容。
"""
from typing import Any, Dict, List
from urllib.parse import urlparse
import re

import requests
from bs4 import BeautifulSoup

from ..agent.tool_framework import BaseTool, ToolResult


class WebScrapeTool(BaseTool):
    """网页抓取工具"""
    
    name = "web_scrape"
    description = "抓取指定URL的网页正文内容"
    
    parameters_schema = {
        "url": {"type": "string", "required": True, "description": "目标URL"},
        "options": {"type": "dict", "default": {}, "description": "抓取选项"}
    }
    
    # 常见反爬虫域名
    BLOCKED_DOMAINS = [
        "google.com",
        "facebook.com", 
        "twitter.com",
        "instagram.com",
        "tiktok.com"
    ]

    def __init__(self):
        self.timeout = 30
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def validate(self, params: Dict[str, Any]) -> bool:
        """校验参数"""
        if "url" not in params:
            return False
        
        url = params["url"]
        if not url.startswith(("http://", "https://")):
            return False
            
        # 检查域名是否被阻止
        domain = urlparse(url).netloc.lower()
        for blocked in self.BLOCKED_DOMAINS:
            if blocked in domain:
                return False
                
        return True

    def execute(self, **kwargs) -> ToolResult:
        """执行抓取"""
        url = kwargs.get("url", "")
        
        try:
            content = self._scrape(url)
            return ToolResult(
                success=True,
                data={
                    "url": url,
                    "content": content["text"],
                    "title": content.get("title", ""),
                    "links": content.get("links", [])
                },
                metadata={
                    "fetched_at": content.get("fetched_at", ""),
                    "word_count": len(content.get("text", ""))
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _scrape(self, url: str) -> Dict[str, Any]:
        """抓取网页"""
        response = requests.get(url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        # 移除脚本和样式
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
            
        # 获取标题
        title = ""
        if soup.title:
            title = soup.title.string or ""
            
        # 获取正文
        text = ""
        article = soup.find("article") or soup.find("main") or soup.find("div", class_=re.compile("content|article|post"))
        if article:
            text = article.get_text(separator="\n", strip=True)
        else:
            body = soup.body
            if body:
                text = body.get_text(separator="\n", strip=True)
                
        # 清理文本
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text = "\n".join(lines[:500])  # 限制行数
        
        # 获取链接
        links = []
        for a in soup.find_all("a", href=True)[:20]:
            href = a.get("href", "")
            if href.startswith(("http://", "https://")):
                links.append({"text": a.get_text(strip=True)[:100], "url": href})
                
        from datetime import datetime
        return {
            "text": text[:10000],  # 限制长度
            "title": title[:200],
            "links": links,
            "fetched_at": datetime.now().isoformat()
        }


class TrafilaturaTool(BaseTool):
    """使用 trafilatura 库的增强抓取工具 (可选)"""
    
    name = "trafilatura_scrape"
    description = "使用 trafilatura 库进行高质量正文提取"
    
    def __init__(self):
        self.timeout = 30
        
    def validate(self, params: Dict[str, Any]) -> bool:
        return "url" in params and params["url"].startswith(("http://", "https://"))
        
    def execute(self, **kwargs) -> ToolResult:
        url = kwargs.get("url", "")
        
        try:
            import trafilatura
            
            result = trafilatura.fetch_url(url)
            if not result:
                return ToolResult(success=False, error="无法获取内容")
                
            extracted = trafilatura.extract(
                result,
                include_links=True,
                include_comments=False
            )
            
            return ToolResult(
                success=True,
                data={"content": extracted, "url": url},
                metadata={"engine": "trafilatura"}
            )
        except ImportError:
            return ToolResult(success=False, error="需要安装 trafilatura: pip install trafilatura")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
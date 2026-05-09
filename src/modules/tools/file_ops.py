"""
File Tools - 文件操作工具。

提供安全的本地文件读写能力（受限于白名单目录）。
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..agent.tool_framework import BaseTool, ToolResult


class FileToolBase(BaseTool):
    """文件工具基类 - 提供安全检查"""
    
    # 白名单目录 (相对于项目根目录)
    ALLOWED_DIRECTORIES = [
        "outputs",
        "workspace",
        "cache",
    ]
    
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir
        
    def _get_allowed_paths(self) -> List[Path]:
        """获取允许访问的目录列表"""
        if not self.base_dir:
            return []
            
        base = Path(self.base_dir).resolve()
        paths = []
        
        for sub in self.ALLOWED_DIRECTORIES:
            path = base / sub
            if path.exists():
                paths.append(path.resolve())
                
        return paths
        
    def _is_allowed(self, file_path: str) -> bool:
        """检查路径是否在允许范围内"""
        allowed_paths = self._get_allowed_paths()
        if not allowed_paths:
            return True  # 如果没有配置base_dir，默认允许
            
        try:
            target = Path(file_path).resolve()
            for allowed in allowed_paths:
                try:
                    target.relative_to(allowed)
                    return True
                except ValueError:
                    continue
            return False
        except Exception:
            return False
            
    def validate(self, params: Dict[str, Any]) -> bool:
        """基础校验"""
        if "path" not in params:
            return False
        return self._is_allowed(params["path"])


class FileReadTool(FileToolBase):
    """文件读取工具"""
    
    name = "file_read"
    description = "读取指定文件的内容（仅限白名单目录）"
    
    parameters_schema = {
        "path": {"type": "string", "required": True, "description": "文件路径"},
        "encoding": {"type": "string", "default": "utf-8", "description": "文件编码"},
        "max_lines": {"type": "int", "default": 1000, "description": "最大行数"}
    }

    def __init__(self, base_dir: str = ""):
        super().__init__(base_dir)
        self.name = "file_read"
        
    def execute(self, **kwargs) -> ToolResult:
        """读取文件"""
        path = kwargs.get("path", "")
        encoding = kwargs.get("encoding", "utf-8")
        max_lines = kwargs.get("max_lines", 1000)
        
        if not self._is_allowed(path):
            return ToolResult(
                success=False,
                error=f"路径不在允许范围内: {path}"
            )
            
        try:
            file_path = Path(path)
            
            if not file_path.exists():
                return ToolResult(success=False, error="文件不存在")
                
            if not file_path.is_file():
                return ToolResult(success=False, error="不是文件")
                
            # 读取内容
            with open(file_path, "r", encoding=encoding) as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line.rstrip("\n"))
                    
            content = "\n".join(lines)
            line_count = len(lines)
            
            return ToolResult(
                success=True,
                data={
                    "path": str(file_path),
                    "content": content,
                    "lines": line_count,
                    "truncated": line_count >= max_lines
                },
                metadata={
                    "size": file_path.stat().st_size,
                    "encoding": encoding
                }
            )
        except UnicodeDecodeError:
            return ToolResult(success=False, error=f"无法使用 {encoding} 解码，尝试 binary 模式")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileWriteTool(FileToolBase):
    """文件写入工具"""
    
    name = "file_write"
    description = "写入内容到文件（仅限白名单目录）"
    
    parameters_schema = {
        "path": {"type": "string", "required": True, "description": "目标文件路径"},
        "content": {"type": "string", "required": True, "description": "写入内容"},
        "encoding": {"type": "string", "default": "utf-8", "description": "文件编码"},
        "append": {"type": "bool", "default": False, "description": "是否追加"}
    }

    def __init__(self, base_dir: str = ""):
        super().__init__(base_dir)
        self.name = "file_write"
        
    def execute(self, **kwargs) -> ToolResult:
        """写入文件"""
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")
        encoding = kwargs.get("encoding", "utf-8")
        append = kwargs.get("append", False)
        
        if not self._is_allowed(path):
            return ToolResult(
                success=False,
                error=f"路径不在允许范围内: {path}"
            )
            
        if not content:
            return ToolResult(success=False, error="内容为空")
            
        try:
            file_path = Path(path)
            
            # 创建父目录
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入模式
            mode = "a" if append else "w"
            
            with open(file_path, mode, encoding=encoding) as f:
                f.write(content)
                
            return ToolResult(
                success=True,
                data={
                    "path": str(file_path),
                    "bytes_written": len(content.encode(encoding)),
                    "mode": "append" if append else "overwrite"
                },
                metadata={"encoding": encoding}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileListTool(FileToolBase):
    """文件列表工具"""
    
    name = "file_list"
    description = "列出目录中的文件"
    
    parameters_schema = {
        "path": {"type": "string", "required": True, "description": "目录路径"},
        "pattern": {"type": "string", "default": "*", "description": "文件匹配模式"},
        "recursive": {"type": "bool", "default": False, "description": "是否递归"}
    }

    def __init__(self, base_dir: str = ""):
        super().__init__(base_dir)
        self.name = "file_list"
        
    def validate(self, params: Dict[str, Any]) -> bool:
        if "path" not in params:
            return False
        return True  # 列表操作不做强制限制
            
    def execute(self, **kwargs) -> ToolResult:
        """列出文件"""
        path = kwargs.get("path", ".")
        pattern = kwargs.get("pattern", "*")
        recursive = kwargs.get("recursive", False)
        
        try:
            dir_path = Path(path)
            
            if not dir_path.exists():
                return ToolResult(success=False, error="目录不存在")
                
            if recursive:
                files = list(dir_path.rglob(pattern))
            else:
                files = list(dir_path.glob(pattern))
                
            # 过滤只保留文件
            files = [f for f in files if f.is_file()]
            
            results = []
            for f in files[:100]:  # 限制数量
                results.append({
                    "name": f.name,
                    "path": str(f),
                    "size": f.stat().st_size
                })
                
            return ToolResult(
                success=True,
                data={
                    "path": str(dir_path),
                    "files": results,
                    "count": len(results)
                },
                metadata={"pattern": pattern, "recursive": recursive}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
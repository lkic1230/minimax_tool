"""
P0 Agent CLI - 快速测试工具。
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.modules.agent.tool_framework import ToolRegistry, ToolExecutor
from src.modules.agent.task_manager import TaskManager, TaskStatus
from src.modules.tools.web_search import WebSearchTool
from src.modules.tools.web_scrape import WebScrapeTool
from src.modules.tools.file_ops import FileReadTool, FileWriteTool


def main():
    """CLI 入口"""
    if len(sys.argv) < 2:
        print("用法: python cli_agent.py <命令> [参数]")
        print("命令:")
        print("  search <关键词>     - 联网搜索")
        print("  scrape <URL>     - 网页抓取")
        print("  read <文件路径>   - 读取文件")
        print("  write <路径> <内容> - 写入文件")
        print("  task create <目标> - 创建任务")
        print("  task list         - 列出任务")
        return

    cmd = sys.argv[1]
    
    # 初始化工具
    registry = ToolRegistry()
    registry.register(WebSearchTool())
    registry.register(WebScrapeTool())
    registry.register(FileReadTool())
    registry.register(FileWriteTool())
    executor = ToolExecutor(registry)
    task_manager = TaskManager()

    if cmd == "search":
        if len(sys.argv) < 3:
            print("用法: python cli_agent.py search <关键词>")
            return
        query = sys.argv[2]
        result = executor.execute("web_search", {"query": query, "max_results": 5})
        if result.success:
            print(f"✅ 搜索成功: {len(result.data.get('results', []))} 条结果")
            for i, r in enumerate(result.data.get("results", [])[:3], 1):
                print(f"  {i}. {r.get('title', '')}")
                print(f"     {r.get('url', '')}")
        else:
            print(f"❌ 搜索失败: {result.error}")

    elif cmd == "scrape":
        if len(sys.argv) < 3:
            print("用法: python cli_agent.py scrape <URL>")
            return
        url = sys.argv[2]
        result = executor.execute("web_scrape", {"url": url})
        if result.success:
            content = result.data.get("content", "")[:200]
            print(f"✅ 抓取成功: {len(content)} 字符")
            print(content)
        else:
            print(f"❌ 抓取失败: {result.error}")

    elif cmd == "task":
        if len(sys.argv) < 3:
            print("用法: python cli_agent.py task <create|list>")
            return
        subcmd = sys.argv[2]
        if subcmd == "create":
            goal = sys.argv[3] if len(sys.argv) > 3 else "测试任务"
            task = task_manager.create_task(goal)
            print(f"✅ 任务创建: {task.id}")
            print(f"   目标: {task.goal}")
        elif subcmd == "list":
            tasks = task_manager.list_tasks()
            print(f"📋 任务列表: {len(tasks)} 个")
            for t in tasks:
                print(f"  - {t.id[:8]}... {t.goal} [{t.status.value}]")

    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    main()
# 测试说明

本目录用于存放 `unittest` 用例。

## 运行方式

```bash
python -m unittest discover -s minimax_tool/tests -p "test_*.py" -v
```

## 执行前确认清单（单人维护版）

1. 确认当前代码变更与测试覆盖范围一致，不直接沿用旧断言。
2. 若距上次确认超过一个版本迭代，先人工抽查关键逻辑再跑全量测试。
3. 若新增/修改聊天核心逻辑，同步补充对应测试并更新下方“用例创建时间”。

## 聊天相关用例创建时间

| 用例文件 | 主要覆盖点 | 创建时间 | 最近人工确认 |
|---|---|---|---|
| `minimax_tool/tests/test_chat_markdown_processing.py` | Markdown 复制语义、`<think>` 清洗边界 | 2026-04-29 | 2026-04-29 |
| `minimax_tool/tests/test_chat_history_manager.py` | 对话 ID 生成、标题兜底、冲突重试 | 2026-04-29 | 2026-04-29 |
| `minimax_tool/tests/test_config_manager_security.py` | 设备多因子匹配、重绑策略、API Key 重绑恢复 | 2026-04-29 | 2026-04-29 |
| `minimax_tool/tests/test_app_meta.py` | 应用名称/版本配置加载（app_config.json） | 2026-04-29 | 2026-04-29 |

> 维护建议：每次跨版本升级后，先更新“最近人工确认”日期，再执行测试。

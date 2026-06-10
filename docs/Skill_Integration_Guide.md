# Skill Integration Guide

版本：v0.1  
状态：边界规范  
适用范围：Claude Skill、Context7、PDF Skill、Sequential Thinking、GitHub MCP

## 1. 核心原则

Scientra Copilot 必须在脱离 Claude 生态后仍可独立运行。

Claude Skill、Context7、PDF Skill、Sequential Thinking、GitHub MCP 只能作为开发辅助工具，不得成为 Scientra Copilot 的核心依赖、运行时依赖或数据处理链路依赖。

## 2. 允许用途

以下工具只允许用于开发期、调试期和维护期：

| 工具 | 允许用途 |
| --- | --- |
| Claude Skill | 开发辅助、文档草拟、Prompt 优化、故障排查 |
| Context7 | 查询第三方库文档、辅助确认 API 用法、开发调试 |
| PDF Skill | 开发期 PDF 样本分析、解析策略调试、人工验证 |
| Sequential Thinking | 架构推演、问题拆解、故障定位、Prompt 优化 |
| GitHub MCP | 查看仓库、Issue、代码参考、开发期变更辅助 |

允许场景：

- 开发 Scientra Copilot 代码。
- 调试 Engine、API、Workflow 的异常。
- 优化 Summary Engine Prompt。
- 分析失败日志和错误报告。
- 查阅第三方库文档。
- 辅助撰写 docs。
- 辅助设计测试用例。

## 3. 禁止用途

以下行为一律禁止：

- 禁止作为 Scientra Copilot 核心依赖。
- 禁止作为 Scientra Copilot 运行时依赖。
- 禁止参与数据库存储。
- 禁止参与向量检索。
- 禁止参与 Metadata 生成。
- 禁止参与 Tag 生成。
- 禁止 Agent 通过 Skill/MCP 绕过 `literature_query()`。
- 禁止 Skill/MCP 直接读写 SQLite。
- 禁止 Skill/MCP 直接读写 LanceDB。
- 禁止 Skill/MCP 直接修改 `tags.yaml`。
- 禁止 Skill/MCP 直接修改 `metadata.yaml`。
- 禁止 Skill/MCP 将 PDF 处理结果直接注入知识层。

## 4. 运行时隔离

Scientra Copilot 运行时允许依赖：

- Python 3.11+
- SQLite
- LanceDB
- FastAPI
- Typer
- Loguru
- PyYAML
- BGE-M3
- GROBID
- DeepSeek V4 Pro 用于 Summary Engine

Scientra Copilot 运行时禁止依赖：

- Claude Code
- Claude Skill
- Context7
- PDF Skill
- Sequential Thinking
- GitHub MCP
- 任意 MCP Server
- 任意 Claude 专属运行环境

## 5. 数据边界

数据链路必须保持：

```text
PDF
-> Parse
-> Metadata
-> Tag
-> Summary
-> Embedding
-> LanceDB
-> Index Update
-> Literature API
-> Agent
```

Skill/MCP 不得插入以下环节：

- Metadata Engine
- Tag Engine
- Embedding Engine
- LanceDB 检索
- SQLite 写入
- Agent 查询入口

Skill/MCP 可以在开发期辅助观察、解释和调试这些环节，但不能成为这些环节的一部分。

## 6. Agent 接入规则

所有 Agent 必须统一调用：

```python
literature_query()
```

或通过 Scientra Copilot API：

```text
POST /v1/scientra/query
```

Agent 禁止：

- 直接访问 PDF。
- 直接访问 SQLite。
- 直接访问 LanceDB。
- 直接调用 Claude Skill 获取 Scientra Copilot 内部知识。
- 直接调用 GitHub MCP、PDF Skill 或其他 MCP 作为检索替代。

## 7. Prompt 优化边界

Sequential Thinking、Claude Skill、Context7 可用于 Summary Engine 的 Prompt 优化，但必须遵守：

- Prompt 可以由开发者更新到代码或配置中。
- Summary Engine 运行时不得依赖这些工具。
- Prompt 优化记录应进入 docs 或变更记录。
- Prompt 优化不得改变 Metadata Engine 和 Tag Engine 的非 LLM 边界。

## 8. 故障排查边界

Skill/MCP 可用于故障排查，但只能读取开发者显式提供的日志、报告或错误片段。

允许读取：

- `07_Workflows/logs/`
- `07_Workflows/reports/`
- 失败 JSONL 片段
- 测试输出
- 开发者明确提供的样本

禁止直接修改：

- `02_Metadata/metadata.yaml`
- `05_Index/tags/*/tags.yaml`
- SQLite 数据库
- LanceDB 数据目录
- Summary 缓存

## 9. 独立运行验收标准

Scientra Copilot 脱离 Claude 生态后，必须仍然能够完成：

1. PDF 导入。
2. GROBID 解析。
3. Metadata 生成。
4. Tag 生成。
5. Summary 生成。
6. BGE-M3 Embedding。
7. LanceDB 写入和检索。
8. Workflow 运行。
9. FastAPI 服务启动。
10. Agent 通过 `literature_query()` 查询。

如果移除 Claude Skill、Context7、PDF Skill、Sequential Thinking、GitHub MCP 后任一核心功能无法运行，则视为架构违规。

## 10. 结论

Skill/MCP 是开发辅助层，不是 Scientra Copilot 的系统层。

最终边界：

```text
Skill / MCP = 开发、调试、Prompt 优化、故障排查
Scientra Copilot = 独立运行的文献知识操作系统
Agent = 通过 literature_query() 消费知识
```

任何未来扩展都必须保持该边界。


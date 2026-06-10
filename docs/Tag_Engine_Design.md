# Tag Engine Design

版本：v0.1  
状态：实现基线  
边界：默认不调用 LLM，默认不重新生成 embedding

## 1. 目标

Tag Engine 负责对已解析文献进行自动标签化。

Tag Engine 只处理标签，不负责：

- PDF 解析
- Summary 生成
- Chunk 切分
- Embedding 生成
- Agent 决策

## 2. 核心原则

1. 标签体系不写死在代码中。
2. 标签体系由 `Config/tag_ontology.yaml` 定义。
3. 标签词典由 `Config/tag_dictionary.yaml` 定义。
4. 新增标签时，只需更新 ontology 和 dictionary。
5. 历史文献可通过 retag 命令重新分配标签。
6. 默认不调用 LLM。
7. 默认不重新生成 embedding。
8. Tag Engine 只更新标签相关产物。
9. Agent 禁止直接修改 `tags.yaml`，必须通过 Tag Engine。

## 3. 配置文件

`Config/tag_ontology.yaml` 定义标签分类和允许出现的标签。

`Config/tag_dictionary.yaml` 定义每个标签的：

- `synonyms`
- `include_patterns`
- `exclude_patterns`
- `weight`
- `min_score`

Tag Engine 只会分配 ontology 中存在、dictionary 中有效配置的标签。

## 4. 输入优先级

Tag Engine 会从以下来源读取文本，并按权重参与匹配：

1. `title`
2. `abstract`
3. `summary.md`
4. `raw_text`
5. `chunks`

默认路径：

- `02_Metadata/yaml/*.metadata.yaml`
- `02_Metadata/papers/*.metadata.json`
- `03_Summary/raw_text/*.txt`
- `03_Summary/<paper_id>/summary.md`
- `03_Summary/chunks/<paper_id>/`

## 5. 输出

每篇文献输出：

```text
05_Index/tags/<paper_id>/tags.yaml
```

格式：

```yaml
paper_id: paper_x
paper_key: paper_x
tag_schema_version: 2026-06-08.v1
tag_dictionary_version: 2026-06-08.v1
tag_engine_version: 0.1.0
assigned_tags:
  MECHANISM:
    - PM
evidence:
  PM:
    matched_terms:
      - peritrophic membrane
    source:
      - abstract
    score: 3.0
llm_used: false
summary_regenerated: false
embedding_regenerated: false
```

## 6. 版本管理

每次标签分配记录：

- `tag_schema_version`
- `tag_dictionary_version`
- `tag_engine_version`
- `tag_schema_hash`
- `tag_dictionary_hash`
- `source_hash`

`--changed-only` 使用这些字段判断是否需要重新打标签。即使版本号没有更新，只要配置文件内容变化，配置哈希也会变化，从而触发 retag。

## 7. Retag 命令

支持：

```powershell
python -m scientra.Scripts.retag --all
python -m scientra.Scripts.retag --category MECHANISM
python -m scientra.Scripts.retag --tag PM
python -m scientra.Scripts.retag --all --changed-only
```

也支持直接运行：

```powershell
python G:\AI_agent\Scientra Copilot\Scripts\retag.py --all
```

## 8. 重新打标签规则

如果只修改 `tag_ontology.yaml` 或 `tag_dictionary.yaml`：

- 只重新分配标签。
- 默认更新 `tags.yaml`。
- 如果 SQLite 存在，更新 SQLite 标签表。
- 如果 LanceDB 存在且可用，尝试更新 LanceDB metadata。

默认不重新：

- PDF 解析
- Summary 生成
- Chunk 切分
- Embedding 生成

只有以下情况才允许其他系统重新 embedding：

- `raw_text` 改变
- `summary` 改变
- `chunk` 改变
- `embedding_model` 改变

Tag Engine 不执行 embedding。

## 9. 报告

每次 retag 后生成：

```text
07_Workflows/reports/retag_report.md
```

报告包含：

1. 本次使用的 ontology 版本
2. 本次使用的 dictionary 版本
3. 处理文献数量
4. 每个标签命中文献数量
5. 新增标签命中文献列表
6. 标签变化统计
7. 未命中文献列表
8. 错误文献列表

## 10. Agent 边界

Agent 是标签消费方，不是标签写入方。

Agent 禁止：

- 直接修改 `tags.yaml`
- 直接改 SQLite 标签表
- 直接改 LanceDB tag metadata
- 自由生成 ontology 之外的标签

Agent 必须通过 Scientra Copilot API 或 Tag Engine 提供的受控入口读取标签。


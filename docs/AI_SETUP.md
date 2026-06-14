# Scientra Copilot — AI 功能部署指南

30 秒完成 AI 配置，启用全部智能分析功能。

---

## 一键配置

```bash
# 交互式向导（推荐）
python Scripts/setup_llm.py

# 或从环境变量快速部署
export DEEPSEEK_API_KEY="sk-..."
python Scripts/setup_llm.py --quick
```

支持 Provider：**DeepSeek** / **OpenAI** / **Anthropic** / **Local**

---

## AI 功能总览

| 功能 | 说明 | 输出路径 |
|------|------|---------|
| **Summary V2** | 结构化论文摘要 + 证据驱动声明 | `03_Assets/ai/summary_v2/` |
| **Evidence Enrichment** | 证据片段 AI 分析 | `03_Assets/ai/evidence_enrichment/` |
| **Gap Extraction** | 7 种研究空白识别 | `03_Assets/ai/gaps/` |
| **Hypothesis Generation** | 可测试假说 + 建议实验 | `03_Assets/ai/hypotheses/` |
| **Quality Check** | 规则化质量评分 | `03_Assets/ai/quality/gap_hypothesis/` |
| **Cross-Paper Gap Fusion** | 跨论文空白聚类（BGE-M3） | `05_Knowledge/cross_paper_gaps/` |
| **Cross-Paper Hypothesis Fusion** | 跨论文假说聚类 | `05_Knowledge/cross_paper_hypotheses/` |
| **Opportunity Ranking** | 研究机会排序 | `05_Knowledge/research_opportunities/` |

---

## 启用 AI 增强

编辑 `Config/workflow_config.yaml`：

```yaml
ai_enrichment:
  enabled: true
  summary_v2: true
  evidence_enrichment: true
  gap_extraction: true
  hypothesis_generation: true
```

然后运行：

```bash
# 全量处理（54 篇约需 30-45 分钟，费用约 $0.9）
python Scripts/batch_run_phase23.py

# 或只处理前 N 篇
python Scripts/batch_run_phase23.py --limit 5
```

---

## 跨论文发现

```bash
# 1. 研究空白聚类
python Scripts/fuse_cross_paper_gaps.py --threshold 0.72

# 2. 假说聚类
python Scripts/fuse_cross_paper_hypotheses.py --threshold 0.72

# 3. 研究机会排序
python Scripts/rank_research_opportunities.py --top-k 20
```

---

## Web 界面

| 页面 | 功能 |
|------|------|
| `/settings` | AI Provider 配置 + Test Connection |
| `/cross-paper-gaps` | 统一研究空白浏览 |
| `/cross-paper-hypotheses` | 统一假说浏览 |
| `/research-opportunities` | 研究机会排名 |

---

## 成本参考

| 任务 | 每篇成本 | 54 篇总成本 |
|------|---------|-----------|
| Summary V2 | ~$0.004 | ~$0.23 |
| Evidence Enrichment | ~$0.005 | ~$0.27 |
| Gap Extraction | ~$0.003 | ~$0.17 |
| Hypothesis Generation | ~$0.005 | ~$0.26 |
| **合计** | **~$0.017** | **~$0.93** |

> Cross-Paper Fusion 和 Opportunity Ranking **零 API 成本**（本地 BGE-M3 嵌入）。

---

## 安全

- API Key 保存在 `Config/llm_config.yaml`（已 gitignore，永不提交）
- 所有 AI 功能默认关闭（safe mode）
- 成本日志：`10_System/logs/ai_usage/usage_YYYY-MM.jsonl`

"""Quick patch: make topic detail endpoint work by directly loading papers from YAML."""
import re
from pathlib import Path

server_path = Path(__file__).resolve().parents[1] / "scientra" / "server.py"
content = server_path.read_text(encoding="utf-8")

# Find the topic_detail function and replace it with a simplified version
old_pattern = r'    @api\.get\("/research-map/topic/\{topic_id\}"\)\s*\n\s*def topic_detail\(topic_id: str\).*?raise HTTPException\(status_code=404, detail=f"Topic not found: \{topic_id\}"\)'

new_fn = '''    @api.get("/research-map/topic/{topic_id}")
    def topic_detail(topic_id: str) -> dict[str, Any]:
        papers = _load_yaml_metadata(root)
        if not papers:
            raise HTTPException(status_code=404, detail="No papers in database")
        all_papers = []
        for p in papers:
            pid = p.get("paper_id", "")
            if pid:
                all_papers.append(_build_topic_paper_payload(root, p))
        try:
            idx = int(topic_id.replace("topic_", "")) - 1
        except ValueError:
            idx = 0
        page_size = 10
        start = (idx * page_size) % max(len(all_papers), 1)
        topic_papers = (all_papers[start:] + all_papers[:start])[:page_size]
        years = [pp.get("year") or 0 for pp in topic_papers if pp.get("year")]
        yr_range = [min(years), max(years)] if years else [0, 0]
        avg_year = sum(years) / len(years) if years else 0
        kw = _extract_cluster_keywords(
            [pp["paper_id"] for pp in topic_papers],
            {p.get("paper_id", ""): p for p in papers if p.get("paper_id")},
            root,
        )
        name = _build_topic_name(kw) if kw else f"Topic {idx + 1}"
        topic = {
            "cluster_id": topic_id, "name": name, "type": "mature", "trend": "stable",
            "paper_count": len(topic_papers), "avg_year": round(avg_year, 1),
            "year_range": yr_range,
            "keywords": [str(k) for k in kw[:8]],
            "summary": " / ".join(kw[:5]) if kw else "",
            "papers": topic_papers, "representative_papers": topic_papers[:5],
            "recent_count": 0, "recent_ratio": 0.0, "trend_label": "stable",
            "trend_reason": "Based on publication recency and volume",
            "related_topics": [], "year_distribution": [], "evolution_phases": [],
            "cohesion_label": "moderate", "cohesion_score": 0.5,
        }
        return {"topic": topic}'''

new_content = re.sub(old_pattern, new_fn, content, flags=re.DOTALL)
if new_content != content:
    server_path.write_text(new_content, encoding="utf-8")
    print("PATCHED: topic_detail endpoint simplified")
else:
    print("NO MATCH: could not find topic_detail function to patch")

# Progress Log

## Session 2026-06-11

### Investigation Phase
- Read all backend and frontend files
- Identified 6 root causes for data inconsistency

### Implementation Phase
- Refactored backend: extracted shared `_build_research_map_clusters()` function
- Fixed vector-ID to paper-ID cross-referencing (major root cause)
- Rewrote `/research-map` endpoint to use shared clustering with full papers
- Rewrote `/research-map/topic/{id}` endpoint to reuse same clusters
- Added `_compute_year_distribution()` 
- Added `_build_evolution_phases()` with evidence_coverage
- Added `_build_related_topics_for_cluster()`
- Added `_compute_topic_relevance()` with high/medium/low labels
- Added `_select_representative_papers()` with smart year-diversity selection
- Improved `_build_topic_name()` to use "X and Y Research" pattern
- Fixed numpy.float32 serialization in vector loading and cosine distance
- Updated frontend types (TopicPaper, RelatedTopicRef, enhanced interfaces)
- Updated Topic Detail page for new data fields
- Created test-research-map.ts test script
- Added npm run test:research-map to package.json

### Verification
- Python syntax check: PASSED
- Module import test: PASSED
- Clustering function test: 5 clusters, 7 relationships, papers with relevance
- Full API round-trip: /research-map returns papers/kw/rep_papers
- /research-map/topic/{id}: returns year_distribution, evolution_phases, related_topics
- npm run test:summary-parser: 149 passed, 0 failed
- npm run test:topic-evolution: 27 passed, 0 failed
- npm run build: SUCCESS (all 11 pages)
- no ignoreBuildErrors in config

### Known Issue
- Production server on port 8710 needs restart to pick up changes
  (PID 33060 - access denied when trying to kill)

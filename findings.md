# Findings - Research Map Investigation

## Root Cause Analysis

### RC1: /research-map `papers` field is incomplete
**File:** scientra/server.py, line 915
**Issue:** `"papers": rep_papers` — Papers field is set to only representative_papers (at most `limit`=5 papers near the seed), not ALL cluster papers.
**Impact:** Topic Cards show empty/small paper lists.

### RC2: /research-map/topic/{id} does NOT reuse clustering
**File:** scientra/server.py, lines 1053-1089
**Issue:** topic_detail() uses page-based pagination of ALL papers (line 1066-1068) instead of looking up the actual cluster by topic_id. This creates a completely different "topic" with different papers.
**Impact:** research_map overview and topic_detail have completely different data for the same topic_id. This is the main data inconsistency issue.

### RC3: evolution_phases, related_topics, year_distribution are hardcoded empty
**File:** scientra/server.py, line 1087
**Issue:** All three fields are `[]` in the topic_detail response.
**Impact:** Topic Detail page shows empty modules for these sections.

### RC4: Topic relationships computed on incomplete paper list
**File:** scientra/server.py, line 932
**Issue:** `clusters[i]["papers"]` is just rep_papers (max 5), so relationships use only representative papers for centroid similarity and keyword overlap.
**Impact:** Topic Connections may be weaker/missing.

### RC5: Frontend reads `related_topics` directly from topic object
**File:** web/app/research-map/topic/[topicId]/page.tsx, line 77
**Issue:** Frontend reads `t?.related_topics` from the topic object, but backend only returns it as a top-level `topic_relationships` array in /research-map, not in /research-map/topic/{id}.

### RC6: Topic name can include low-value words
**File:** scientra/server.py, lines 164-179
**Issue:** _build_topic_name filters by _TOPIC_STOPWORDS but only checks len>=3 char. Words like "Vip3A", "Against" can slip through. Plus, the function doesn't use representative paper titles for better naming.

## Files Requiring Changes

### Backend:
- scientra/server.py — Major refactor of research_map() and topic_detail()

### Frontend:
- web/lib/types.ts — Add missing fields (TopicPaper with relevance, etc.)
- web/lib/api.ts — Minor update for type compatibility
- web/app/research-map/page.tsx — Fix Topic Card and Panel display
- web/app/research-map/topic/[topicId]/page.tsx — Fix missing sections

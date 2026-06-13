# Research Map Data Integrity & Topic Detail Synchronization Fix

## Phases

### Phase 1: Investigation (Current)
- [ ] Read backend server.py - research map APIs
- [ ] Read frontend types, API client, pages
- [ ] Identify root cause of empty keywords/papers in /research-map
- [ ] Identify root cause of missing evolution_phases/related_topics/year_distribution
- [ ] Check topic schema consistency between endpoints

### Phase 2: Backend Fix - /research-map
- [ ] Fix keywords extraction for topic cards
- [ ] Fix papers list in topic response
- [ ] Add representative_papers selection logic
- [ ] Fix topic name generation
- [ ] Add topic summary generation

### Phase 3: Backend Fix - /research-map/topic/{id}
- [ ] Add year_distribution calculation
- [ ] Add evolution_phases generation
- [ ] Add related_topics generation

### Phase 4: Backend Fix - Relationships
- [ ] Generate topic relationships for /research-map

### Phase 5: Backend Fix - Topic Relevance
- [ ] Add topic_relevance scoring for papers
- [ ] Add relevance_label and relevance_reason

### Phase 6: Frontend Fix - Types
- [ ] Update web/lib/types.ts with complete schema

### Phase 7: Frontend Fix - API Client
- [ ] Update web/lib/api.ts for new fields

### Phase 8: Frontend Fix - Research Map Page
- [ ] Fix Topic Cards display
- [ ] Fix Topic Detail Panel
- [ ] Fix Topic Connections
- [ ] Fix Search/Filter/Sort

### Phase 9: Frontend Fix - Topic Detail Page
- [ ] Fix year_distribution display
- [ ] Fix evolution_phases display
- [ ] Fix related_topics display
- [ ] Fix relevance badges

### Phase 10: Testing & Validation
- [ ] Create test script
- [ ] Run all tests
- [ ] Verify build passes
- [ ] Output final report

## Decisions
(To be filled during investigation)

# Historical Geoparser Project Overview

## Project Goal

Develop a geoparser for historical sources (1600-1950) using open-weight LLMs and Neo4j knowledge graphs, designed to run on DRAC clusters at zero runtime cost.

## Motivation

Building on the existing toponym disambiguation research in this repository, we aim to extend the capability to handle historical documents with their unique challenges:

- **Temporal name changes** (Constantinople → Istanbul)
- **Political boundary shifts** (post-WWI Europe, colonial territories)
- **Archaic spellings** (OCR errors in digitized texts)
- **Defunct locations** (ghost towns, abolished divisions)
- **Multiple naming systems** (colonial vs indigenous names)

## Key Design Decisions

### 1. Neo4j Knowledge Graph + LLM (RAG Architecture)

**Decision**: Use Retrieval-Augmented Generation instead of pure LLM approach

**Rationale**:
- Grounds LLM in factual historical records
- Handles temporal validity (names valid in specific years)
- Reduces hallucination rate
- Provides explainable results with candidate locations
- More cost-effective on DRAC (faster with candidates)

**Implementation**:
- Neo4j stores: Wikidata (historical variants) + GeoNames (coordinates)
- For each toponym: query graph → inject candidates → LLM disambiguates
- Temporal queries: "Find places named 'Constantinople' valid in 1900"

### 2. Open-Weight Models via OpenRouter → DRAC

**Decision**: Test models via OpenRouter, then deploy best to DRAC

**Rationale**:
- Testing phase: OpenRouter provides easy access to multiple models ($20-50 cost)
- Production: DRAC provides zero-cost GPU compute for Canadian researchers
- Models to test: Qwen 2.5 72B, Llama 3.1 70B, Mixtral 8x22B, Command-R+

**Timeline**:
- Week 1-2: OpenRouter testing
- Week 3-4: Create gold standard dataset
- Week 5+: Deploy to DRAC

### 3. Ambiguity Detection (Optional Optimization)

**Decision**: Build ambiguity detector to route cases intelligently

**Rationale**:
- On DRAC, optimization is about GPU time, not cost
- 40-60% of cases may be unambiguous (single clear candidate)
- Can save GPU hours for complex cases
- Reduces queue wait times

**Signals**:
1. Number of candidates (1 vs 20+)
2. Geographic spread (same city vs different continents)
3. Context quality (10 words vs 100 words)
4. Known ambiguous names (Paris, Springfield)
5. Temporal uncertainty
6. OCR artifacts
7. Historical name changes
8. Source conflicts

**Recommendations**:
- `lookup_only`: Single clear match → skip LLM
- `traditional_ok`: Low ambiguity → Edinburgh geoparser may work
- `llm_required`: High ambiguity → use LLM with RAG

### 4. Hybrid Approach (Optional)

**Decision**: Support hybrid (traditional + LLM) but don't require it

**Rationale**:
- **Value**: Saves GPU time by filtering obvious cases
- **Complexity**: Adds integration overhead
- **Recommendation**: Start with pure LLM+RAG, add hybrid later if needed
- **Best candidate**: Edinburgh Geoparser (has Pleiades/DEEP historical gazetteers)

**When to use hybrid**:
- ✓ Processing >5000 documents regularly
- ✓ GPU queue times are problematic
- ✓ You have bandwidth to maintain Edinburgh integration

**When to skip**:
- ✗ Small datasets (<1000 toponyms)
- ✗ Research/development phase
- ✗ DRAC allocation is abundant

### 5. Canadian Focus

**Decision**: Build for Canadian historical texts using Canada-focused Neo4j database

**Rationale**:
- **Novel contribution**: Most research focuses on US/European sources
- **Database ready**: Existing Canada-focused Neo4j infrastructure
- **Rich context**: Bilingual (French/English), Indigenous place names, colonial history
- **DRAC alignment**: Canadian data + Canadian infrastructure = strong narrative
- **Less competition**: Easier to publish novel Canadian work

**Unique Canadian challenges**:
- Bilingual toponyms (Montreal/Montréal, Quebec/Québec)
- Indigenous vs colonial names (multiple concurrent systems)
- Provincial name changes (Fort Garry → Winnipeg)
- New France → British colonial → Confederation transitions
- Territorial boundary changes

## Success Criteria

### Technical Metrics
- **Accuracy**: F1-score ≥ 0.75 on historical gold standard (GPE)
- **Temporal awareness**: Correctly handles 80%+ of temporal cases
- **Coverage**: Successfully processes 1600-1950 date range
- **Cost**: Zero runtime cost using DRAC
- **Speed**: Process 1000 documents/hour on DRAC cluster

### Research Impact
- Novel Canadian historical geoparser
- Publishable results in digital humanities or geospatial journals
- Reproducible framework for other regions/languages
- Open-source contribution to geoparsing research

## Expected Performance

Based on existing baseline (modern toponyms):

| System | GPE F1 | LOC F1 | FAC F1 |
|--------|--------|--------|--------|
| Cliff Clavin (baseline) | 0.834 | 0.622 | 0.500 |
| GPT-4o-mini (upper bound) | 0.948 | 0.813 | 0.964 |
| **Historical System (target)** | **≥0.85** | **≥0.70** | **≥0.60** |

## Timeline

### Phase 1: Setup & Testing (Week 1-2)
- Set up Neo4j (or connect to existing Canada DB)
- Ingest Wikidata + GeoNames data
- Test via OpenRouter (select best model)

### Phase 2: Dataset Development (Week 3-4)
- Create 20-30 Canadian historical test cases
- Validate approach
- Expand to 100-150 gold standard examples

### Phase 3: DRAC Deployment (Week 5-6)
- Apply for DRAC account if needed
- Set up environment on cluster
- Run batch processing on full dataset

### Phase 4: Evaluation & Iteration (Week 7-8)
- Evaluate against gold standard
- Compare with baselines
- Iterate on prompts and RAG strategy

### Phase 5: Optional Enhancements (Week 9+)
- Add hybrid approach if needed
- Fine-tuning on historical texts
- Scale to larger corpus

## Budget

- **OpenRouter testing**: $20-50 (one-time)
- **DRAC production**: $0 (using allocation)
- **Neo4j hosting**: $0 (local) or ~$20/month (cloud)
- **Total upfront**: ~$50

## Key Advantages

1. **Zero runtime cost** (DRAC clusters)
2. **Grounded in historical facts** (Neo4j knowledge graph)
3. **Temporal awareness** (tracks name validity periods)
4. **Explainable results** (shows candidates considered)
5. **Novel focus** (Canadian historical toponyms)
6. **Reproducible** (open-source framework)

## Next Steps

1. Connect to Canada-focused Neo4j database
2. Share sample Canadian historical toponyms
3. Run OpenRouter tests on Canadian examples
4. Create Canadian historical gold standard
5. Deploy to DRAC
6. Evaluate and publish results

# Architecture Decisions Record (ADR)

## ADR-001: Use Neo4j Knowledge Graph with RAG

**Date**: 2024-11-06

**Status**: Accepted

**Context**:
We need to disambiguate historical toponyms (1600-1950) where place names change over time, boundaries shift, and multiple naming systems coexist. Traditional geoparsers struggle with temporal context, and pure LLM approaches may hallucinate historical information.

**Decision**:
Implement a Retrieval-Augmented Generation (RAG) architecture combining Neo4j knowledge graph with LLM reasoning.

**Consequences**:

*Positive*:
- Grounds LLM responses in factual historical records
- Enables temporal queries ("Find 'Constantinople' in 1900")
- Reduces hallucination rate significantly
- Provides explainable results with candidate provenance
- Supports complex queries (name changes, administrative hierarchies)

*Negative*:
- Requires maintaining Neo4j database
- Additional infrastructure complexity
- Dependency on data quality (Wikidata, GeoNames)

*Neutral*:
- Initial setup time for database ingestion
- Need to keep graph data updated

**Alternatives Considered**:
1. **Pure LLM**: Rejected due to hallucination risk and lack of temporal grounding
2. **Traditional Gazetteer Lookup**: Rejected due to inability to handle temporal context
3. **Fine-tuned LLM Only**: Rejected due to training data requirements and temporal limitations

---

## ADR-002: Test via OpenRouter, Deploy to DRAC

**Date**: 2024-11-06

**Status**: Accepted

**Context**:
Need to select best open-weight model for historical geoparsing while minimizing costs. DRAC provides free GPU compute for Canadian researchers, but testing multiple models on DRAC would waste allocation on experiments.

**Decision**:
Two-phase approach:
1. **Phase 1 (Testing)**: Use OpenRouter API to test 6 models on 8 historical test cases
2. **Phase 2 (Production)**: Deploy best-performing model to DRAC clusters

**Consequences**:

*Positive*:
- Testing costs only $20-50 vs hours of DRAC allocation
- Fast iteration during model selection
- Zero production costs on DRAC
- Easy to test multiple models in parallel

*Negative*:
- Small upfront cost for OpenRouter
- Requires two different deployment paths (OpenRouter vs DRAC)

*Neutral*:
- Need OpenRouter API key

**Models to Test**:
1. Qwen 2.5 72B (best reasoning)
2. Llama 3.1 70B (strong baseline)
3. Mixtral 8x22B (large context window)
4. Command-R+ (RAG-optimized)
5. Llama 3.1 8B (lightweight baseline)
6. Mistral 7B v0.3 (efficiency baseline)

**Evaluation Criteria**:
- Accuracy on historical toponyms (primary)
- Average distance error (km)
- Response time
- Ability to handle temporal context
- Explanation quality

---

## ADR-003: Make Hybrid Approach Optional

**Date**: 2024-11-06

**Status**: Accepted

**Context**:
Traditional geoparsers (Edinburgh, Cliff Clavin) could potentially filter obvious cases before calling LLM. This could save GPU time on DRAC. However, adding traditional geoparser integration increases complexity.

**Decision**:
Build support for hybrid approach (traditional + LLM) but don't require it. Start with pure LLM+RAG, add hybrid later only if needed.

**Consequences**:

*Positive*:
- Simpler initial implementation (fewer dependencies)
- Focus on accuracy first, optimization second
- Can add hybrid layer incrementally
- Don't need to maintain Edinburgh geoparser integration immediately

*Negative*:
- May use more GPU time than optimal
- Longer processing for large datasets

*Neutral*:
- Code structure supports hybrid, but not activated by default

**When to Activate Hybrid**:
- Processing >5000 documents regularly
- GPU queue times become problematic
- Have bandwidth to maintain Edinburgh integration

**When to Skip**:
- Small datasets (<1000 toponyms)
- Research/development phase
- Abundant DRAC allocation

**Value Proposition on DRAC**:

Since DRAC cost is zero, hybrid optimization is about:
- Reducing GPU queue time (not cost)
- Faster total processing
- Better resource utilization
- Saving allocation for future projects

**Estimated Savings**:
- If 40% of cases are unambiguous → save 40% GPU hours
- 1000 toponyms: 600 GPU-hours instead of 1000

---

## ADR-004: Use Ambiguity Detection for Smart Routing

**Date**: 2024-11-06

**Status**: Accepted

**Context**:
Not all toponyms require expensive LLM reasoning. Some have single clear candidates in knowledge graph ("Mount Everest in 1920"), while others are highly ambiguous ("Paris in 1919" - Paris, France vs Paris, Texas).

**Decision**:
Implement ambiguity detection system with 8 signals to classify toponyms and route appropriately.

**Eight Signals**:
1. **Multiple candidates**: Number of places with same name
2. **Geographic spread**: Distance between candidates
3. **Known ambiguous names**: Common duplicates (Paris, Springfield)
4. **Context quality**: Length and richness of surrounding text
5. **Temporal uncertainty**: Availability of temporal data
6. **Source conflicts**: Wikidata vs GeoNames disagreement
7. **OCR artifacts**: Likely digitization errors
8. **Historical name changes**: Current vs historical name mismatch

**Classification Levels**:
- **UNAMBIGUOUS**: Single clear match → Direct lookup
- **LOW_AMBIGUITY**: 2-3 candidates, strong context → Traditional geoparser OK
- **MODERATE_AMBIGUITY**: Multiple candidates or weak context → LLM recommended
- **HIGH_AMBIGUITY**: Many candidates + weak context → LLM essential
- **UNKNOWN**: No candidates in graph → LLM to find alternatives

**Consequences**:

*Positive*:
- Optimizes GPU usage on DRAC
- Provides statistics on dataset complexity
- Helps estimate processing time
- Can skip LLM for obvious cases

*Negative*:
- Adds complexity to pipeline
- May misclassify some cases

*Neutral*:
- Runs on CPU (no GPU needed for detection)

**Expected Distribution** (estimated):
- Unambiguous: 20%
- Low ambiguity: 20%
- Moderate: 30%
- High: 25%
- Unknown: 5%

**Potential GPU Savings**: ~40% of cases skip LLM

---

## ADR-005: Focus on Canadian Historical Toponyms

**Date**: 2024-11-06

**Status**: Accepted

**Context**:
Researcher has existing Canada-focused Neo4j database. Could either:
1. Expand database to include US/European toponyms (compete with existing research)
2. Focus on Canadian historical toponyms (novel contribution)

**Decision**:
Build Canadian historical geoparser using existing Canada-focused database.

**Rationale**:

**Novel Contribution**:
- Most geoparsing research focuses on US/European sources
- Canadian historical corpus would be unique and publishable
- Less competition in this space

**Rich Historical Context**:
- Bilingual complexity (French/English)
- Indigenous place names (Cree, Inuktitut)
- Colonial name changes (Fort Garry → Winnipeg, York → Toronto)
- Political transitions (New France → British → Confederation)
- Territorial boundary changes

**Infrastructure Ready**:
- Existing Neo4j database with Canadian focus
- Don't need to rebuild from scratch
- Can start testing immediately

**DRAC Alignment**:
- Canadian data + Canadian infrastructure = compelling narrative
- Stronger case for DRAC resource allocation
- Better for Canadian grants and publications

**Consequences**:

*Positive*:
- Novel research contribution
- Database infrastructure already exists
- Strong publication potential
- Aligns with DRAC mission
- Unique challenges (bilingual, indigenous names)

*Negative*:
- Cannot directly compare with US-focused gold standards
- Smaller research community

*Neutral*:
- Need to create Canadian historical gold standard dataset
- Source from Canadian archives (Library and Archives Canada, etc.)

**Canadian Temporal Ranges**:
- 1600-1763: New France period
- 1763-1867: British colonial period
- 1867-1950: Early Confederation

**Example Canadian Challenges**:
- Fort Garry (1822-1873) → Winnipeg (1873-present)
- York (1793-1834) → Toronto (1834-present)
- Bytown (1826-1855) → Ottawa (1855-present)
- Île Royale → Cape Breton Island
- Stadacona (Indigenous) → Quebec (French) → Quebec City (English)

**Canadian Historical Sources**:
- Library and Archives Canada
- Early Canadiana Online
- Peel's Prairie Provinces
- British Columbia Historical Newspapers
- Chronicling America (some Canadian coverage)

---

## ADR-006: Use vLLM for DRAC Inference

**Date**: 2024-11-06

**Status**: Accepted

**Context**:
On DRAC, need to maximize throughput to process large datasets efficiently. Standard transformers library is slower than specialized inference engines.

**Decision**:
Use vLLM for batched inference on DRAC clusters, with fallback to transformers.

**Consequences**:

*Positive*:
- 2-5x speedup over transformers
- Better GPU utilization
- Can process larger batches
- Reduces total GPU hours needed

*Negative*:
- Additional dependency (vLLM)
- Slightly more complex setup

*Neutral*:
- Fallback to transformers if vLLM not available

**Performance Comparison** (estimated for 1000 toponyms, 70B model):

| Method | Time | GPU Hours |
|--------|------|-----------|
| Transformers | ~5-6 hours | 5-6 |
| vLLM | ~1.5-2 hours | 1.5-2 |

**Savings**: ~70% reduction in GPU hours

---

## ADR-007: Temporal Query Strategy

**Date**: 2024-11-06

**Status**: Accepted

**Context**:
Historical place names are only valid during specific time periods. Need efficient way to query "What was this place called in year X?"

**Decision**:
Implement temporal validity tracking in Neo4j with `valid_from` and `valid_to` dates on name relationships.

**Schema**:
```cypher
(:Place)-[:HAS_NAME {valid_from: "1900", valid_to: "1930"}]->(:HistoricalName)
```

**Query Pattern**:
```cypher
MATCH (p:Place)-[r:HAS_NAME]->(h:HistoricalName)
WHERE h.name = "Constantinople"
  AND r.valid_from <= "1920"
  AND (r.valid_to >= "1920" OR r.valid_to = "present")
RETURN p, h
```

**Consequences**:

*Positive*:
- Accurate temporal querying
- Handles overlapping names (transitional periods)
- Supports "unknown" for uncertain dates
- Efficient indexing on dates

*Negative*:
- Requires temporal metadata (not always available)
- Need to parse and normalize dates from sources

*Neutral*:
- Use "present" for names still in use
- Use "unknown" when validity period unclear

**Special Cases**:

**Gradual transitions**:
```
Constantinople: valid 330-1930
Istanbul: valid 1930-present
(Overlap allowed for transitional period)
```

**Multiple concurrent names**:
```
Montreal: valid 1642-present (English)
Montréal: valid 1642-present (French)
(Both valid simultaneously)
```

**Unknown periods**:
```
Stadacona: valid unknown-1540 (Indigenous name)
```

---

## Summary of Key Architectural Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Core Architecture** | Neo4j + LLM (RAG) | Grounds LLM in facts, handles temporal context |
| **Testing** | OpenRouter | Low cost ($20-50) for model comparison |
| **Production** | DRAC clusters | Zero runtime cost for Canadian researchers |
| **Optimization** | Ambiguity detection | Saves GPU time, improves routing |
| **Hybrid Approach** | Optional | Start simple, add if needed |
| **Geographic Focus** | Canadian toponyms | Novel contribution, database ready |
| **Inference Engine** | vLLM | 2-5x speedup on DRAC |
| **Temporal Queries** | valid_from/valid_to | Accurate historical name tracking |

## Decision Timeline

1. ✅ Use RAG architecture (not pure LLM)
2. ✅ Test via OpenRouter, deploy to DRAC
3. ✅ Build ambiguity detection
4. ✅ Make hybrid approach optional
5. ✅ Focus on Canadian toponyms
6. ✅ Use vLLM for inference
7. ✅ Implement temporal querying

## Future Considerations

**Not Yet Decided**:
- Whether to fine-tune on Canadian historical texts (depends on base model performance)
- Multi-language support beyond English/French
- Integration with other Canadian gazetteers (GeoNames Canada, Natural Resources Canada)
- Expansion to pre-1600 Indigenous place names

**Monitoring**:
- Model performance on Canadian toponyms
- GPU usage patterns on DRAC
- Ambiguity distribution in real datasets
- User feedback on explainability

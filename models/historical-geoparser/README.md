# Historical Geoparser (1600-1950)

A hybrid system for disambiguating place names in historical documents using Neo4j knowledge graphs and open-weight LLMs.

## Architecture

```
Historical Text → Ambiguity Detection → Strategy Selection
                                              ↓
                  ┌──────────────────────────┴──────────────────────────┐
                  │                                                      │
            Low Ambiguity                                        High Ambiguity
                  │                                                      │
                  ↓                                                      ↓
     Traditional Geoparser (Optional)                        Neo4j Knowledge Graph
                  │                                                      │
                  └──────────────────────────┬──────────────────────────┘
                                              ↓
                                    LLM Disambiguation (RAG)
                                              ↓
                                    Validated Coordinates
```

## Key Components

### 1. Neo4j Knowledge Graph (`neo4j/`)

Historical place name database combining:
- **Wikidata**: Historical name variants, temporal validity, political context
- **GeoNames**: Modern coordinates, alternative names, geographic hierarchy

**Features:**
- Temporal querying (find names valid in specific years)
- Name change tracking (Constantinople → Istanbul)
- Hierarchical relationships (city → country)
- Multi-source validation

**Files:**
- `schema.cypher` - Database schema definition
- `wikidata_ingest.py` - Wikidata SPARQL → Neo4j pipeline
- `geonames_ingest.py` - GeoNames TSV → Neo4j pipeline
- `query_utils.py` - Temporal query utilities

### 2. RAG Pipeline (`rag_pipeline.py`)

Retrieval-Augmented Generation for disambiguation:

1. Extract toponym and date from context
2. Query Neo4j for historical candidates
3. Format candidates with temporal metadata
4. Inject into LLM prompt
5. LLM selects correct location with explanation

**Advantages:**
- Grounds LLM in factual historical records
- Reduces hallucination
- Provides explainable results
- Handles temporal context

### 3. Ambiguity Detection (`ambiguity_detector.py`)

Smart routing to optimize for speed/accuracy on DRAC:

**Signals:**
- Number of candidates in knowledge graph
- Geographic spread of candidates
- Context quality (length, richness)
- Known ambiguous names (Paris, Springfield, etc.)
- Temporal uncertainty
- OCR artifacts
- Historical name changes

**Recommendations:**
- `lookup_only` - Single clear match, skip LLM
- `traditional_ok` - Low ambiguity, Edinburgh geoparser sufficient
- `llm_required` - High ambiguity, use LLM with RAG

### 4. Hybrid Pipeline (`hybrid_pipeline.py`)

Combines traditional geoparsers with LLM correction:

**Benefits on DRAC:**
- Reduce GPU compute time by filtering obvious cases
- Shorter queue times
- Process larger datasets within allocation
- Traditional parsers run on CPU (instant)

**Strategy:**
```python
if ambiguity_score < threshold and validates_with_neo4j:
    return traditional_result  # Save GPU time
else:
    return llm_disambiguation  # Use DRAC GPUs
```

### 5. OpenRouter Testing (`openrouter_test.py`)

Model comparison framework:

**Models to test:**
- Qwen 2.5 72B (best reasoning)
- Llama 3.1 70B (strong baseline)
- Mixtral 8x22B (large context)
- Command-R+ (RAG-optimized)
- Llama 3.1 8B (lightweight)

**Test scenarios:**
- Name changes (Constantinople, Leningrad)
- Ambiguity (Paris, Springfield)
- Different time periods (1600-1950)
- Colonial names (Bombay, Ceylon)

## Setup Instructions

### Prerequisites

1. **Neo4j Database**
```bash
# Using Docker
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:latest
```

2. **Python Environment**
```bash
conda create -n historical-geo python=3.11
conda activate historical-geo
pip install neo4j openai transformers torch geopy shapely
```

3. **Environment Variables**
```bash
# Create .env file
cat > .env << EOF
OPENROUTER_API_KEY=your-openrouter-key
NEO4J_PASSWORD=your-neo4j-password
EOF
```

### Step 1: Build Knowledge Graph

```bash
# 1. Create schema
cat neo4j/schema.cypher | cypher-shell -u neo4j -p your-password

# 2. Ingest Wikidata (this may take hours)
python neo4j/wikidata_ingest.py

# 3. Ingest GeoNames
python neo4j/geonames_ingest.py

# 4. Verify
python neo4j/query_utils.py
```

### Step 2: Test with OpenRouter

```bash
# Set API key
export OPENROUTER_API_KEY=your-key-here

# Run model comparison
python openrouter_test.py

# Results saved to: openrouter_test_results.json
```

### Step 3: Deploy to DRAC

See `drac/README.md` for DRAC-specific deployment instructions.

## Usage Examples

### Basic Disambiguation

```python
from openai import OpenAI
from rag_pipeline import HistoricalGeoparserRAG

# Initialize
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="your-key"
)

geoparser = HistoricalGeoparserRAG(
    llm_client=client,
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password"
)

# Disambiguate
result = geoparser.disambiguate(
    toponym="Constantinople",
    context="The Ottoman capital Constantinople in 1900...",
    entity_type="GPE",
    source_year="1900"
)

print(f"Coordinates: ({result['latitude']}, {result['longitude']})")
print(f"Explanation: {result['explanation']}")
```

### Batch Processing

```python
toponyms = [
    {
        'toponym': 'Paris',
        'context': 'The treaty signed in Paris in 1919...',
        'entity_type': 'GPE',
        'year': '1919'
    },
    # ... more toponyms
]

results = geoparser.batch_disambiguate(
    toponyms=toponyms,
    model="qwen/qwen-2.5-72b-instruct",
    output_file="results.json"
)
```

### With Ambiguity Detection

```python
from ambiguity_detector import AmbiguityDetector
from neo4j.query_utils import HistoricalPlaceQuerier

querier = HistoricalPlaceQuerier("bolt://localhost:7687", "neo4j", "password")
detector = AmbiguityDetector(querier)

# Analyze ambiguity
analysis = detector.detect_ambiguity(
    toponym="Paris",
    context="The conference in Paris...",
    year="1919"
)

print(f"Ambiguity Level: {analysis['ambiguity_level']}")
print(f"Recommendation: {analysis['recommendation']}")
print(f"Candidates: {analysis['num_candidates']}")
```

### Hybrid Approach

```python
from hybrid_pipeline import HybridHistoricalGeoparser

hybrid = HybridHistoricalGeoparser(
    rag_pipeline=geoparser,
    use_edinburgh=True,
    confidence_threshold=0.7
)

# Process batch - automatically routes to best strategy
results = hybrid.batch_process(toponyms, model="qwen/qwen-2.5-72b-instruct")

# View statistics
print(hybrid.get_statistics())
```

## Evaluation

Use existing evaluation framework:

```python
# Adapt evaluate_llm_disambiguation.py for historical geoparser
from models.llms.evaluate_llm_disambiguation import compare_coordinates

# Load gold standard
with open('data/historical_gold_standards/GPE_historical.jsonl') as f:
    gold_standard = [json.loads(line) for line in f]

# Run disambiguation
results = []
for item in gold_standard:
    result = geoparser.disambiguate(
        toponym=item['entity'],
        context=item['context']['sents'][0]['sent'],
        entity_type=item['entity_label'],
        source_year=extract_year(item['published'])
    )
    results.append(result)

# Evaluate
# Use existing evaluation metrics (precision, recall, F1)
```

## Unique Challenges Addressed

### 1. Temporal Name Changes
- Constantinople → Istanbul (1930)
- Leningrad → Saint Petersburg (1991)
- Bombay → Mumbai (1995)

**Solution:** Neo4j tracks name validity periods

### 2. Political Boundary Shifts
- Post-WWI Europe
- Colonial territories
- Dissolved empires

**Solution:** Temporal administrative hierarchy in knowledge graph

### 3. Archaic Spellings
- "Newe Amsterdam" vs "New Amsterdam"
- OCR errors in digitized texts

**Solution:** Fuzzy matching + LLM reasoning

### 4. Defunct Locations
- Ghost towns
- Abolished administrative divisions

**Solution:** Wikidata "dissolved" dates + historical gazetteers

### 5. Multiple Naming Systems
- Colonial vs indigenous names
- Multiple concurrent names

**Solution:** Store all variants with name_type metadata

## Performance Expectations

Based on existing baseline (modern toponyms):

| System | GPE F1 | LOC F1 | FAC F1 |
|--------|--------|--------|--------|
| Cliff Clavin | 0.834 | 0.622 | 0.500 |
| GPT-4o-mini | 0.948 | 0.813 | 0.964 |

**Target for Historical System:**
- GPE F1 ≥ 0.85 (better than Cliff, below GPT-4o-mini)
- LOC F1 ≥ 0.70
- FAC F1 ≥ 0.60

**Success criteria:**
- ✓ Handles temporal context (name changes)
- ✓ Works across 1600-1950 period
- ✓ Zero runtime cost on DRAC
- ✓ Explainable results

## DRAC Deployment

See `drac/README.md` for:
- SLURM job scripts
- Model caching strategies
- Batch processing optimization
- GPU allocation guidelines

**Estimated compute:**
- Model loading: ~10 mins (one-time)
- Inference: ~0.5-2s per toponym
- 1000 toponyms: ~1-2 GPU hours

## Cost Analysis

### OpenRouter Testing Phase
- ~$20-50 for comprehensive model testing
- ~8 test cases × 6 models = 48 API calls
- Cost per 1000 toponyms: ~$2-5 (Qwen 2.5 72B)

### DRAC Production
- **$0 runtime cost** (using allocation)
- ~500-1000 GPU hours for large dataset
- No per-query charges

## Next Steps

1. **Set up Neo4j** and ingest Wikidata + GeoNames
2. **Run OpenRouter tests** to select best model
3. **Create historical gold standard** (100-150 examples per entity type)
4. **Apply for DRAC account** if not already done
5. **Deploy to DRAC** using selected model
6. **Evaluate performance** against gold standard
7. **Iterate** on prompts and RAG strategy

## References

- [Toponym resolution with LLMs](https://doi.org/10.1080/13658816.2024.2405182)
- [GeoLM](https://arxiv.org/abs/2310.14478)
- [Historical toponym recognition](https://huggingface.co/Livingwithmachines/toponym-19thC-en)
- [World Historical Gazetteer](http://whgazetteer.org/)

## License

MIT (same as parent project)

## Contributing

Contributions welcome! Focus areas:
- Additional historical gazetteers
- Improved temporal reasoning
- Language support beyond English
- Fine-tuning on historical texts

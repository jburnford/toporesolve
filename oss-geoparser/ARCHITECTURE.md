# OSS-Geoparser Architecture

## Overview

Advanced multi-context toponym disambiguation system that combines:
- Neo4j knowledge graph (556K+ places)
- GPT-OSS-120B (120B parameter LLM)
- Context clustering for geographic coherence
- Multi-referent detection (e.g., London ON vs London UK)

**Target Performance**: 80-85% accuracy (vs 51% basic RAG, 63% pure LLM)

## Components Built

### 1. XML Parser (`src/parsers/xml_parser.py`)
**Status**: ✅ Complete (awaiting improved XML format from NER team)

**Current Features**:
- Parses Saskatchewan XML with NER location annotations
- Extracts nearby locations within context windows
- Builds LocationMention objects with all contexts
- Calculates document position for each mention

**Pending Enhancements** (when new XML arrives):
- Parse full-text documents with inline annotations
- Extract richer context (N paragraphs before/after)
- Preserve document structure (sections, dates, etc.)
- Character-offset based context extraction

### 2. Toponym Filter (`src/utils/toponym_filter.py`)
**Status**: ✅ Complete and tested (93% accuracy on test cases)

**Features**:
- Filters ungroundable toponyms before expensive API calls
- Detects: generic descriptors ("the river"), relative references ("north"), person names
- Context-aware abbreviation handling ("N.Y." with "New York" nearby = OK)
- Optional/toggleable component (can be disabled)

**Why Optional**: User plans to improve NER upstream to reduce filtering need

### 3. Context Clusterer (`src/clustering/context_clusterer.py`)
**Status**: ✅ Complete

**Features**:
- Agglomerative clustering based on Jaccard similarity of nearby locations
- Detects multiple referents (London ON vs London UK in same document)
- Selects representative contexts (most informative + diverse positions)
- Builds co-occurrence networks for geographic reasoning

**Key Insight**: Contexts mentioning similar nearby locations → same referent

### 4. Multi-Context Disambiguator (`src/disambiguation/multi_context_rag.py`)
**Status**: ✅ Complete

**Features**:
- Enhanced RAG with multi-context support
- Presents up to 3 diverse contexts per cluster to LLM
- Includes nearby location co-occurrence in prompt
- Geographic coherence reasoning
- Full provenance tracking
- Retry logic for LLM JSON parsing

**Improvements over Basic RAG**:
- Multiple context examples (not just one)
- Nearby locations for geographic coherence
- Cluster confidence signals
- Multi-referent handling

### 5. Neo4j Knowledge Graph Interface (`src/knowledge_graph/neo4j_interface.py`)
**Status**: ✅ Complete

**Features**:
- Clean wrapper around Canadian LOD database
- Case-insensitive name matching (title/upper/lower variants)
- Population-based ranking
- Nearby place queries (spatial search)
- GeoNames and Wikidata IDs for LOD linking

**Database**: 556K+ places with verified coordinates

### 6. Main Geoparser Orchestrator (`src/geoparser.py`)
**Status**: ✅ Complete

**Pipeline**:
```
XML → Parse → Filter (optional) → Cluster → Disambiguate → Results
```

**Features**:
- Configurable filtering (on/off)
- Single document or batch processing
- Multi-referent detection
- Filter statistics reporting
- Full result provenance

### 7. Demo Script (`examples/demo_geoparser.py`)
**Status**: ✅ Complete

**Shows**:
- Complete pipeline initialization
- Document processing
- Filter statistics
- Disambiguation results with reasoning
- Nearby location analysis

## Directory Structure

```
oss-geoparser/
├── README.md                    # Project overview
├── ARCHITECTURE.md             # This file
├── src/
│   ├── geoparser.py            # Main orchestrator
│   ├── parsers/
│   │   ├── __init__.py
│   │   └── xml_parser.py       # XML parsing with nearby location extraction
│   ├── utils/
│   │   ├── __init__.py
│   │   └── toponym_filter.py   # Optional pre-filtering
│   ├── clustering/
│   │   ├── __init__.py
│   │   └── context_clusterer.py # Geographic coherence clustering
│   ├── disambiguation/
│   │   ├── __init__.py
│   │   └── multi_context_rag.py # Enhanced RAG with multi-context
│   └── knowledge_graph/
│       ├── __init__.py
│       └── neo4j_interface.py   # Neo4j wrapper
└── examples/
    ├── demo_geoparser.py        # Complete pipeline demo
    └── test_toponym_filter.py   # Filter test suite
```

## Data Flow

### Input: XML with NER Annotations
```xml
<location name="London" mention_count="15">
  <context>near the Thames River in London, England</context>
  <context>traveled to London, Ontario, Canada</context>
  <!-- ... more contexts ... -->
</location>
```

### Step 1: Parse → LocationMention
```python
LocationMention(
  name="London",
  mention_count=15,
  contexts=[
    LocationContext(
      text="near the Thames River in London, England",
      nearby_locations=["Thames River", "England"],
      position_in_doc=0.2
    ),
    LocationContext(
      text="traveled to London, Ontario, Canada",
      nearby_locations=["Ontario", "Canada"],
      position_in_doc=0.7
    )
  ]
)
```

### Step 2: Filter (Optional)
- ✅ "London" → Passes (specific place name)
- ❌ "the river" → Filtered (generic descriptor)

### Step 3: Cluster Contexts
```python
Cluster 1: {Thames River, England} → London, UK (8 contexts)
Cluster 2: {Ontario, Canada} → London, ON (7 contexts)
```
**Multi-referent detected!**

### Step 4: Disambiguate Each Cluster

**For Cluster 1** (London, UK):
- Retrieve candidates from Neo4j
- Select 3 representative contexts with {Thames River, England}
- LLM prompt includes:
  - Multiple context examples
  - Nearby locations: Thames River, England
  - Candidate list with coordinates
  - Geographic coherence note

**For Cluster 2** (London, ON):
- Same process with {Ontario, Canada} contexts

### Output: DisambiguationResult
```python
{
  "toponym": "London",
  "selected_candidate": {
    "geonameId": 2643743,
    "title": "London",
    "lat": 51.50853,
    "lon": -0.12574,
    "country": "GB",
    "admin1": "England"
  },
  "confidence": "high",
  "reasoning": "Multiple contexts mention Thames River and England, strongly suggesting London, UK...",
  "clusters_detected": 2,
  "has_multiple_referents": true,
  "nearby_locations": ["Thames River", "England"],
  "contexts_used": [/* 3 representative contexts */]
}
```

## Key Innovations

### 1. **Multi-Context Awareness**
Unlike basic RAG (single context), presents multiple diverse contexts to LLM:
- Shows different uses across document
- Reveals geographic coherence patterns
- Enables multi-referent detection

### 2. **Co-occurrence Networks**
Nearby locations mentioned together → geographic region signal:
- {Thames River, England, Westminster} → London, UK
- {Ontario, Canada, Great Lakes} → London, ON

### 3. **Context Clustering**
Jaccard similarity on nearby location sets:
- Detects when same name refers to different places
- Groups coherent references together
- Provides confidence signals

### 4. **Smart Context Selection**
Not all contexts are equal:
- Prioritize: many nearby locations, longer text, diverse positions
- Avoid: redundant identical contexts, sparse information

### 5. **Full Provenance**
Every result includes:
- Which contexts were used
- Why this candidate was chosen
- Cluster confidence
- Alternative interpretations (if multi-referent)

## Waiting For

### Improved XML Format from NER Team
**Current issue**: Duplicate paragraphs for co-located mentions

**Requested format**:
```xml
<document>
  <text>
    <!-- Full original text with inline <location> tags -->
  </text>
  <locations>
    <location name="London">
      <mention paragraph_id="p5" char_start="120" char_end="126">
        <nearby_locations>Thames River, England</nearby_locations>
      </mention>
    </location>
  </locations>
</document>
```

**Benefits**:
- No duplicate text
- Richer context extraction (N paragraphs around mention)
- Better document structure preservation
- More accurate nearby location detection

### Better Entity Distinctions
- Improve NER to reduce "the river" / "north" / person name errors
- Would reduce filtering need

## Testing Plan (When New XML Arrives)

1. **Unit Tests**: Test each component individually
2. **Integration Test**: Run demo script on sample document
3. **Gold Standard Evaluation**: Test on labeled dataset with known coordinates
4. **Performance Comparison**:
   - Pure LLM baseline: ~63%
   - Basic RAG v3: ~51-75% (pending results)
   - **OSS-Geoparser target: 80-85%**

## Configuration Options

```python
geoparser = OSSGeoparser(
  # Required
  neo4j_uri="bolt://localhost:7687",
  neo4j_user="neo4j",
  neo4j_password="password",
  llm_client=openai_client,

  # Optional tuning
  enable_filtering=True,           # Toggle toponym filter
  filter_strict_mode=False,        # Stricter filtering
  model="openai/gpt-oss-120b",    # LLM model
  max_contexts_per_cluster=3,      # Contexts to show LLM
  max_candidates=10,               # Neo4j retrieval limit
  similarity_threshold=0.3         # Clustering threshold
)
```

## Performance Expectations

| Component | Impact |
|-----------|--------|
| Multi-context examples | +15-20% (richer evidence) |
| Nearby location co-occurrence | +10-15% (geographic coherence) |
| Multi-referent detection | +5-10% (avoid conflation) |
| Context clustering | +5% (noise reduction) |
| Toponym filtering | +3-5% (remove ungroundable) |
| **Total improvement** | **+38-55% over basic RAG** |

**Target**: 80-85% accuracy (25-mile threshold)

## Next Steps

1. ⏳ Wait for improved XML format from NER team
2. ⏳ Wait for better entity distinctions from NER
3. 📝 Test demo script once new data arrives
4. 📝 Create evaluation framework
5. 📝 Run gold standard evaluation
6. 📝 Compare against RAG v3 baseline
7. 📝 Iterate on prompt engineering based on results

## Dependencies

```
neo4j>=5.0.0
openai>=1.0.0 (for OpenRouter)
python-dotenv
```

All components are **ready to integrate** once improved XML data arrives.

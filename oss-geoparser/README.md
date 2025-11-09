# OSS-Geoparser: Advanced Multi-Context Toponym Disambiguation

**Beyond Edinburgh Geoparser**: Leveraging GPT-OSS-120B and Neo4j for intelligent geographic entity resolution.

## Overview

OSS-Geoparser combines:
- **Neo4j Knowledge Graph**: 556K+ verified locations with LOD metadata
- **GPT-OSS-120B**: 120B parameter LLM for reasoning over geographic context
- **Multi-Context Analysis**: Geographic coherence across multiple mentions
- **Co-occurrence Networks**: Spatial relationships between place names

## Key Innovations

### 1. Multi-Context Disambiguation
Unlike single-context approaches, we analyze multiple mentions to build geographic coherence:
- Cluster contexts by nearby location mentions
- Detect multiple referents in same document (London ON vs London UK)
- Select maximally informative contexts for LLM reasoning

### 2. Geographic Coherence
The LLM reasons over spatial relationships:
- "Fort Enterprise + Point Lake + Copper-Mine River" → coherent Arctic cluster
- "Ontario + Toronto + Hamilton" → coherent Ontario cluster

### 3. Evidence Triangulation
Multiple contexts reduce hallucination and improve confidence:
- Cross-reference mentions
- Build co-occurrence networks
- Weight by document position and specificity

## Architecture

```
oss-geoparser/
├── src/
│   ├── parsers/          # XML/NER input parsers
│   ├── clustering/       # Context clustering algorithms
│   ├── disambiguation/   # RAG-based disambiguator
│   ├── knowledge_graph/  # Neo4j interface
│   └── utils/            # Helpers and validators
├── tests/                # Unit and integration tests
├── data/                 # Sample data and schemas
├── examples/             # Usage examples
└── docs/                 # Documentation
```

## Quick Start

```python
from oss_geoparser import OSSGeoparser

# Initialize with Neo4j and LLM
geoparser = OSSGeoparser(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="your_password",
    llm_api_key="your_openrouter_key"
)

# Process XML location data
results = geoparser.process_xml("/path/to/locations.xml")

# Results include:
# - Coordinates with confidence scores
# - GeoNames/Wikidata IDs
# - Reasoning traces
# - Multi-referent detection
```

## Performance Targets

| Metric | Edinburgh | Basic RAG | OSS-Geoparser |
|--------|-----------|-----------|---------------|
| Accuracy (25-mile) | ~60% | 51% | **80-85%** |
| Multi-referent detection | No | No | **Yes** |
| LOD metadata | No | Yes | Yes |
| Explainability | Rules | Limited | **Full trace** |

## Status

🚧 **Active Development** - Building on proven RAG v3 foundation

- [x] Basic RAG implementation
- [x] Geographic context integration
- [ ] Multi-context clustering
- [ ] XML parser for Saskatchewan data
- [ ] Enhanced disambiguator
- [ ] Evaluation framework

## Citation

Based on research combining:
- Canadian LOD Knowledge Graph (GeoNames + Wikidata)
- GPT-OSS-120B (OpenRouter)
- Neo4j graph database
- Saskatchewan historical newspaper corpus

## License

Research project - University of Saskatchewan

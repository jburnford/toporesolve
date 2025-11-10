# Zero-Match Analytics Workflow

## Overview

The **Zero-Match Analytics** system tracks toponyms that returned 0 candidates from the knowledge graph. This enables a data-driven workflow for improving knowledge graph coverage through human review.

## Philosophy

Instead of adding complex name-variant matching that risks false positives, we:

1. **Gather data first** - Run processing on large corpus to identify patterns
2. **Prioritize by frequency** - Review high-frequency zero-matches first (biggest impact)
3. **Human decision** - Expert reviewer decides action for each toponym
4. **Systematic improvement** - Apply decisions to improve future runs

## How It Works

### During Processing

Every time the geoparser encounters a toponym with **0 candidates from Neo4j**:

1. The toponym name is recorded
2. Frequency counter is incremented
3. Sample context is stored (up to 3 examples per toponym)

### After Processing

At the end of document processing, the system generates:

1. **Summary Statistics** - Printed to console
   - Total unique zero-match toponyms
   - Total zero-match occurrences
   - Top 10 most frequent (preview)

2. **Review Report (JSON)** - Exported to `results/zero_match_review_*.json`
   - All toponyms with frequency ≥ 2 (configurable)
   - Sorted by frequency (most common first)
   - Sample contexts for each toponym
   - Instructions for human reviewers

## Review Report Structure

```json
{
  "metadata": {
    "description": "Zero-match toponyms for human review",
    "total_unique": 45,
    "total_occurrences": 183,
    "min_frequency": 2,
    "items_in_report": 28
  },
  "instructions": {
    "workflow": [
      "1. Review each toponym starting from highest frequency",
      "2. Check sample contexts to understand usage",
      "3. Decide action: FILTER / MAP / CREATE",
      "4. Document decision in 'action' field"
    ]
  },
  "review_items": [
    {
      "toponym": "Falls of Niagara",
      "frequency": 23,
      "contexts": [
        "...near the Falls of Niagara in Upper Canada...",
        "...traveled from Montreal to the Falls of Niagara...",
        "...the great cataract known as the Falls of Niagara..."
      ]
    }
  ]
}
```

## Human Review Process

### For Each Toponym, Decide One Action:

#### 1. **FILTER** (Ungroundable)
**When:** Toponym is too ambiguous/generic to ground reliably

**Action:** Add to `config/ambiguous_terms.txt`

**Example:**
```
# Fort is too generic without qualifier
fort

# River without name is ungroundable
river
```

**Result:** Future runs will filter this term before Neo4j query (saves API costs)

---

#### 2. **MAP** (Name Variant)
**When:** Toponym is a historical variant of an entity in the database

**Action:** Create mapping in `config/historical_aliases.json` (future feature)

**Example:**
```json
{
  "Falls of Niagara": ["Niagara Falls", "Niagara", "The Falls"],
  "Fort Niagara": ["Niagara Fort", "Old Fort Niagara"]
}
```

**Result:** Future runs will search for modern name variants automatically

---

#### 3. **CREATE** (Missing Entity)
**When:** Legitimate location that should be in knowledge graph

**Action:** Flag for database addition

**Examples:**
- Well-known location: "Falls of Niagara" (should definitely be in DB)
- Historical settlement: "Fort Vermilion" (missing from coverage area)
- Regional feature: "Lake of the Woods" (significant geographic feature)

**Result:** Add to knowledge graph import queue

---

## Example Review Session

### Top 5 Zero-Matches from P000045.toponym.xml:

```
1. "Fort Niagara" - 13 occurrences
   → ACTION: CREATE (major historical fort, should be in DB)

2. "Falls of Niagara" - 12 occurrences
   → ACTION: MAP to "Niagara Falls" (name variant)

3. "the river" - 8 occurrences
   → ACTION: FILTER (already filtered by generic_descriptor, but confirm)

4. "Canadians" - 6 occurrences
   → ACTION: FILTER (demonym, not a place)

5. "Carrying-place of the Lost Child" - 3 occurrences
   → ACTION: CREATE (specific historical portage location)
```

## Impact Analysis

### Example: If "Falls of Niagara" appears 300 times across corpus

**Before mapping:** 300 zero-match failures, 0% coverage

**After mapping:** 300 successful groundings (assuming DB has "Niagara Falls"), 100% coverage

**Estimated time saved:** ~39 hours of human review (300 × 13 sec/toponym ÷ 60 min)

## Configuration

### Minimum Frequency Threshold

Control which toponyms appear in review report:

```python
# In run_full_document.py
geoparser.zero_match_tracker.export_for_review(
    review_file,
    min_frequency=2  # Only include toponyms appearing ≥2 times
)
```

**Recommended thresholds:**
- Single document: `min_frequency=2`
- Small corpus (10-50 docs): `min_frequency=5`
- Large corpus (100+ docs): `min_frequency=10`

### Sample Context Limit

Number of example contexts stored per toponym:

```python
# In zero_match_analytics.py
# Store up to 3 sample contexts for human review
if context and len(self.zero_matches[toponym]['contexts']) < 3:
```

Increase if you need more context for decision-making.

## Workflow Integration

### Current Setup

The zero-match tracker is automatically enabled in `OSSGeoparser`:

```python
# Initialized automatically
self.zero_match_tracker = ZeroMatchTracker()
self.disambiguator.zero_match_tracker = self.zero_match_tracker
```

No configuration needed - it just works!

### Future Enhancements

1. **Historical Aliases File Support**
   - Load `config/historical_aliases.json`
   - Query Neo4j with both original and mapped names
   - Log which variant matched

2. **Batch Review Dashboard**
   - Web interface for reviewing zero-matches
   - Side-by-side comparison with candidate photos/descriptions
   - One-click actions (FILTER/MAP/CREATE)

3. **Automated Pattern Detection**
   - Machine learning to suggest likely actions
   - Pattern matching for common transformations
   - Confidence scores for auto-application

## Best Practices

### 1. Review High-Frequency Items First
- Biggest impact on coverage
- Example: Fixing 1 toponym with 50 occurrences > fixing 10 toponyms with 1 occurrence each

### 2. Look for Systematic Patterns
- If "Falls of X" is common, consider implementing a global transform
- If many demonyms appear, add to filter list

### 3. Balance Precision vs Recall
- **FILTER** if uncertain → preserves precision
- **MAP** if confident variant → improves recall
- **CREATE** if definite gap → improves coverage

### 4. Document Decisions
- Add comments to `ambiguous_terms.txt` explaining why
- Keep review report with action annotations for audit trail

### 5. Iterative Improvement
- Run → Review → Apply fixes → Run again
- Track coverage improvement over iterations

## Performance Benefits

### API Cost Savings

Filtering ungroundable terms **before** Neo4j query:

- **Before:** 100 zero-matches × 10 sec/query = 1,000 seconds wasted
- **After filtering:** 0 queries for filtered terms = 0 seconds wasted

### Human Review Efficiency

Frequency-sorted review prioritizes high-impact items:

- Reviewing top 10 items might cover 80% of zero-match occurrences
- Pareto principle: 20% of unique terms cause 80% of failures

## Support

For questions or issues:
- See examples in `examples/run_full_document.py`
- Check source: `src/utils/zero_match_analytics.py`
- Review running job log: `results/full_document_run.log`

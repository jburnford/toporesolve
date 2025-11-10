# Migration Guide: XML Format Changes

## Overview

The Saskatchewan toponym corpus has migrated to a **simplified XML format** that separates text content from entity annotations. This document describes the changes required to support the new format.

**Date**: January 2025
**Status**: MIGRATION REQUIRED
**Impact**: HIGH - All XML parsing code needs updates

---

## Format Comparison

### Old Format (Expected by Current Code)

**File**: `toponym_xml_parser.py` expects this structure

```xml
<document id="P000045" source_file="..." location_count="N">
  <toponyms>
    <toponym name="London" mention_count="10">
      <mention paragraph_id="p100" char_start="15234" char_end="15240">
        <nearby_entities>
          <toponyms>
            <toponym>England</toponym>
            <toponym>Thames</toponym>
          </toponyms>
          <water_bodys>
            <water_body>Thames River</water_body>
          </water_bodys>
          <administrative_regions>
            <administrative_region>England</administrative_region>
          </administrative_regions>
        </nearby_entities>
      </mention>
    </toponym>
  </toponyms>
  <!-- Text paragraphs NOT included in old format -->
</document>
```

**Key Features (Old)**:
- No text content included (paragraphs missing)
- `<nearby_entities>` pre-calculated within each `<mention>`
- Entity types: toponyms, water_bodys, landforms, administrative_regions, routes
- No access to paragraph text for context extraction

### New Format (Current Corpus)

**File**: `*.toponym.xml` in `/home/jic823/saskatchewan_toponym_xml/`

```xml
<document id="P000045" source_file="P000045.toponym.ner.json"
          total_entity_count="1223" total_mention_count="16807">
  <text paragraph_count="770">
    <paragraph id="p0" char_start="0" char_end="7">TRAVELS</paragraph>
    <paragraph id="p30" char_start="3542" char_end="3938">
      IN the year 1760, soon after the conquest of Canada, I resolved
      to take a voyage to London, to settle my affairs there.
    </paragraph>
  </text>

  <entities>
    <toponyms unique_count="303" mention_count="5167">
      <toponym name="London" mention_count="10">
        <mention paragraph_id="p30" char_start="3612" char_end="3618"/>
        <mention paragraph_id="p100" char_start="15234" char_end="15240"/>
      </toponym>
    </toponyms>
  </entities>
</document>
```

**Key Features (New)**:
- **Full text included**: `<text>` section with all paragraphs
- **Clean separation**: Text separate from annotations
- **No pre-calculated nearby entities**: Must be computed on-the-fly
- **Simplified mentions**: Only paragraph_id and character offsets
- **Document-level offsets**: All char_start/char_end relative to document start

---

## Key Differences

| Feature | Old Format | New Format |
|---------|-----------|------------|
| **Text Content** | ❌ Not included | ✅ Full text in `<text>` section |
| **Paragraph Access** | ❌ No paragraph text | ✅ All paragraphs with IDs |
| **Nearby Entities** | ✅ Pre-calculated in XML | ❌ Must calculate on-the-fly |
| **Entity Types** | Multiple (water bodies, landforms, etc.) | Currently only toponyms |
| **Character Offsets** | Mention-level only | Document-level (consistent) |
| **File Size** | Smaller (no text) | Larger (includes full text) |

---

## Files Requiring Updates

### 1. `src/parsers/toponym_xml_parser.py` ⚠️ CRITICAL

**Current Status**: Expects OLD format with pre-calculated nearby entities

**Lines Requiring Changes**:
- **Lines 149-181**: `_parse_toponym_mentions()` expects `<nearby_entities>` subelement
- **Lines 197-225**: `_build_context_text()` should work but needs testing
- **Lines 127-137**: `_load_paragraphs()` should work with new format ✅

**Required Changes**:

#### Change 1: Remove `<nearby_entities>` Parsing

**Current code (lines 149-181)**:
```python
# Extract nearby entities (already done in XML!)
nearby_entities = mention_elem.find('nearby_entities')

nearby_toponyms = []
nearby_water_bodies = []
# ... etc
```

**New approach**:
```python
# Nearby entities NOT in new format - will calculate later
nearby_toponyms = []
nearby_water_bodies = []
nearby_landforms = []
nearby_admin_regions = []
nearby_routes = []
```

#### Change 2: Calculate Proximity Entities On-The-Fly

**New method needed**:
```python
def _calculate_proximity_entities(
    self,
    mention_para_id: str,
    mention_start: int,
    mention_end: int,
    all_toponyms: List[Tuple[str, str, int, int]],
    window: int = 500
) -> Dict[str, List[str]]:
    """
    Calculate toponyms near a mention (within window characters)

    Args:
        mention_para_id: Paragraph containing mention
        mention_start: Document-level char offset (start)
        mention_end: Document-level char offset (end)
        all_toponyms: List of (name, para_id, start, end) for all toponyms
        window: Character distance threshold

    Returns:
        Dict with 'nearby_toponyms' list
    """
    nearby = []

    for name, para_id, start, end in all_toponyms:
        # Skip self-mention
        if start == mention_start and end == mention_end:
            continue

        # Calculate distance (document-level offsets)
        distance = min(
            abs(start - mention_end),
            abs(end - mention_start)
        )

        if distance <= window:
            nearby.append(name)

    return {
        'nearby_toponyms': nearby,
        'nearby_water_bodies': [],  # Not in new format
        'nearby_landforms': [],
        'nearby_admin_regions': [],
        'nearby_routes': []
    }
```

#### Change 3: Update `parse_file()` Method

**Lines 80-86** need modification to:
1. First collect ALL mention locations across all toponyms
2. Then for each toponym, calculate proximity to other mentions

**Pseudo-code**:
```python
def parse_file(self, xml_path: str) -> List[LocationMention]:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Step 1: Load paragraphs
    self._load_paragraphs(root)

    # Step 2: Collect ALL toponym mentions (for proximity calculation)
    all_mentions = []
    for toponym_elem in root.findall('.//toponym'):
        name = toponym_elem.get('name')
        for mention_elem in toponym_elem.findall('mention'):
            all_mentions.append((
                name,
                mention_elem.get('paragraph_id'),
                int(mention_elem.get('char_start')),
                int(mention_elem.get('char_end'))
            ))

    # Step 3: Parse each toponym with proximity calculation
    mentions = []
    for toponym_elem in root.findall('.//toponym'):
        toponym_name = toponym_elem.get('name')
        mention_count = int(toponym_elem.get('mention_count', 0))

        contexts = []
        for mention_elem in toponym_elem.findall('mention'):
            para_id = mention_elem.get('paragraph_id')
            char_start = int(mention_elem.get('char_start'))
            char_end = int(mention_elem.get('char_end'))

            # Calculate proximity entities
            proximity = self._calculate_proximity_entities(
                para_id, char_start, char_end, all_mentions
            )

            # Build context text
            context_text = self._build_context_text(para_id, char_start, char_end)

            # Create LocationContext
            context = LocationContext(
                text=context_text,
                nearby_locations=proximity['nearby_toponyms'],
                position_in_doc=self._calculate_position(para_id)
            )
            contexts.append(context)

        # Create LocationMention
        mention = LocationMention(
            name=toponym_name,
            mention_count=mention_count,
            contexts=contexts,
            document_id=root.get('id'),
            all_doc_locations=[name for name, _, _, _ in all_mentions]
        )
        mentions.append(mention)

    return mentions
```

### 2. `scripts/analyze_corpus_toponyms.py` ✅ COMPATIBLE

**Current Status**: Uses `ToponymXMLParser`, will work once parser is fixed

**Lines 47-54**: Calls `parser.parse_file()` - no changes needed

**Lines 34**: File glob pattern `*.toponym.xml` matches new format ✅

### 3. `scripts/extract_ambiguous_contexts.py` ⚠️ NEEDS UPDATE

**Current Status**: Expects `.txt` files, not XML

**Required Changes**: Rewrite to use new XML format

**New approach**:
```python
def extract_contexts(toponym, corpus_dir, window=150):
    """Extract contexts from new XML format"""
    corpus_path = Path(corpus_dir)
    contexts = []

    for xml_file in sorted(corpus_path.glob("*.toponym.xml")):
        tree = ET.parse(xml_file)
        root = tree.getroot()
        doc_id = root.get('id')

        # Load paragraphs
        paragraphs = {}
        for para in root.findall('.//paragraph'):
            paragraphs[para.get('id')] = para.text or ''

        # Find toponym
        for toponym_elem in root.findall(f'.//toponym[@name="{toponym}"]'):
            for mention in toponym_elem.findall('mention'):
                para_id = mention.get('paragraph_id')
                char_start = int(mention.get('char_start'))
                char_end = int(mention.get('char_end'))

                # Get paragraph text
                para_text = paragraphs.get(para_id, '')

                # Calculate position within paragraph (approximate)
                # Note: char_start is document-level, need to convert

                # Extract context window
                context = para_text  # Simplified: use full paragraph

                contexts.append({
                    'document': doc_id,
                    'paragraph': para_id,
                    'toponym': toponym,
                    'char_start': char_start,
                    'char_end': char_end,
                    'context': context
                })

    return contexts
```

### 4. `scripts/build_corpus_cache.py` - ✅ COMPATIBLE (via parser)

Uses `ToponymXMLParser`, will work once parser is fixed.

---

## Testing Strategy

### Phase 1: Update Parser

1. ✅ Create backup of `toponym_xml_parser.py`
2. ⚠️ Implement proximity entity calculation method
3. ⚠️ Update `_parse_toponym_mentions()` to remove nearby entity parsing
4. ⚠️ Update `parse_file()` to collect all mentions first
5. ✅ Keep `_load_paragraphs()`, `_build_context_text()` unchanged

### Phase 2: Test with Sample File

```bash
python3 -c "
from src.parsers.toponym_xml_parser import ToponymXMLParser

parser = ToponymXMLParser(context_paragraphs=2)
mentions = parser.parse_file('/home/jic823/saskatchewan_toponym_xml/P000045.toponym.xml')

print(f'Parsed {len(mentions)} unique toponyms')
print(f'First toponym: {mentions[0].name}')
print(f'  Mention count: {mentions[0].mention_count}')
print(f'  Contexts: {len(mentions[0].contexts)}')
print(f'  Nearby locations: {mentions[0].contexts[0].nearby_locations}')
"
```

**Expected Output**:
```
Parsed 303 unique toponyms
First toponym: Albany
  Mention count: 2
  Contexts: 2
  Nearby locations: ['Canada', 'London', 'England', ...]
```

### Phase 3: Test Corpus Analysis

```bash
cd /home/jic823/historical-geoparser/toporesolve/oss-geoparser
python3 scripts/analyze_corpus_toponyms.py
```

Should complete without errors and generate statistics.

### Phase 4: Update Context Extraction

```bash
python3 scripts/extract_ambiguous_contexts.py London /home/jic823/saskatchewan_toponym_xml/ results/london_contexts.json
```

Should extract all London mentions with context.

---

## Proximity Entity Calculation - Design Notes

### Window Size

**Recommendation**: 500 characters (about 1-2 paragraphs)

**Rationale**:
- Captures immediate geographic context
- Avoids noise from distant mentions
- Balances precision vs recall for disambiguation

### Distance Metric

**Option 1: Document-level distance** (RECOMMENDED)
```python
distance = min(
    abs(start2 - end1),  # Distance to start
    abs(end2 - start1)   # Distance to end
)
```

**Option 2: Same-paragraph only**
```python
if para_id1 == para_id2:
    # Calculate distance within paragraph
```

**Recommendation**: Use document-level distance (more flexible)

### Performance Optimization

For large documents with many toponyms:

**Problem**: O(N²) comparison for N toponyms

**Solution 1: Spatial indexing**
```python
# Sort mentions by char_start
all_mentions_sorted = sorted(all_mentions, key=lambda x: x[2])

# For each mention, only check nearby mentions
def find_nearby(target_start, target_end, window=500):
    # Binary search for mentions within window
    nearby = []
    for name, para, start, end in all_mentions_sorted:
        if start > target_end + window:
            break  # Past window
        if end < target_start - window:
            continue  # Before window
        nearby.append(name)
    return nearby
```

**Solution 2: Paragraph-based filtering**
```python
# First filter by paragraph proximity
nearby_paragraphs = get_nearby_paragraphs(target_para_id, distance=2)

# Then calculate character distance only for mentions in nearby paragraphs
```

**Recommendation**: Start with naive O(N²), optimize if performance is an issue.

---

## Migration Checklist

- [x] Document new XML format (`docs/XML_CORPUS_FORMAT.md`)
- [x] Identify files requiring changes
- [ ] Backup current `toponym_xml_parser.py`
- [ ] Implement proximity entity calculation
- [ ] Update `toponym_xml_parser.py`
- [ ] Test with single XML file
- [ ] Update `extract_ambiguous_contexts.py`
- [ ] Test corpus analysis script
- [ ] Test London context extraction
- [ ] Update other scripts as needed
- [ ] Commit changes to Git
- [ ] Update documentation

---

## Rollback Plan

If migration fails:

1. **Restore old parser**:
   ```bash
   git checkout src/parsers/toponym_xml_parser.py
   ```

2. **Use old corpus** (if available):
   - Check if old XML format exists in backup
   - Update corpus path in scripts

3. **Gradual migration**:
   - Create `toponym_xml_parser_v2.py` for new format
   - Keep old parser for compatibility
   - Migrate scripts one at a time

---

## Future Enhancements

### 1. Cache Proximity Calculations

Pre-calculate proximity entities and save to XML:

```xml
<mention paragraph_id="p30" char_start="3612" char_end="3618">
  <proximity_entities window="500">
    <toponym distance="45">Canada</toponym>
    <toponym distance="120">England</toponym>
  </proximity_entities>
</mention>
```

**Benefit**: Faster parsing, no recalculation needed

### 2. Add Entity Types

Expand beyond toponyms:

```xml
<entities>
  <toponyms unique_count="303" mention_count="5167">...</toponyms>
  <persons unique_count="150" mention_count="800">...</persons>
  <organizations unique_count="75" mention_count="450">...</organizations>
</entities>
```

### 3. Add Grounding Results

Store disambiguation results in XML:

```xml
<toponym name="London" mention_count="10" geonames_id="2643743" wikidata_id="Q84">
  <grounding>
    <candidate geonames_id="2643743" wikidata_id="Q84" name="London, England" confidence="0.95"/>
    <candidate geonames_id="6058560" wikidata_id="Q132851" name="London, Ontario" confidence="0.05"/>
  </grounding>
  <mention paragraph_id="p30" char_start="3612" char_end="3618" resolved_to="2643743"/>
</toponym>
```

---

## Contact

**Questions?** Check:
- `docs/XML_CORPUS_FORMAT.md` - Full format specification
- `docs/CORPUS_CACHE.md` - Caching strategy
- `docs/ZERO_MATCH_WORKFLOW.md` - Disambiguation workflow

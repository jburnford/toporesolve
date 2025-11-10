# Saskatchewan Toponym XML Corpus Format

## Overview

This document describes the simplified XML format used for the Saskatchewan toponym corpus. The format separates document text from entity annotations, with precise character-level offsets for all mentions.

**Corpus Location**: `/home/jic823/saskatchewan_toponym_xml/`
**Corpus Size**: 405MB (150+ documents)
**Format Version**: Simplified XML (v2)

## XML Schema

### Document Structure

```xml
<?xml version="1.0" ?>
<document id="DOCUMENT_ID" source_file="SOURCE_FILE.json"
          total_entity_count="N" total_mention_count="M">
  <text paragraph_count="N">
    <!-- Paragraphs with text content -->
  </text>
  <entities>
    <!-- Entity annotations with mention references -->
  </entities>
</document>
```

### Root Element: `<document>`

The root element contains document-level metadata.

**Attributes**:
- `id` (string): Unique document identifier (e.g., "P000045")
- `source_file` (string): Original source file name (e.g., "P000045.toponym.ner.json")
- `total_entity_count` (int): Total number of unique entities in the document
- `total_mention_count` (int): Total number of entity mentions across all types

**Example**:
```xml
<document id="P000045" source_file="P000045.toponym.ner.json"
          total_entity_count="1223" total_mention_count="16807">
```

## Text Section

### `<text>` Element

Contains the full document text segmented into paragraphs.

**Attributes**:
- `paragraph_count` (int): Number of paragraphs in the document

**Child Elements**: Multiple `<paragraph>` elements

### `<paragraph>` Element

Each paragraph contains the text content and character offset information.

**Attributes**:
- `id` (string): Unique paragraph identifier (e.g., "p0", "p1", "p30")
- `char_start` (int): Document-level character offset where paragraph begins
- `char_end` (int): Document-level character offset where paragraph ends

**Content**: Plain text of the paragraph

**Example**:
```xml
<text paragraph_count="770">
  <paragraph id="p0" char_start="0" char_end="7">TRAVELS</paragraph>
  <paragraph id="p1" char_start="8" char_end="10">IN</paragraph>
  <paragraph id="p30" char_start="3542" char_end="3938">
    IN the year 1760, soon after the conquest of Canada, I resolved...
  </paragraph>
</text>
```

**Key Points**:
- Paragraph IDs are sequential: p0, p1, p2, ..., pN
- Character offsets are cumulative from the start of the document
- Offsets include all characters (whitespace, punctuation, etc.)
- Text content is preserved exactly as it appears in the source

## Entities Section

### `<entities>` Element

Container for all entity types in the document.

**Child Elements**: Currently contains `<toponyms>` (may expand to include other entity types in the future)

### `<toponyms>` Element

Container for all toponym (place name) entities.

**Attributes**:
- `unique_count` (int): Number of unique toponyms in the document
- `mention_count` (int): Total number of toponym mentions

**Child Elements**: Multiple `<toponym>` elements

**Example**:
```xml
<entities>
  <toponyms unique_count="303" mention_count="5167">
    <!-- Individual toponym entities -->
  </toponyms>
</entities>
```

### `<toponym>` Element

Represents a unique place name with all its mentions in the document.

**Attributes**:
- `name` (string): The normalized toponym string (e.g., "London", "Canada")
- `mention_count` (int): Number of times this toponym appears in the document

**Child Elements**: Multiple `<mention>` elements (one per occurrence)

**Example**:
```xml
<toponym name="London" mention_count="10">
  <mention paragraph_id="p100" char_start="15234" char_end="15240"/>
  <mention paragraph_id="p150" char_start="23456" char_end="23462"/>
  <!-- ... 8 more mentions -->
</toponym>
```

### `<mention>` Element

Represents a single occurrence of a toponym in the text.

**Attributes**:
- `paragraph_id` (string): Reference to the paragraph containing this mention (e.g., "p30")
- `char_start` (int): Document-level character offset where mention begins
- `char_end` (int): Document-level character offset where mention ends (exclusive)

**Content**: Empty element (self-closing)

**Example**:
```xml
<mention paragraph_id="p33" char_start="5083" char_end="5089"/>
```

**Key Points**:
- Character offsets are document-level (not paragraph-level)
- `char_end` is exclusive (Python slice notation: `text[char_start:char_end]`)
- Multiple mentions of the same toponym are grouped under one `<toponym>` element
- Paragraph reference allows quick lookup of surrounding context

## Complete Example

```xml
<?xml version="1.0" ?>
<document id="P000045" source_file="P000045.toponym.ner.json"
          total_entity_count="1223" total_mention_count="16807">
  <text paragraph_count="770">
    <paragraph id="p0" char_start="0" char_end="7">TRAVELS</paragraph>
    <paragraph id="p30" char_start="3542" char_end="3938">
      IN the year 1760, soon after the conquest of Canada, I resolved
      to take a voyage to London, to settle my affairs there.
    </paragraph>
    <paragraph id="p33" char_start="4823" char_end="5105">
      We set sail from Albany on June 3rd, bound for London with a
      cargo of furs and timber.
    </paragraph>
  </text>

  <entities>
    <toponyms unique_count="303" mention_count="5167">
      <toponym name="Albany" mention_count="2">
        <mention paragraph_id="p33" char_start="5083" char_end="5089"/>
        <mention paragraph_id="p52" char_start="16036" char_end="16042"/>
      </toponym>

      <toponym name="London" mention_count="2">
        <mention paragraph_id="p30" char_start="3612" char_end="3618"/>
        <mention paragraph_id="p33" char_start="4867" char_end="4873"/>
      </toponym>

      <toponym name="Canada" mention_count="1">
        <mention paragraph_id="p30" char_start="3585" char_end="3591"/>
      </toponym>
    </toponyms>
  </entities>
</document>
```

## Usage Patterns

### Extracting Context for a Toponym

To extract context for a specific toponym mention:

1. Find the `<toponym>` element with desired name
2. Iterate through its `<mention>` elements
3. For each mention:
   - Get `paragraph_id` to find the relevant paragraph
   - Use `char_start` and `char_end` to extract the exact mention
   - Extract surrounding text from the paragraph for context

**Example Python Code**:
```python
import xml.etree.ElementTree as ET

def extract_toponym_contexts(xml_file, toponym_name, context_window=150):
    """Extract all contexts for a specific toponym."""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Build paragraph lookup
    paragraphs = {}
    for para in root.findall('.//paragraph'):
        paragraphs[para.get('id')] = {
            'text': para.text or '',
            'char_start': int(para.get('char_start')),
            'char_end': int(para.get('char_end'))
        }

    # Find toponym
    contexts = []
    for toponym in root.findall(f'.//toponym[@name="{toponym_name}"]'):
        for mention in toponym.findall('mention'):
            para_id = mention.get('paragraph_id')
            char_start = int(mention.get('char_start'))
            char_end = int(mention.get('char_end'))

            # Get paragraph text
            para = paragraphs[para_id]
            para_text = para['text']

            # Calculate position within paragraph
            offset_in_para = char_start - para['char_start']

            # Extract context window
            context_start = max(0, offset_in_para - context_window)
            context_end = min(len(para_text), offset_in_para + len(toponym_name) + context_window)

            context = para_text[context_start:context_end]

            contexts.append({
                'document': root.get('id'),
                'paragraph': para_id,
                'char_start': char_start,
                'char_end': char_end,
                'context': context
            })

    return contexts
```

### Finding Co-occurring Toponyms (Proximity Entities)

To find other toponyms that appear near a specific mention:

1. Identify the paragraph containing the mention
2. Find all other toponym mentions in the same paragraph
3. Calculate distances based on character offsets
4. Filter by distance threshold

**Example Use Case**: Disambiguation via geographic context
- "London" near "England" → London, England
- "London" near "Ontario", "Canada" → London, Ontario

### Iterating Through All Toponyms

```python
def get_all_toponyms(xml_file):
    """Get all unique toponyms with mention counts."""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    toponyms = []
    for toponym in root.findall('.//toponym'):
        toponyms.append({
            'name': toponym.get('name'),
            'mention_count': int(toponym.get('mention_count')),
            'mentions': [
                {
                    'paragraph_id': m.get('paragraph_id'),
                    'char_start': int(m.get('char_start')),
                    'char_end': int(m.get('char_end'))
                }
                for m in toponym.findall('mention')
            ]
        })

    return toponyms
```

## Character Offset System

### Key Properties

- **Document-level**: All offsets are relative to the start of the document
- **Zero-indexed**: First character is at position 0
- **Exclusive end**: Range `[start, end)` follows Python slice notation
- **Includes all characters**: Whitespace, newlines, punctuation counted
- **Consistent across elements**: Both paragraphs and mentions use same system

### Verification

To verify offsets are correct:
```python
# Reconstruct full document text
full_text = ''.join(p['text'] for p in paragraphs.values())

# Extract mention using offsets
mention_text = full_text[char_start:char_end]

# Should match the toponym name
assert mention_text == toponym_name
```

## Corpus Statistics

### Sample Document (P000045)

- **Total entities**: 1,223
- **Total mentions**: 16,807
- **Unique toponyms**: 303
- **Toponym mentions**: 5,167
- **Paragraphs**: 770

### High-frequency Toponyms

Based on sample analysis across corpus:
- **London**: 150+ documents, ranging 1-73 mentions per document
- **Canada**: Very common (major geographic context)
- **England**: Frequent in colonial documents
- **France**: Common in historical context

## Migration Notes

### Changes from Previous Format

This simplified XML format replaces an earlier structure that likely had:
- Embedded entity annotations within text
- More complex nesting
- Possibly inline markup

### Advantages of New Format

1. **Separation of concerns**: Text content separated from annotations
2. **Efficient lookups**: All mentions of a toponym grouped together
3. **Precise offsets**: Character-level precision for exact extraction
4. **Paragraph-based context**: Easy to extract surrounding context
5. **Scalable**: Large documents don't require parsing full text to find entities

### Data Source

Original data comes from NER pipeline:
- Source files: `*.toponym.ner.json`
- Converted to simplified XML format
- Character offsets preserved from original NER output

## Future Extensions

### Potential Enhancements

1. **Additional entity types**: Persons (PER), Organizations (ORG), etc.
2. **Entity linking**: Add GeoNames/Wikidata IDs to `<toponym>` elements
3. **Disambiguation metadata**: Confidence scores, candidate entities
4. **Relationship annotations**: Co-reference, part-of relationships
5. **Temporal expressions**: Date/time entities for historical context

### Schema Evolution

If adding new entity types:
```xml
<entities>
  <toponyms unique_count="303" mention_count="5167">
    <!-- Toponym entities -->
  </toponyms>
  <persons unique_count="150" mention_count="800">
    <!-- Person entities -->
  </persons>
  <organizations unique_count="75" mention_count="450">
    <!-- Organization entities -->
  </organizations>
</entities>
```

## References

- **Corpus location**: `/home/jic823/saskatchewan_toponym_xml/`
- **Sample document**: `P000045.toponym.xml`
- **Total documents**: 150+ XML files
- **Related documentation**: See `CORPUS_CACHE.md` for grounding strategy

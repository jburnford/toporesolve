# Creating Canadian Historical Gold Standard Dataset

## Overview

Goal: Create 300-450 manually validated examples of Canadian historical toponyms (1600-1950) for evaluation.

## Using Gemini 2.5 Pro for Dataset Creation

### Why Gemini 2.5 Pro?

**Advantages**:
- **Free tier available** through AI Studio (60 requests/minute)
- **Large context window** (2M tokens) - can process entire historical documents
- **Strong reasoning** - good at historical context
- **Multilingual** - handles French and English
- **Grounding capability** - can search for verification
- **Fast** - quick iteration on examples

**Use Cases**:
1. **Extract toponyms** from historical texts
2. **Verify coordinates** for historical places
3. **Suggest historical names** and dates
4. **Generate context sentences** from sources
5. **Validate examples** against multiple sources
6. **Identify name changes** and temporal validity

### Setup

1. **Get API Key**:
   - Go to [aistudio.google.com](https://aistudio.google.com/)
   - Create project
   - Get API key

2. **Install SDK**:
```bash
pip install google-generativeai
```

3. **Test Connection**:
```python
import google.generativeai as genai

genai.configure(api_key="YOUR_API_KEY")
model = genai.GenerativeModel('gemini-2.5-pro')

response = model.generate_content("What is the historical name for Toronto before 1834?")
print(response.text)
```

### Workflow 1: Extract Toponyms from Historical Documents

**Input**: Historical document (from Library and Archives Canada, etc.)

**Prompt**:
```python
prompt = f"""
You are a historical geography expert. Analyze this Canadian historical document and extract place names (toponyms).

Document (from {year}):
{document_text}

For each toponym, provide:
1. Place name as it appears in the text
2. Type (city, province, region, river, fort, etc.)
3. Approximate modern coordinates (if known)
4. Modern equivalent name (if changed)
5. Historical context

Format as JSON array.
"""

response = model.generate_content(prompt)
toponyms = json.loads(response.text)
```

**Example Output**:
```json
[
  {
    "historical_name": "Fort Garry",
    "type": "fort/settlement",
    "modern_coordinates": [49.8951, -97.1384],
    "modern_name": "Winnipeg",
    "context": "Hudson's Bay Company headquarters, Red River Settlement",
    "year_range": "1822-1873"
  },
  {
    "historical_name": "Rupert's Land",
    "type": "region",
    "modern_coordinates": null,
    "modern_name": "Parts of MB, SK, AB, NT, ON, QC",
    "context": "Vast territory controlled by Hudson's Bay Company",
    "year_range": "1670-1870"
  }
]
```

### Workflow 2: Verify and Enrich Examples

**Input**: Potential toponym from document

**Prompt**:
```python
prompt = f"""
You are verifying a historical Canadian toponym for a research dataset.

Toponym: {toponym}
Year: {year}
Source context: {context}

Please verify and provide:
1. Precise coordinates (latitude, longitude) for this place in {year}
2. Historical accuracy check
3. Alternative names that existed in {year}
4. When this name was valid (date range)
5. What this place is called today
6. Relevant historical notes

Use your knowledge and be precise. If uncertain, explain why.
"""

response = model.generate_content(prompt)
```

**Example**:
```
Toponym: York
Year: 1820
Context: "The colonial capital at York..."

Response:
York in 1820 refers to what is now Toronto, Ontario.

Coordinates: 43.6532°N, 79.3832°W (approximate center of 1820 settlement)
Historical accuracy: ✓ Confirmed - York was the official name 1793-1834
Alternative names: "Muddy York" (nickname), "Town of York"
Name validity: 1793-1834
Modern name: Toronto (renamed March 6, 1834)
Notes: Founded as capital of Upper Canada by John Graves Simcoe.
       Named after Prince Frederick, Duke of York. Changed to Toronto
       (from Mohawk word) when incorporated as a city.
```

### Workflow 3: Generate Context Sentences

**Input**: Toponym with basic info

**Prompt**:
```python
prompt = f"""
Generate a realistic historical sentence mentioning the Canadian place "{toponym}" as it would have appeared in a document from {year}.

Requirements:
- Accurate historical context for that time period
- Natural language (as if from a newspaper, letter, or official document)
- Include relevant historical events or details
- 1-2 sentences
- Appropriate tone for the era

Place: {toponym}
Year: {year}
Type: {entity_type}
"""

response = model.generate_content(prompt)
```

**Example Output**:
```
"The Red River Rebellion began near Fort Garry in November 1869,
when Louis Riel and the Métis National Committee seized the fort
to resist the transfer of Rupert's Land to the Dominion of Canada."
```

### Workflow 4: Batch Validation

**Input**: List of potential examples

**Prompt**:
```python
prompt = f"""
You are validating historical toponyms for a research dataset.
Review these examples and flag any issues.

Examples:
{json.dumps(examples, indent=2)}

For each example, check:
1. Are the coordinates accurate for that historical period?
2. Was this name actually used in that year?
3. Is the context historically accurate?
4. Are there any anachronisms?
5. Overall quality (Good/Fair/Poor)

Provide detailed feedback on any issues.
"""

response = model.generate_content(prompt)
```

## Manual Creation Process

### Step 1: Source Selection

**Choose diverse sources**:
- Library and Archives Canada digitized newspapers
- Early Canadiana Online books
- Provincial archives
- Hudson's Bay Company records
- Railway historical documents

**Distribution targets**:
- Mix of time periods (1600-1763, 1763-1867, 1867-1950)
- Various provinces/territories
- English and French sources
- Urban and rural places
- Different entity types (GPE, LOC, FAC)

### Step 2: Initial Extraction (Gemini-Assisted)

```python
import google.generativeai as genai
import json

genai.configure(api_key="YOUR_API_KEY")
model = genai.GenerativeModel('gemini-2.5-pro')

def extract_toponyms_from_document(document_text, source_year):
    prompt = f"""
    Extract all Canadian place names from this historical document from {source_year}.

    Document:
    {document_text}

    Return JSON array with: historical_name, type, context_sentence,
    estimated_coordinates, modern_name, notes.
    """

    response = model.generate_content(prompt)
    return json.loads(response.text)

# Process multiple documents
for doc in historical_documents:
    toponyms = extract_toponyms_from_document(doc['text'], doc['year'])
    # Save for manual review
    save_candidates(toponyms)
```

### Step 3: Manual Verification

**For each extracted toponym**:

1. **Verify coordinates** using:
   - GeoNames
   - OpenStreetMap historical data
   - Historical maps (David Rumsey Map Collection)
   - Provincial/territorial gazetteers
   - Google Maps (for modern equivalent)

2. **Verify temporal validity**:
   - Check when name was actually used
   - Confirm historical events match the period
   - Look for name change dates

3. **Verify context**:
   - Ensure context sentence is historically accurate
   - Check for anachronisms
   - Verify related place names mentioned

4. **Cross-reference** multiple sources:
   - Wikidata
   - Canadian Geographic Names Database
   - Provincial archives
   - Academic historical sources

### Step 4: Gemini-Assisted Verification

```python
def verify_toponym(toponym_data):
    prompt = f"""
    Verify this historical Canadian toponym entry:

    {json.dumps(toponym_data, indent=2)}

    Check:
    1. Are coordinates accurate for {toponym_data['year']}?
    2. Was this name used in {toponym_data['year']}?
    3. Is the historical context accurate?
    4. Any errors or concerns?

    Provide verification report with confidence level (High/Medium/Low).
    """

    response = model.generate_content(prompt)
    return response.text

# Verify each candidate
for candidate in candidates:
    verification = verify_toponym(candidate)
    candidate['verification'] = verification

    # Flag low-confidence for manual review
    if 'Low' in verification or 'concern' in verification.lower():
        candidate['needs_review'] = True
```

### Step 5: Quality Control

**Criteria**:
- ✓ Coordinates verified against 2+ sources
- ✓ Name validity confirmed in historical records
- ✓ Context factually accurate
- ✓ No anachronisms
- ✓ Entity type correctly identified
- ✓ Temporal info complete

**Peer Review**:
- Have second researcher review flagged examples
- Discuss ambiguous cases
- Document disagreements and resolutions

## Example Creation Script

```python
import google.generativeai as genai
import json
from datetime import datetime

class CanadianGoldStandardCreator:
    def __init__(self, gemini_api_key):
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.5-pro')
        self.examples = []

    def extract_from_source(self, source_text, source_metadata):
        """Extract toponyms from historical source"""
        prompt = f"""
        Extract Canadian place names from this {source_metadata['year']} document.

        Source: {source_metadata['title']}
        Year: {source_metadata['year']}

        Document:
        {source_text}

        Return JSON array of toponyms with context.
        """

        response = self.model.generate_content(prompt)
        return json.loads(response.text)

    def verify_toponym(self, toponym, year, context):
        """Verify a single toponym"""
        prompt = f"""
        Verify this Canadian historical toponym:

        Name: {toponym}
        Year: {year}
        Context: {context}

        Provide:
        1. Precise coordinates in {year}
        2. Name validity period
        3. Modern equivalent name
        4. Historical accuracy assessment
        5. Confidence level (High/Medium/Low)

        Format as JSON.
        """

        response = self.model.generate_content(prompt)
        return json.loads(response.text)

    def create_gold_standard_entry(self, toponym_data):
        """Create formatted gold standard entry"""

        # Verify with Gemini
        verification = self.verify_toponym(
            toponym_data['name'],
            toponym_data['year'],
            toponym_data['context']
        )

        # Create entry
        entry = {
            "lat_long": verification['coordinates'],
            "entity": toponym_data['name'],
            "entity_label": toponym_data['type'],
            "context": {
                "sents": [{
                    "sent": toponym_data['context'],
                    "rng": [0, len(toponym_data['context'])]
                }]
            },
            "link": toponym_data.get('source_url', ''),
            "title": toponym_data.get('source_title', ''),
            "published": toponym_data['year'],
            "source": toponym_data.get('source', 'LAC'),
            "year": toponym_data['year'],
            "modern_name": verification.get('modern_name'),
            "name_valid_from": verification.get('valid_from'),
            "name_valid_to": verification.get('valid_to'),
            "verification": verification,
            "created_at": datetime.now().isoformat(),
            "needs_manual_review": verification.get('confidence') != 'High'
        }

        return entry

    def batch_create(self, source_documents):
        """Process multiple source documents"""
        for doc in source_documents:
            # Extract toponyms
            toponyms = self.extract_from_source(doc['text'], doc['metadata'])

            # Create entries
            for toponym in toponyms:
                entry = self.create_gold_standard_entry({
                    **toponym,
                    'year': doc['metadata']['year'],
                    'source_url': doc['metadata'].get('url'),
                    'source_title': doc['metadata'].get('title'),
                })

                self.examples.append(entry)

        return self.examples

    def save(self, filename):
        """Save gold standard dataset"""
        with open(filename, 'w', encoding='utf-8') as f:
            for entry in self.examples:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')

        # Save items needing review separately
        needs_review = [e for e in self.examples if e.get('needs_manual_review')]
        if needs_review:
            with open(filename.replace('.jsonl', '_review.jsonl'), 'w') as f:
                for entry in needs_review:
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')

        print(f"Saved {len(self.examples)} examples")
        print(f"{len(needs_review)} need manual review")


# Usage
creator = CanadianGoldStandardCreator(api_key="YOUR_GEMINI_KEY")

# Sample source documents (from LAC, ECO, etc.)
sources = [
    {
        'text': "The Red River Rebellion began near Fort Garry in 1869...",
        'metadata': {
            'year': '1869',
            'title': 'Manitoba Historical Documents',
            'url': 'https://www.bac-lac.gc.ca/...'
        }
    },
    # Add more sources
]

examples = creator.batch_create(sources)
creator.save('data/canadian_historical_gold_standard.jsonl')
```

## Cost Estimation

### Gemini 2.5 Pro Pricing (as of 2024)

**AI Studio Free Tier**:
- 60 requests per minute
- 1,500 requests per day
- 1 million requests per month
- **Free for moderate use**

**Paid Tier** (if needed):
- Input: ~$1.25 per 1M tokens
- Output: ~$5 per 1M tokens
- Very cheap for this use case

**Estimated Costs** for 400 examples:

| Task | Requests | Est. Cost |
|------|----------|-----------|
| Extract toponyms | ~50 docs | $0.50 |
| Verify toponyms | 400 | $2.00 |
| Generate context | 100 | $0.50 |
| Validation | 400 | $1.00 |
| **Total** | | **~$4** |

**Likely free** under daily limits if spread over a few days.

## Quality Metrics

### Target Metrics
- **Inter-annotator agreement**: >90% for coordinates
- **Temporal accuracy**: 100% (names valid in specified years)
- **Geographic coverage**: All provinces/territories represented
- **Temporal coverage**: All three historical periods
- **Language balance**: 70% English, 25% French, 5% Indigenous

### Validation Checks
- [ ] All coordinates within Canadian boundaries
- [ ] Temporal validity confirmed in historical records
- [ ] No anachronisms in context
- [ ] Entity types correct
- [ ] Source URLs accessible
- [ ] Duplicate detection complete

## Timeline

**Week 1**: Source gathering and Gemini setup
- Identify 50-100 source documents
- Set up Gemini API
- Create extraction scripts

**Week 2**: Initial extraction
- Run Gemini extraction on sources
- Generate 600-800 candidates

**Week 3**: Verification and filtering
- Gemini-assisted verification
- Manual review of flagged items
- Reduce to 400-500 high-quality examples

**Week 4**: Final validation
- Peer review
- Final quality checks
- Format and document dataset

**Total time**: ~40-60 hours of work (with Gemini assistance)

## Best Practices

1. **Use Gemini for first pass, not final decision**
   - Gemini extracts and suggests
   - Humans verify and validate

2. **Document everything**
   - Keep verification notes
   - Track sources meticulously
   - Record decision rationale

3. **Batch processing**
   - Process similar items together
   - Use consistent prompts
   - Save intermediate results

4. **Iterative improvement**
   - Start with 20-30 examples
   - Refine process based on learnings
   - Scale to full dataset

5. **Version control**
   - Git track the dataset
   - Document changes
   - Tag versions

## Next Steps

1. **Set up Gemini API** and test extraction
2. **Identify 20 diverse source documents** from LAC
3. **Create 20 pilot examples** with Gemini assistance
4. **Manually verify** pilot examples
5. **Refine workflow** based on pilot
6. **Scale to 400 examples**
7. **Final peer review and validation**

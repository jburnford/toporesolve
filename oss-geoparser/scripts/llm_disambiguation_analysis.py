"""
LLM-Based Disambiguation Analysis for Ambiguous Toponyms

Uses LLM to analyze sampled contexts and determine:
1. Which referents are present in the corpus
2. What patterns distinguish different referents
3. Whether corpus-level caching or per-mention disambiguation is needed

Approach:
- Extract representative sample of contexts (stratified by proximity patterns)
- Use LLM to classify each context
- Aggregate results to determine disambiguation strategy

Usage:
    python llm_disambiguation_analysis.py London --sample-size 50
    python llm_disambiguation_analysis.py Victoria --sample-size 50
"""

import sys
import os
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Tuple
import json
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from parsers.toponym_xml_parser_v2 import ToponymXMLParserV2


# Candidate referents for common ambiguous toponyms
CANDIDATE_REFERENTS = {
    'London': [
        {
            'name': 'London, England',
            'geonames_id': 2643743,
            'wikidata_id': 'Q84',
            'description': 'Capital of England and United Kingdom',
            'indicators': ['England', 'Thames', 'British', 'Europe', 'UK']
        },
        {
            'name': 'London, Ontario, Canada',
            'geonames_id': 6058560,
            'wikidata_id': 'Q132851',
            'description': 'City in southwestern Ontario, Canada',
            'indicators': ['Ontario', 'Canada', 'Canadian', 'Toronto']
        },
    ],
    'Victoria': [
        {
            'name': 'Victoria, British Columbia, Canada',
            'geonames_id': 6174041,
            'wikidata_id': 'Q2132',
            'description': 'Capital of British Columbia, Canada',
            'indicators': ['British Columbia', 'BC', 'Vancouver', 'Canada']
        },
        {
            'name': 'Queen Victoria',
            'geonames_id': None,
            'wikidata_id': 'Q9439',
            'description': 'Queen of the United Kingdom (1837-1901)',
            'indicators': ['Queen', 'Royal', 'Majesty', 'reign', 'monarch']
        },
        {
            'name': 'Victoria, Australia',
            'geonames_id': 2145234,
            'wikidata_id': 'Q36687',
            'description': 'State in southeastern Australia',
            'indicators': ['Australia', 'Melbourne', 'Australian']
        },
        {
            'name': 'Lake Victoria',
            'geonames_id': 149830,
            'wikidata_id': 'Q5511',
            'description': 'Large lake in Africa',
            'indicators': ['Lake', 'Africa', 'Nile', 'Uganda']
        },
    ]
}


def extract_stratified_sample(toponym: str, corpus_dir: str, sample_size: int = 50) -> List[Dict]:
    """
    Extract stratified sample of contexts for LLM analysis

    Strategy: Sample across different proximity entity patterns to ensure
    diverse representation of potential referents

    Args:
        toponym: The toponym to analyze
        corpus_dir: Directory containing XML files
        sample_size: Number of contexts to sample

    Returns:
        List of sampled context dictionaries
    """
    corpus_path = Path(corpus_dir)
    parser = ToponymXMLParserV2(context_paragraphs=2, proximity_window=500)

    all_contexts = []

    print(f"Extracting contexts for '{toponym}'...")
    print()

    # Find XML files with this toponym
    xml_files = []
    for xml_file in sorted(corpus_path.glob("*.toponym.xml")):
        with open(xml_file) as f:
            if f'name="{toponym}"' in f.read():
                xml_files.append(xml_file)

    print(f"Found {len(xml_files)} documents with '{toponym}'")

    # Extract all contexts
    for i, xml_file in enumerate(xml_files, 1):
        if i % 20 == 0:
            print(f"Processed {i}/{len(xml_files)} files...")

        try:
            mentions = parser.parse_file(str(xml_file))

            for mention in mentions:
                if mention.name == toponym:
                    for context in mention.contexts:
                        all_contexts.append({
                            'document': mention.document_id,
                            'toponym': toponym,
                            'context_text': context.text,
                            'nearby_entities': context.nearby_locations[:15],  # Limit for prompt
                            'position_in_doc': context.position_in_doc
                        })
                    break

        except Exception as e:
            print(f"Error parsing {xml_file.name}: {e}")

    print(f"✓ Extracted {len(all_contexts)} total contexts")
    print()

    # Stratified sampling based on proximity patterns
    # Group contexts by which indicators they contain
    if toponym in CANDIDATE_REFERENTS:
        referent_candidates = CANDIDATE_REFERENTS[toponym]
        context_groups = defaultdict(list)

        for ctx in all_contexts:
            nearby_lower = set(e.lower() for e in ctx['nearby_entities'])

            # Check which referent's indicators appear
            matches = []
            for ref in referent_candidates:
                indicators_lower = set(i.lower() for i in ref['indicators'])
                if nearby_lower & indicators_lower:
                    matches.append(ref['name'])

            if not matches:
                group_key = 'no_clear_indicators'
            elif len(matches) == 1:
                group_key = matches[0]
            else:
                group_key = 'mixed_indicators'

            context_groups[group_key].append(ctx)

        # Sample from each group proportionally
        print("Context distribution by indicator patterns:")
        for group, contexts in context_groups.items():
            print(f"  {group}: {len(contexts)} contexts")
        print()

        # Sample proportionally with minimum from each group
        sampled = []
        total = len(all_contexts)

        for group, contexts in context_groups.items():
            # Proportional sample size
            group_sample_size = max(5, int(sample_size * len(contexts) / total))
            group_sample_size = min(group_sample_size, len(contexts))

            sampled.extend(random.sample(contexts, group_sample_size))

        # If we don't have enough, randomly sample more
        if len(sampled) < sample_size:
            remaining = [c for c in all_contexts if c not in sampled]
            additional = min(sample_size - len(sampled), len(remaining))
            sampled.extend(random.sample(remaining, additional))

        sampled = sampled[:sample_size]

    else:
        # Simple random sampling if no candidate referents defined
        sampled = random.sample(all_contexts, min(sample_size, len(all_contexts)))

    print(f"Sampled {len(sampled)} contexts for LLM analysis")
    print()

    return sampled


def generate_llm_prompt(toponym: str, contexts: List[Dict]) -> str:
    """
    Generate LLM prompt for disambiguation analysis

    Args:
        toponym: The toponym being analyzed
        contexts: List of context dictionaries

    Returns:
        Formatted prompt string
    """
    # Get candidate referents
    if toponym not in CANDIDATE_REFERENTS:
        referents_desc = "Unknown - please identify possible referents"
    else:
        referents = CANDIDATE_REFERENTS[toponym]
        referents_desc = "\n".join([
            f"{i+1}. {ref['name']}: {ref['description']}"
            for i, ref in enumerate(referents)
        ])

    prompt = f"""You are analyzing mentions of the ambiguous toponym "{toponym}" in historical documents about Saskatchewan, Canada (late 1800s - early 1900s).

TASK:
For each context below, determine which specific place the author is referring to. Consider the full text context and nearby place names.

CANDIDATE REFERENTS:
{referents_desc}

INSTRUCTIONS:
1. Read each context carefully
2. Consider:
   - Geographic context from nearby place names
   - Historical context (time period, subject matter)
   - Text clues (descriptive phrases, relationships mentioned)
3. Classify each mention as one of the candidate referents
4. If you're unsure or the context is ambiguous, say "AMBIGUOUS" and explain why
5. Note any patterns you observe across multiple contexts

CONTEXTS TO ANALYZE:
"""

    for i, ctx in enumerate(contexts, 1):
        nearby_str = ', '.join(ctx['nearby_entities']) if ctx['nearby_entities'] else 'none'

        prompt += f"\n{'='*80}\n"
        prompt += f"CONTEXT {i} (Document: {ctx['document']})\n"
        prompt += f"Nearby places: {nearby_str}\n"
        prompt += f"\nText:\n{ctx['context_text']}\n"

    prompt += f"\n{'='*80}\n\n"
    prompt += """REQUIRED OUTPUT FORMAT:

For each context, provide:
Context N: [Referent Name]
Confidence: [High/Medium/Low]
Reasoning: [Brief explanation]

Then provide:
SUMMARY:
- Dominant referent (if any): [Name and percentage]
- Ambiguous cases: [Number and patterns]
- Recommendation: [Corpus-level cache OR per-mention disambiguation]
- Key distinguishing features: [What helps identify each referent]
"""

    return prompt


def main():
    """Run LLM-based disambiguation analysis"""

    if len(sys.argv) < 2:
        print("Usage: python llm_disambiguation_analysis.py <toponym> [--sample-size N]")
        print("Example: python llm_disambiguation_analysis.py London --sample-size 50")
        sys.exit(1)

    toponym = sys.argv[1]

    # Parse optional arguments
    sample_size = 50
    if '--sample-size' in sys.argv:
        idx = sys.argv.index('--sample-size')
        if idx + 1 < len(sys.argv):
            sample_size = int(sys.argv[idx + 1])

    corpus_dir = os.path.expanduser("~/saskatchewan_toponym_xml")

    print("=" * 80)
    print(f"LLM-BASED DISAMBIGUATION ANALYSIS: {toponym}")
    print("=" * 80)
    print()

    # Extract stratified sample
    sampled_contexts = extract_stratified_sample(toponym, corpus_dir, sample_size)

    # Generate LLM prompt
    prompt = generate_llm_prompt(toponym, sampled_contexts)

    # Save prompt and contexts
    output_dir = "results"
    os.makedirs(output_dir, exist_ok=True)

    # Save sampled contexts
    contexts_file = f"{output_dir}/{toponym.lower()}_sampled_contexts.json"
    with open(contexts_file, 'w') as f:
        json.dump({
            'toponym': toponym,
            'sample_size': len(sampled_contexts),
            'contexts': sampled_contexts
        }, f, indent=2)

    print(f"✓ Saved sampled contexts to: {contexts_file}")

    # Save LLM prompt
    prompt_file = f"{output_dir}/{toponym.lower()}_llm_prompt.txt"
    with open(prompt_file, 'w') as f:
        f.write(prompt)

    print(f"✓ Saved LLM prompt to: {prompt_file}")
    print()

    print("=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print(f"1. Review the prompt: {prompt_file}")
    print(f"2. Send prompt to LLM (Claude, GPT-4, or similar)")
    print(f"3. Analyze LLM response to determine:")
    print(f"   - Is one referent dominant (>90%)? → Add to corpus cache")
    print(f"   - Are multiple referents common? → Use per-mention disambiguation")
    print(f"   - What features distinguish referents? → Update disambiguation logic")
    print()

    # Also print first part of prompt for review
    print("PROMPT PREVIEW (first 1500 characters):")
    print("-" * 80)
    print(prompt[:1500])
    if len(prompt) > 1500:
        print(f"\n[... {len(prompt) - 1500} more characters ...]")
    print()


if __name__ == "__main__":
    main()

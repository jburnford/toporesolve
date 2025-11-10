"""
Analyze Ambiguous Toponym Disambiguation Patterns

Extracts all contexts for a highly ambiguous toponym (like London or Victoria)
and analyzes proximity entities to determine:
1. Which referent is most common in the corpus
2. What proximity patterns distinguish different referents
3. Whether we can add to corpus cache or need per-mention disambiguation

Usage:
    python analyze_ambiguous_toponym.py London
    python analyze_ambiguous_toponym.py Victoria
"""

import sys
import os
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Tuple
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from parsers.toponym_xml_parser_v2 import ToponymXMLParserV2


# Known referents for analysis
KNOWN_REFERENTS = {
    'London': {
        'London, England': ['England', 'Thames', 'British', 'Europe', 'UK', 'English'],
        'London, Ontario': ['Ontario', 'Canada', 'Canadian', 'Toronto'],
        'London, Kentucky': ['Kentucky', 'USA', 'United States'],
    },
    'Victoria': {
        'Victoria, BC': ['British Columbia', 'BC', 'Vancouver', 'Canada', 'Canadian'],
        'Victoria (Queen)': ['Queen', 'Royal', 'Crown', 'Majesty', 'Empire', 'reign'],
        'Victoria, Australia': ['Australia', 'Melbourne', 'Australian'],
        'Lake Victoria': ['Lake', 'Africa', 'Nile'],
    }
}


def analyze_toponym(toponym: str, corpus_dir: str):
    """
    Analyze all mentions of a toponym across corpus

    Args:
        toponym: The toponym to analyze (e.g., 'London')
        corpus_dir: Directory containing XML files

    Returns:
        Analysis dictionary with statistics and patterns
    """
    corpus_path = Path(corpus_dir)
    parser = ToponymXMLParserV2(context_paragraphs=2, proximity_window=500)

    # Statistics
    total_mentions = 0
    docs_with_toponym = 0
    all_proximity_entities = []
    proximity_by_doc = defaultdict(list)

    # Sample contexts for manual review
    sample_contexts = []

    print(f"Analyzing '{toponym}' across corpus...")
    print()

    # Find all XML files with this toponym
    xml_files = []
    for xml_file in sorted(corpus_path.glob("*.toponym.xml")):
        # Quick check if file contains toponym
        with open(xml_file) as f:
            if f'name="{toponym}"' in f.read():
                xml_files.append(xml_file)

    print(f"Found {len(xml_files)} documents containing '{toponym}'")
    print()

    # Parse each file
    for i, xml_file in enumerate(xml_files, 1):
        if i % 20 == 0:
            print(f"Processed {i}/{len(xml_files)} files...")

        try:
            mentions = parser.parse_file(str(xml_file))

            # Find the target toponym
            for mention in mentions:
                if mention.name == toponym:
                    docs_with_toponym += 1
                    total_mentions += mention.mention_count

                    # Collect proximity entities from each context
                    for context in mention.contexts:
                        nearby = context.nearby_locations
                        all_proximity_entities.extend(nearby)
                        proximity_by_doc[mention.document_id].append(nearby)

                        # Sample a few contexts for review
                        if len(sample_contexts) < 10:
                            sample_contexts.append({
                                'document': mention.document_id,
                                'nearby': nearby[:10],  # First 10 nearby
                                'context_preview': context.text[:200] + '...'
                            })

                    break  # Found the toponym, move to next file

        except Exception as e:
            print(f"Error parsing {xml_file.name}: {e}")

    print(f"✓ Analysis complete!")
    print()

    # Analyze proximity patterns
    proximity_freq = Counter(all_proximity_entities)

    return {
        'toponym': toponym,
        'docs_with_toponym': docs_with_toponym,
        'total_mentions': total_mentions,
        'avg_mentions_per_doc': total_mentions / docs_with_toponym if docs_with_toponym > 0 else 0,
        'proximity_freq': dict(proximity_freq.most_common(50)),
        'sample_contexts': sample_contexts,
        'proximity_by_doc': dict(proximity_by_doc)
    }


def classify_referent(toponym: str, nearby_entities: List[str]) -> Tuple[str, float]:
    """
    Classify which referent a mention likely refers to based on proximity entities

    Args:
        toponym: The toponym being classified
        nearby_entities: List of nearby toponyms

    Returns:
        Tuple of (referent_name, confidence_score)
    """
    if toponym not in KNOWN_REFERENTS:
        return ('Unknown', 0.0)

    referents = KNOWN_REFERENTS[toponym]
    nearby_set = set(e.lower() for e in nearby_entities)

    scores = {}
    for referent, indicators in referents.items():
        indicator_set = set(i.lower() for i in indicators)
        # Count how many indicators appear in nearby entities
        matches = len(nearby_set & indicator_set)
        scores[referent] = matches

    if not scores or max(scores.values()) == 0:
        return ('Ambiguous', 0.0)

    best_referent = max(scores, key=scores.get)
    confidence = scores[best_referent] / len(referents[best_referent])

    return (best_referent, confidence)


def generate_report(analysis: Dict):
    """Generate analysis report"""

    toponym = analysis['toponym']

    print("=" * 80)
    print(f"DISAMBIGUATION ANALYSIS: {toponym}")
    print("=" * 80)
    print()

    print(f"Documents with '{toponym}': {analysis['docs_with_toponym']}")
    print(f"Total mentions: {analysis['total_mentions']}")
    print(f"Average mentions per document: {analysis['avg_mentions_per_doc']:.1f}")
    print()

    # Top proximity entities
    print("TOP 30 PROXIMITY ENTITIES:")
    print("-" * 80)
    print(f"{'Entity':<40} {'Frequency':>10} {'% of Mentions':>15}")
    print("-" * 80)

    total_proximity = sum(analysis['proximity_freq'].values())
    for entity, freq in list(analysis['proximity_freq'].items())[:30]:
        pct = (freq / total_proximity) * 100
        print(f"{entity:<40} {freq:>10} {pct:>14.1f}%")

    print()

    # Try to classify referents based on known patterns
    if toponym in KNOWN_REFERENTS:
        print("REFERENT CLASSIFICATION ATTEMPT:")
        print("-" * 80)

        referent_counts = Counter()
        ambiguous_count = 0

        for doc_id, proximity_lists in analysis['proximity_by_doc'].items():
            # Classify based on ALL proximity entities in document
            all_nearby = []
            for prox_list in proximity_lists:
                all_nearby.extend(prox_list)

            referent, confidence = classify_referent(toponym, all_nearby)

            if referent == 'Ambiguous':
                ambiguous_count += 1
            else:
                referent_counts[referent] += 1

        print(f"\nClassification results (by document):")
        for referent, count in referent_counts.most_common():
            pct = (count / analysis['docs_with_toponym']) * 100
            print(f"  {referent:<40} {count:>5} docs ({pct:>5.1f}%)")

        if ambiguous_count > 0:
            pct = (ambiguous_count / analysis['docs_with_toponym']) * 100
            print(f"  {'Ambiguous/Unclear':<40} {ambiguous_count:>5} docs ({pct:>5.1f}%)")

        print()

    # Sample contexts
    print("SAMPLE CONTEXTS FOR MANUAL REVIEW:")
    print("-" * 80)

    for i, sample in enumerate(analysis['sample_contexts'][:5], 1):
        print(f"\n{i}. Document: {sample['document']}")
        print(f"   Nearby entities: {', '.join(sample['nearby'][:8])}")
        print(f"   Context: {sample['context_preview']}")

    print()

    # Recommendations
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print()

    # Check if one referent is overwhelmingly dominant
    if toponym in KNOWN_REFERENTS:
        referent_counts = Counter()
        for proximity_lists in analysis['proximity_by_doc'].values():
            all_nearby = []
            for prox_list in proximity_lists:
                all_nearby.extend(prox_list)
            referent, _ = classify_referent(toponym, all_nearby)
            if referent != 'Ambiguous':
                referent_counts[referent] += 1

        if referent_counts:
            top_referent, top_count = referent_counts.most_common(1)[0]
            top_pct = (top_count / analysis['docs_with_toponym']) * 100

            if top_pct >= 90:
                print(f"✓ CORPUS-LEVEL CACHE CANDIDATE:")
                print(f"  '{toponym}' refers to '{top_referent}' in {top_pct:.1f}% of documents")
                print(f"  Recommendation: Add to corpus_cache.json with high confidence")
            elif top_pct >= 70:
                print(f"⚠ MOSTLY CONSISTENT:")
                print(f"  '{toponym}' refers to '{top_referent}' in {top_pct:.1f}% of documents")
                print(f"  Recommendation: Add to corpus cache with note about exceptions")
                print(f"  Consider per-mention disambiguation for remaining {100-top_pct:.1f}%")
            else:
                print(f"✗ HIGHLY AMBIGUOUS:")
                print(f"  '{toponym}' has no dominant referent (top is {top_referent} at {top_pct:.1f}%)")
                print(f"  Recommendation: Per-mention disambiguation required")
                print(f"  Use proximity entities and context for each mention")

    print()


def main():
    """Run ambiguous toponym analysis"""

    if len(sys.argv) < 2:
        print("Usage: python analyze_ambiguous_toponym.py <toponym>")
        print("Example: python analyze_ambiguous_toponym.py London")
        print("Example: python analyze_ambiguous_toponym.py Victoria")
        sys.exit(1)

    toponym = sys.argv[1]
    corpus_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser("~/saskatchewan_toponym_xml")

    # Run analysis
    analysis = analyze_toponym(toponym, corpus_dir)

    # Generate report
    generate_report(analysis)

    # Save results
    output_dir = "results"
    os.makedirs(output_dir, exist_ok=True)
    output_file = f"{output_dir}/{toponym.lower()}_disambiguation_analysis.json"

    with open(output_file, 'w') as f:
        json.dump(analysis, f, indent=2)

    print(f"Full analysis saved to: {output_file}")


if __name__ == "__main__":
    main()

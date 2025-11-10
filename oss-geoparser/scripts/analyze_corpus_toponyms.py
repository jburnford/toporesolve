"""
Corpus-Level Toponym Analysis for Saskatchewan Historical Documents

Analyzes all 579 XML files to identify:
1. High-frequency toponyms (candidates for corpus-level caching)
2. Toponym distribution patterns
3. Potential ambiguous cases
4. Recommendations for caching strategy
"""

import sys
import os
from pathlib import Path
from collections import defaultdict, Counter
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from parsers.toponym_xml_parser import ToponymXMLParser


def analyze_corpus(xml_dir: str, sample_size: int = None):
    """
    Analyze toponym frequencies across corpus

    Args:
        xml_dir: Directory with XML files
        sample_size: If set, only analyze this many files (for speed)

    Returns:
        Dictionary with analysis results
    """
    xml_files = sorted(Path(xml_dir).glob("*.toponym.xml"))

    if sample_size:
        xml_files = xml_files[:sample_size]

    print(f"Analyzing {len(xml_files)} XML files...")
    print()

    # Track statistics
    toponym_global_freq = Counter()  # How many times each toponym appears total
    toponym_doc_freq = Counter()     # How many documents each toponym appears in
    doc_toponym_counts = []          # Number of unique toponyms per document

    parser = ToponymXMLParser(context_paragraphs=2)

    for i, xml_file in enumerate(xml_files, 1):
        if i % 50 == 0:
            print(f"Processed {i}/{len(xml_files)} files...")

        try:
            mentions = parser.parse_file(str(xml_file))

            # Track unique toponyms in this document
            doc_toponyms = set()

            for mention in mentions:
                toponym = mention.name.strip()
                toponym_global_freq[toponym] += 1
                doc_toponyms.add(toponym)

            # Track document frequency
            for toponym in doc_toponyms:
                toponym_doc_freq[toponym] += 1

            doc_toponym_counts.append(len(doc_toponyms))

        except Exception as e:
            print(f"Error parsing {xml_file.name}: {e}")

    print(f"✓ Analysis complete!")
    print()

    return {
        'total_files': len(xml_files),
        'toponym_global_freq': dict(toponym_global_freq),
        'toponym_doc_freq': dict(toponym_doc_freq),
        'doc_toponym_counts': doc_toponym_counts
    }


def generate_recommendations(analysis: Dict):
    """Generate caching recommendations based on analysis"""

    total_files = analysis['total_files']
    toponym_global_freq = Counter(analysis['toponym_global_freq'])
    toponym_doc_freq = Counter(analysis['toponym_doc_freq'])

    print("="*80)
    print("CORPUS-LEVEL TOPONYM ANALYSIS")
    print("="*80)
    print()

    # Overall statistics
    total_toponym_occurrences = sum(toponym_global_freq.values())
    unique_toponyms = len(toponym_global_freq)

    print(f"Files analyzed: {total_files}")
    print(f"Total toponym occurrences: {total_toponym_occurrences:,}")
    print(f"Unique toponyms: {unique_toponyms:,}")
    print(f"Average occurrences per toponym: {total_toponym_occurrences/unique_toponyms:.1f}")
    print()

    # Document frequency analysis
    avg_toponyms_per_doc = sum(analysis['doc_toponym_counts']) / len(analysis['doc_toponym_counts'])
    print(f"Average unique toponyms per document: {avg_toponyms_per_doc:.1f}")
    print()

    # High-frequency analysis
    print("="*80)
    print("HIGH-FREQUENCY TOPONYMS (Corpus-Level Cache Candidates)")
    print("="*80)
    print()

    # Thresholds for cache candidates
    doc_freq_threshold_high = int(total_files * 0.30)  # Appears in 30%+ of docs
    doc_freq_threshold_med = int(total_files * 0.10)   # Appears in 10%+ of docs

    print(f"Threshold for HIGH priority caching: {doc_freq_threshold_high} documents (30%)")
    print(f"Threshold for MEDIUM priority caching: {doc_freq_threshold_med} documents (10%)")
    print()

    # Categorize toponyms
    high_priority = []
    medium_priority = []

    for toponym, doc_freq in toponym_doc_freq.most_common():
        global_freq = toponym_global_freq[toponym]

        if doc_freq >= doc_freq_threshold_high:
            high_priority.append({
                'toponym': toponym,
                'doc_freq': doc_freq,
                'doc_percentage': (doc_freq / total_files) * 100,
                'global_freq': global_freq,
                'avg_per_doc': global_freq / doc_freq
            })
        elif doc_freq >= doc_freq_threshold_med:
            medium_priority.append({
                'toponym': toponym,
                'doc_freq': doc_freq,
                'doc_percentage': (doc_freq / total_files) * 100,
                'global_freq': global_freq,
                'avg_per_doc': global_freq / doc_freq
            })

    # Display HIGH priority candidates
    print(f"HIGH PRIORITY CACHE CANDIDATES ({len(high_priority)} toponyms):")
    print("-"*80)
    print(f"{'Toponym':<30} {'Docs':>6} {'%':>6} {'Total':>8} {'Avg/Doc':>8}")
    print("-"*80)

    for item in high_priority[:50]:  # Top 50
        print(f"{item['toponym']:<30} {item['doc_freq']:>6} {item['doc_percentage']:>5.1f}% "
              f"{item['global_freq']:>8} {item['avg_per_doc']:>8.1f}")

    if len(high_priority) > 50:
        print(f"... and {len(high_priority) - 50} more")

    print()

    # Display MEDIUM priority candidates
    print(f"MEDIUM PRIORITY CACHE CANDIDATES ({len(medium_priority)} toponyms):")
    print("-"*80)
    print(f"{'Toponym':<30} {'Docs':>6} {'%':>6} {'Total':>8} {'Avg/Doc':>8}")
    print("-"*80)

    for item in medium_priority[:30]:  # Top 30
        print(f"{item['toponym']:<30} {item['doc_freq']:>6} {item['doc_percentage']:>5.1f}% "
              f"{item['global_freq']:>8} {item['avg_per_doc']:>8.1f}")

    if len(medium_priority) > 30:
        print(f"... and {len(medium_priority) - 30} more")

    print()

    # Long-tail analysis
    singleton_docs = sum(1 for freq in toponym_doc_freq.values() if freq == 1)
    print(f"Long-tail toponyms (appear in only 1 document): {singleton_docs:,} ({singleton_docs/unique_toponyms*100:.1f}%)")
    print()

    # Recommendations
    print("="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    print()

    print("1. CORPUS-LEVEL CACHE:")
    print(f"   - Implement caching for {len(high_priority)} high-priority toponyms")
    print(f"   - These appear in 30%+ of documents")
    print(f"   - Will reduce {sum(item['global_freq'] for item in high_priority):,} API calls")
    print()

    print("2. WORKFLOW:")
    print("   a) Human review of high-priority list to confirm unambiguous")
    print("   b) One-time grounding of confirmed toponyms")
    print("   c) Save to config/corpus_cache.json")
    print("   d) Check cache before Neo4j/LLM in batch processing")
    print()

    print("3. ESTIMATED SAVINGS:")
    total_high_priority_calls = sum(item['global_freq'] for item in high_priority)
    estimated_time_saved = total_high_priority_calls * 14  # 14 sec per toponym
    print(f"   - API calls saved: {total_high_priority_calls:,}")
    print(f"   - Time saved: {estimated_time_saved/3600:.1f} hours")
    print()

    return {
        'high_priority': high_priority,
        'medium_priority': medium_priority,
        'thresholds': {
            'high': doc_freq_threshold_high,
            'medium': doc_freq_threshold_med
        }
    }


def main():
    """Run corpus analysis"""

    xml_dir = os.path.expanduser("~/saskatchewan_toponym_xml")

    # For initial analysis, use a sample to get quick results
    # Set to None to analyze ALL files (will take longer)
    SAMPLE_SIZE = 100  # Analyze first 100 files for speed

    print("="*80)
    print("SASKATCHEWAN CORPUS TOPONYM ANALYSIS")
    print("="*80)
    print()

    if SAMPLE_SIZE:
        print(f"NOTE: Analyzing SAMPLE of {SAMPLE_SIZE} files for speed")
        print("      Set SAMPLE_SIZE=None to analyze full corpus")
        print()

    # Run analysis
    analysis = analyze_corpus(xml_dir, sample_size=SAMPLE_SIZE)

    # Generate recommendations
    recommendations = generate_recommendations(analysis)

    # Save results
    output_dir = "results"
    os.makedirs(output_dir, exist_ok=True)

    output_file = f"{output_dir}/corpus_analysis_sample{SAMPLE_SIZE if SAMPLE_SIZE else 'FULL'}.json"

    with open(output_file, 'w') as f:
        json.dump({
            'analysis': analysis,
            'recommendations': recommendations
        }, f, indent=2)

    print(f"Full analysis saved to: {output_file}")
    print()
    print("="*80)
    print("NEXT STEPS:")
    print("="*80)
    print("1. Review high-priority toponym list")
    print("2. Manually verify these are unambiguous in Saskatchewan context")
    print("3. Ground each confirmed toponym once (get coordinates)")
    print("4. Create config/corpus_cache.json with groundings")
    print("5. Modify geoparser to check cache before Neo4j/LLM")
    print("="*80)


if __name__ == "__main__":
    main()

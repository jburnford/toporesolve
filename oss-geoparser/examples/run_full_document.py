"""
Full Document Processing with Precision-First OSS-Geoparser

Processes complete P000045.toponym.xml document
Saves detailed results for inspection
"""

import sys
import os
from dotenv import load_dotenv
import logging
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from geoparser import OSSGeoparser

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Process full document with precision-first geoparser"""

    # Load environment
    load_dotenv()

    # Initialize OpenRouter client
    from openai import OpenAI

    llm_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY")
    )

    # Initialize geoparser
    print("="*80)
    print("FULL DOCUMENT PROCESSING: Precision-First OSS-Geoparser")
    print("="*80)
    print()
    print("Configuration:")
    print("  - XML Format: Toponym (improved)")
    print("  - Precision-First: ENABLED")
    print("  - Toponym Filtering: ENABLED")
    print("  - Context Clustering: ENABLED")
    print("  - Low-Confidence Rejection: ENABLED")
    print()

    geoparser = OSSGeoparser(
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD"),
        llm_client=llm_client,
        enable_filtering=True,
        model="openai/gpt-oss-120b",
        max_contexts_per_cluster=3,
        similarity_threshold=0.3,
        xml_format="toponym"
    )

    # Process document
    xml_path = "/home/jic823/saskatchewan_toponyms_xml/P000045.toponym.xml"

    print(f"Processing: {xml_path}")
    print()
    print("This will process all 303 toponyms...")
    print("Estimated time: ~60-90 minutes (13 sec/toponym average)")
    print()

    start_time = datetime.now()

    result = geoparser.geoparse_document(
        xml_path=xml_path,
        source_location=None,  # No source location context
        disambiguate_all_clusters=False  # Only largest cluster per toponym
    )

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Print summary
    print()
    print("="*80)
    print("PROCESSING COMPLETE")
    print("="*80)
    print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    print(f"Document: {result.document_id}")
    print(f"Total mentions: {result.total_mentions}")
    print(f"Filtered (ungroundable): {result.filtered_mentions}")
    print(f"Processed: {result.processed_mentions}")
    print(f"Multi-referent detected: {result.multi_referent_detected}")
    print()

    # Analyze results
    total_processed = len(result.results)
    selected_count = sum(1 for r in result.results if r['selected_candidate'] is not None)
    rejected_count = total_processed - selected_count

    print("Results Breakdown:")
    print(f"  Candidates selected: {selected_count} ({selected_count/total_processed*100:.1f}%)")
    print(f"  Rejected (precision-first): {rejected_count} ({rejected_count/total_processed*100:.1f}%)")
    print()

    # Confidence breakdown
    high_conf = sum(1 for r in result.results if r['confidence'] == 'high')
    med_conf = sum(1 for r in result.results if r['confidence'] == 'medium')
    low_conf = sum(1 for r in result.results if r['confidence'] == 'low')

    print("Confidence Distribution:")
    print(f"  High: {high_conf} ({high_conf/total_processed*100:.1f}%)")
    print(f"  Medium: {med_conf} ({med_conf/total_processed*100:.1f}%)")
    print(f"  Low: {low_conf} ({low_conf/total_processed*100:.1f}%)")
    print()

    # Multi-referent stats
    multi_ref_count = sum(1 for r in result.results if r['has_multiple_referents'])
    print(f"Multi-referent toponyms: {multi_ref_count} ({multi_ref_count/total_processed*100:.1f}%)")
    print()

    # Filter statistics
    if result.filter_statistics:
        print("="*80)
        print("FILTER STATISTICS")
        print("="*80)
        for reason, data in result.filter_statistics.items():
            print(f"\n{reason}: {data['count']}")
            print(f"  Examples: {', '.join(data['examples'][:5])}")

    # Save detailed results to JSON
    output_file = "results/precision_first_full_P000045.json"
    os.makedirs("results", exist_ok=True)

    output_data = {
        "metadata": {
            "document_id": result.document_id,
            "processed_at": datetime.now().isoformat(),
            "duration_seconds": duration,
            "xml_path": xml_path,
            "configuration": {
                "xml_format": "toponym",
                "precision_first": True,
                "filtering_enabled": True,
                "model": "openai/gpt-oss-120b",
                "max_contexts_per_cluster": 3,
                "similarity_threshold": 0.3
            }
        },
        "summary": {
            "total_mentions": result.total_mentions,
            "filtered_mentions": result.filtered_mentions,
            "processed_mentions": result.processed_mentions,
            "multi_referent_detected": result.multi_referent_detected,
            "candidates_selected": selected_count,
            "precision_first_rejected": rejected_count,
            "confidence_high": high_conf,
            "confidence_medium": med_conf,
            "confidence_low": low_conf,
            "multi_referent_toponyms": multi_ref_count
        },
        "filter_statistics": result.filter_statistics,
        "results": result.results
    }

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print()
    print("="*80)
    print(f"Detailed results saved to: {output_file}")
    print("="*80)
    print()

    # Show sample results
    print("SAMPLE RESULTS (first 5 with candidates):")
    print("="*80)

    sample_count = 0
    for r in result.results:
        if r['selected_candidate'] and sample_count < 5:
            sample_count += 1
            print(f"\n{sample_count}. {r['toponym']}")
            print(f"   Confidence: {r['confidence']}")
            print(f"   Clusters: {r['clusters_detected']}, Multi-referent: {r['has_multiple_referents']}")

            cand = r['selected_candidate']
            print(f"   Selected: {cand['title']}, {cand.get('admin1', 'N/A')}, {cand['country']}")
            print(f"   Coords: ({cand['lat']}, {cand['lon']})")
            print(f"   Reasoning: {r['reasoning'][:150]}...")

    print()
    print("SAMPLE REJECTIONS (first 5 precision-first rejections):")
    print("="*80)

    rejection_count = 0
    for r in result.results:
        if not r['selected_candidate'] and rejection_count < 5:
            rejection_count += 1
            print(f"\n{rejection_count}. {r['toponym']}")
            print(f"   Confidence: {r['confidence']}")
            print(f"   Reasoning: {r['reasoning'][:150]}...")

    # Close connections
    geoparser.close()

    print()
    print("="*80)
    print("✓ Full Document Processing Complete")
    print("="*80)
    print(f"\nInspect results at: {output_file}")


if __name__ == "__main__":
    main()

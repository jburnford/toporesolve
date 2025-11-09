"""
Demo script for OSS-Geoparser

Shows complete pipeline on Saskatchewan XML data
"""

import sys
import os
from dotenv import load_dotenv
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from geoparser import OSSGeoparser

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Demo geoparser on sample XML"""

    # Load environment
    load_dotenv()

    # Initialize OpenRouter client (same as RAG v3)
    from openai import OpenAI

    llm_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY")
    )

    # Initialize geoparser
    print("Initializing OSS-Geoparser...")
    geoparser = OSSGeoparser(
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD"),
        llm_client=llm_client,
        enable_filtering=True,  # Filter ungroundable toponyms
        model="openai/gpt-oss-120b",
        max_contexts_per_cluster=3,  # Show up to 3 contexts per cluster
        similarity_threshold=0.3  # Context clustering threshold
    )

    # Get knowledge graph statistics
    print("\nKnowledge Graph Statistics:")
    stats = geoparser.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value:,}")

    # Process sample document
    xml_path = "/home/jic823/saskatchewan_locations_xml/P000992.locations.xml"

    if not os.path.exists(xml_path):
        print(f"\nError: Sample file not found: {xml_path}")
        print("Please update the path to a valid Saskatchewan XML file")
        return

    print(f"\n{'='*80}")
    print("Processing Sample Document")
    print(f"{'='*80}\n")

    # Optional: Add source location context
    # For Saskatchewan historical documents, you might know the newspaper location
    source_location = {
        'city': 'Regina',
        'state': 'Saskatchewan'
    }

    # Geoparse the document
    result = geoparser.geoparse_document(
        xml_path=xml_path,
        source_location=source_location,
        disambiguate_all_clusters=False  # Only disambiguate largest cluster
    )

    # Print summary
    print(f"\n{'='*80}")
    print("RESULTS SUMMARY")
    print(f"{'='*80}")
    print(f"Document: {result.document_id}")
    print(f"Total mentions: {result.total_mentions}")
    print(f"Filtered (ungroundable): {result.filtered_mentions}")
    print(f"Processed: {result.processed_mentions}")
    print(f"Multi-referent detected: {result.multi_referent_detected}")

    # Show filter statistics
    if result.filter_statistics:
        print(f"\n{'='*80}")
        print("FILTER STATISTICS")
        print(f"{'='*80}")
        for reason, data in result.filter_statistics.items():
            print(f"\n{reason}: {data['count']}")
            print(f"  Examples: {', '.join(data['examples'][:5])}")

    # Show disambiguation results
    print(f"\n{'='*80}")
    print("DISAMBIGUATION RESULTS")
    print(f"{'='*80}")

    for i, res in enumerate(result.results[:5], 1):  # Show first 5
        print(f"\n--- {i}. {res['toponym']} ---")
        print(f"Confidence: {res['confidence']}")
        print(f"Clusters detected: {res['clusters_detected']}")
        print(f"Multiple referents: {res['has_multiple_referents']}")

        if res['selected_candidate']:
            cand = res['selected_candidate']
            print(f"\nSelected: {cand['title']}")
            print(f"Location: {cand.get('admin1', 'N/A')}, {cand['country']}")
            print(f"Coordinates: ({cand['lat']}, {cand['lon']})")
            if cand.get('geonameId'):
                print(f"GeoNames ID: {cand['geonameId']}")
        else:
            print("\nNo candidate selected")

        print(f"\nReasoning: {res['reasoning'][:200]}...")

        if res['nearby_locations']:
            print(f"\nNearby locations: {', '.join(res['nearby_locations'][:5])}")

    if len(result.results) > 5:
        print(f"\n... and {len(result.results) - 5} more results")

    # Close connections
    geoparser.close()
    print("\n✓ Demo completed successfully")


if __name__ == "__main__":
    main()

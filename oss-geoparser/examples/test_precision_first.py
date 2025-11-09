"""
Test script for Precision-First OSS-Geoparser

Tests the complete pipeline on new XML format with precision-first disambiguation
Processes only the first 3 toponyms to verify everything works
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
    """Test precision-first geoparser on new XML"""

    # Load environment
    load_dotenv()

    # Initialize OpenRouter client
    from openai import OpenAI

    llm_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY")
    )

    # Initialize geoparser with new parser
    print("Initializing Precision-First OSS-Geoparser...")
    print("- Using ToponymXMLParser (improved format)")
    print("- Precision-first disambiguation enabled")
    print("- Low-confidence selections will be rejected")
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
        xml_format="toponym"  # Use new improved XML format
    )

    # Get knowledge graph statistics
    print("Knowledge Graph Statistics:")
    stats = geoparser.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value:,}")

    # Process sample document
    xml_path = "/home/jic823/saskatchewan_toponyms_xml/P000045.toponym.xml"

    if not os.path.exists(xml_path):
        print(f"\nError: Sample file not found: {xml_path}")
        return

    print(f"\n{'='*80}")
    print("Testing Precision-First Pipeline on P000045.toponym.xml")
    print(f"{'='*80}\n")

    # Parse XML to get mentions
    from parsers.toponym_xml_parser import ToponymXMLParser

    parser = ToponymXMLParser(context_paragraphs=2)
    mentions = parser.parse_file(xml_path)

    print(f"Total toponyms in document: {len(mentions)}")
    print(f"Testing first 3 toponyms only...\n")

    # Test first 3 toponyms
    test_mentions = mentions[:3]

    for i, mention in enumerate(test_mentions, 1):
        print(f"\n{'='*80}")
        print(f"TOPONYM {i}/{len(test_mentions)}: {mention.name}")
        print(f"{'='*80}")
        print(f"Mention count: {mention.mention_count}")
        print(f"Contexts available: {len(mention.contexts)}")

        # Show first context
        if mention.contexts:
            ctx = mention.contexts[0]
            print(f"\nFirst context preview:")
            print(f"  {ctx.text[:200]}...")
            print(f"  Nearby locations: {', '.join(ctx.nearby_locations[:5])}")
            if len(ctx.nearby_locations) > 5:
                print(f"    ... and {len(ctx.nearby_locations) - 5} more")

        # Disambiguate with precision-first approach
        print(f"\nDisambiguating with precision-first approach...")

        result = geoparser.disambiguator.disambiguate(
            mention=mention,
            source_location=None  # No source location for this test
        )

        print(f"\nResults:")
        print(f"  Clusters detected: {result.clusters_detected}")
        print(f"  Multiple referents: {result.has_multiple_referents}")
        print(f"  Confidence: {result.confidence}")

        if result.selected_candidate:
            cand = result.selected_candidate
            print(f"\n  ✓ SELECTED CANDIDATE:")
            print(f"    Name: {cand.get('title', 'N/A')}")
            print(f"    Location: {cand.get('admin1', 'N/A')}, {cand.get('country', 'N/A')}")
            print(f"    Coordinates: ({cand.get('lat')}, {cand.get('lon')})")
            if cand.get('feature_class'):
                print(f"    Feature Type: {cand['feature_class']}/{cand.get('feature_code', 'N/A')}")
            if cand.get('population'):
                print(f"    Population: {cand['population']:,}")
        else:
            print(f"\n  ✗ NO CANDIDATE SELECTED (precision-first rejection)")

        print(f"\n  Reasoning: {result.reasoning[:300]}...")

        print(f"\n  Nearby locations used: {', '.join(result.nearby_locations[:5])}")
        if len(result.nearby_locations) > 5:
            print(f"    ... and {len(result.nearby_locations) - 5} more")

    # Close connections
    geoparser.close()
    print(f"\n{'='*80}")
    print("✓ Precision-First Pipeline Test Complete")
    print(f"{'='*80}")
    print("\nNOTE: This was a limited test (3 toponyms only)")
    print("Full document processing would use geoparser.geoparse_document()")


if __name__ == "__main__":
    main()

"""
Build corpus-level cache for high-frequency unambiguous toponyms

Queries Neo4j once for each confirmed toponym and caches the result
for reuse across all documents in the corpus.
"""

import sys
import os
from dotenv import load_dotenv
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from knowledge_graph.neo4j_interface import Neo4jKnowledgeGraph


# Confirmed unambiguous toponyms from corpus analysis + domain expert review
CACHE_CANDIDATES = [
    # Major Canadian provinces/territories
    "Canada",
    "Saskatchewan",
    "Manitoba",
    "Ontario",
    "Quebec",

    # Major Canadian cities
    "Winnipeg",
    "Toronto",
    "Montreal",
    "Ottawa",
    "Edmonton",
    "Regina",

    # International
    "England",
    "United States",

    # Geographic features
    "Lake Winnipeg",
    "Lake Superior",
    "Red River",

    # Historical settlements
    "Fort Garry",
    "Prince Albert",
    "Battleford",
    "Batoche",
]


def build_cache(neo4j_interface):
    """
    Query Neo4j for each toponym and build cache

    Returns:
        Dictionary mapping lowercase toponym to grounding data
    """
    cache = {}

    print("="*80)
    print("BUILDING CORPUS-LEVEL CACHE")
    print("="*80)
    print(f"Grounding {len(CACHE_CANDIDATES)} toponyms...")
    print()

    for toponym in CACHE_CANDIDATES:
        print(f"Querying: {toponym}...")

        try:
            candidates = neo4j_interface.get_candidates(toponym, limit=5)

            if not candidates:
                print(f"  ⚠️  WARNING: No candidates found for '{toponym}'")
                print(f"      This toponym will NOT be cached.")
                continue

            # Take the first (highest ranked) candidate
            best = candidates[0]

            # Store in cache with lowercase key for case-insensitive matching
            cache[toponym.lower()] = {
                'geonames_id': best.get('geonameId'),
                'wikidata_id': best.get('wikidataId'),
                'title': best.get('title'),
                'country': best.get('country'),
                'admin1': best.get('admin1'),
                'lat': best.get('lat'),
                'lon': best.get('lon'),
                'feature_class': best.get('feature_class'),
                'feature_code': best.get('feature_code'),
                'population': best.get('population'),
                'confidence': 'corpus_level',
                'source': 'neo4j_corpus_cache',
                'original_toponym': toponym  # Preserve original casing
            }

            print(f"  ✓ Cached: {best['title']}, {best.get('admin1', 'N/A')}, {best['country']} "
                  f"({best['lat']}, {best['lon']})")

        except Exception as e:
            print(f"  ✗ Error querying '{toponym}': {e}")

    print()
    print(f"✓ Successfully cached {len(cache)}/{len(CACHE_CANDIDATES)} toponyms")

    return cache


def main():
    """Build and save corpus cache"""

    load_dotenv()

    # Connect to Neo4j
    neo4j = Neo4jKnowledgeGraph(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD")
    )

    # Build cache
    cache = build_cache(neo4j)

    # Save to config file
    cache_file = "config/corpus_cache.json"

    output = {
        "_metadata": {
            "description": "Corpus-level cache for high-frequency unambiguous toponyms",
            "created": "2024-11-09",
            "source": "Saskatchewan historical documents corpus analysis",
            "total_cached": len(cache),
            "usage": "Checked before Neo4j/LLM queries to save API calls"
        },
        "cache": cache
    }

    with open(cache_file, 'w') as f:
        json.dump(output, f, indent=2)

    print()
    print("="*80)
    print(f"Cache saved to: {cache_file}")
    print("="*80)
    print()
    print("NEXT STEPS:")
    print("1. Review the cache file to verify groundings are correct")
    print("2. Integrate cache into geoparser (check cache before Neo4j query)")
    print("3. Test on sample documents to measure savings")
    print("="*80)

    # Close connection
    neo4j.close()


if __name__ == "__main__":
    main()

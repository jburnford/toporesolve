"""
Add additional high-frequency toponyms to corpus cache
"""

import sys
import os
from dotenv import load_dotenv
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from knowledge_graph.neo4j_interface import Neo4jKnowledgeGraph


# Additional toponyms to cache (20%+ document frequency)
ADDITIONAL_CACHE = [
    "Qu'Appelle",
    "Fort Pitt",
    "Carlton",
    "Assiniboia",
    "North-West Territories",
    "Assiniboine",
    "St. Paul",
    "Nord-Ouest",
    "Europe",
    "Rome",
    "France",
    "New York",
    "Montana",
    "Minnesota",
    "Rocky Mountains"
]


def add_to_cache(neo4j_interface, cache_file):
    """
    Query Neo4j for additional toponyms and add to cache
    """
    # Load existing cache
    with open(cache_file) as f:
        cache_data = json.load(f)

    cache = cache_data['cache']
    initial_count = len(cache)

    print("=" * 80)
    print("ADDING TO CORPUS CACHE")
    print("=" * 80)
    print(f"Current cache size: {initial_count}")
    print(f"Adding {len(ADDITIONAL_CACHE)} toponyms...")
    print()

    for toponym in ADDITIONAL_CACHE:
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
    print(f"✓ Added {len(cache) - initial_count} toponyms to cache")
    print(f"Total cache size: {len(cache)}")

    # Update metadata
    cache_data['_metadata']['total_cached'] = len(cache)

    # Save updated cache
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f, indent=2)

    print()
    print("=" * 80)
    print(f"Updated cache saved to: {cache_file}")
    print("=" * 80)


def main():
    """Add toponyms to cache"""

    load_dotenv()

    # Connect to Neo4j
    neo4j = Neo4jKnowledgeGraph(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD")
    )

    # Add to cache
    cache_file = "config/corpus_cache.json"
    add_to_cache(neo4j, cache_file)

    # Close connection
    neo4j.close()


if __name__ == "__main__":
    main()

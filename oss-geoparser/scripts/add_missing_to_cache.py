"""
Add missing entities to cache with correct mappings
"""

import sys
import os
from dotenv import load_dotenv
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from knowledge_graph.neo4j_interface import Neo4jKnowledgeGraph

load_dotenv()

# Entities found in Neo4j that can be added
FOUND_IN_NEO4J = {
    'North Saskatchewan': 'North Saskatchewan River',
    'South Saskatchewan': 'South Saskatchewan River',
    'Lake of the Woods': 'Lake of the Woods',
    "Hudson's Bay": 'Hudson Bay',
    'York Fort': 'York Factory',
    'North-West Territory': 'Northwest Territories',
    'N.W.T.': 'Northwest Territories',
    'Saskatchewan District': 'Saskatchewan',
    'Territoires du Nord-Ouest': 'Northwest Territories',
}

# Entities not in Neo4j - manually add with Wikidata
MANUAL_ADDITIONS = {
    'Upper Fort Garry': {
        'geonames_id': None,
        'wikidata_id': 'Q689727',
        'title': 'Upper Fort Garry',
        'country': 'CA',
        'admin1': '03',
        'lat': 49.8950,
        'lon': -97.1366,
        'feature_class': 'S',
        'feature_code': 'HSTS',
        'population': 0,
    },
    "Rupert's Land": {
        'geonames_id': None,
        'wikidata_id': 'Q738395',
        'title': "Rupert's Land",
        'country': 'CA',
        'admin1': None,
        'lat': 55.0,
        'lon': -95.0,
        'feature_class': 'A',
        'feature_code': 'TERR',
        'population': 0,
    },
    'North America': {
        'geonames_id': 6255149,
        'wikidata_id': 'Q49',
        'title': 'North America',
        'country': None,
        'admin1': None,
        'lat': 46.07323,
        'lon': -100.54688,
        'feature_class': 'L',
        'feature_code': 'CONT',
        'population': 0,
    },
}

# Map to existing entries
MAP_TO_EXISTING = {
    'Dominion of Canada': 'Canada',
    'Province of Manitoba': 'Manitoba',
    'Province of Quebec': 'Quebec',
    'Province of Ontario': 'Ontario',
    'Canadian North-West': 'Northwest Territories',
}


def add_missing_to_cache(neo4j_interface, cache_file):
    """
    Add missing entities to cache
    """
    # Load existing cache
    with open(cache_file) as f:
        cache_data = json.load(f)

    cache = cache_data['cache']
    initial_count = len(cache)

    print("=" * 80)
    print("ADDING MISSING ENTITIES TO CACHE")
    print("=" * 80)
    print(f"Current cache size: {initial_count}")
    print()

    added = 0

    # Add entities found in Neo4j
    print("ADDING ENTITIES FOUND IN NEO4J:")
    print("-" * 80)
    for original, search_term in FOUND_IN_NEO4J.items():
        print(f"Adding: {original} (as {search_term})...")

        try:
            candidates = neo4j_interface.get_candidates(search_term, limit=1)

            if not candidates:
                print(f"  ✗ Not found: {search_term}")
                continue

            best = candidates[0]
            cache[original.lower()] = {
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
                'original_toponym': original
            }

            print(f"  ✓ Added: {best['title']} (GeoNames:{best.get('geonameId')}, Wikidata:{best.get('wikidataId')})")
            added += 1

        except Exception as e:
            print(f"  ✗ Error: {e}")

    print()

    # Add manual entries
    print("ADDING MANUAL ENTRIES WITH WIKIDATA:")
    print("-" * 80)
    for original, data in MANUAL_ADDITIONS.items():
        print(f"Adding: {original}...")

        cache[original.lower()] = {
            **data,
            'confidence': 'corpus_level',
            'source': 'manual_wikidata',
            'original_toponym': original
        }

        print(f"  ✓ Added: {data['title']} (Wikidata:{data['wikidata_id']})")
        added += 1

    print()

    # Map to existing entries
    print("MAPPING TO EXISTING CACHE ENTRIES:")
    print("-" * 80)
    for original, map_to in MAP_TO_EXISTING.items():
        print(f"Mapping: {original} → {map_to}...")

        # Find existing entry
        if map_to.lower() in cache:
            existing = cache[map_to.lower()].copy()
            existing['original_toponym'] = original
            cache[original.lower()] = existing
            print(f"  ✓ Mapped to: {existing['title']}")
            added += 1
        else:
            print(f"  ✗ Not found in cache: {map_to}")

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Added {added} entries")
    print(f"Total cache size: {initial_count} → {len(cache)}")

    # Update metadata
    cache_data['_metadata']['total_cached'] = len(cache)

    # Save updated cache
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f, indent=2)

    print(f"✓ Cache saved to: {cache_file}")
    print("=" * 80)


def main():
    """Add missing entities to cache"""

    # Connect to Neo4j
    neo4j = Neo4jKnowledgeGraph(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD")
    )

    # Add missing entities
    cache_file = "config/corpus_cache.json"
    add_missing_to_cache(neo4j, cache_file)

    # Close connection
    neo4j.close()


if __name__ == "__main__":
    main()

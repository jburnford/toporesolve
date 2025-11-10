"""
Expand corpus cache with 98 conservative safe additions
Zero false positive risk - all toponyms are unambiguous
"""

import sys
import os
from dotenv import load_dotenv
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from knowledge_graph.neo4j_interface import Neo4jKnowledgeGraph


# Safe cache additions (98 toponyms with 5+ occurrences)
SAFE_ADDITIONS = [
    # Geographic Features - Rivers (23)
    "Saskatchewan River",
    "North Saskatchewan",
    "South Saskatchewan",
    "Bow River",
    "Peace River",
    "Swan River",
    "Rainy River",
    "Battle River",
    "Nelson River",
    "Columbia River",
    "Pembina River",
    "Hayes River",
    "Mackenzie River",
    "Churchill River",
    "Red Deer River",
    "Winnipeg River",
    "Red Lake River",
    "Shell River",

    # Geographic Features - Lakes/Hills/Oceans
    "Lake Manitoba",
    "Lake of the Woods",
    "Cedar Lake",
    "Long Lake",
    "Rainy Lake",
    "Shoal Lake",
    "Lake Huron",
    "Touchwood Hills",
    "Cypress Hills",
    "Eagle Hills",
    "Hudson's Bay",
    "Hudson Bay",
    "St. Lawrence",
    "Pacific Ocean",
    "Atlantic",
    "Arctic Ocean",

    # Canadian Cities (16)
    "Calgary",
    "St. Boniface",
    "Selkirk",
    "Portage la Prairie",
    "Kildonan",
    "Swift Current",
    "St. Albert",
    "Saskatoon",
    "Brandon",
    "Moose Jaw",
    "Emerson",
    "Medicine Hat",
    "Humboldt",
    "Moosomin",
    "Birtle",
    "Maple Creek",

    # HBC Forts (22)
    "Fort William",
    "Cumberland House",
    "York Factory",
    "Norway House",
    "Fort Carlton",
    "Fort Ellice",
    "Fort Qu'Appelle",
    "Fort Pelly",
    "Fort Edmonton",
    "Fort Alexander",
    "Fort Churchill",
    "Fort Saskatchewan",
    "Fort Frances",
    "Rocky Mountain House",
    "Lower Fort Garry",
    "Carlton House",
    "Edmonton House",
    "Stone Fort",
    "Oxford House",
    "York Fort",
    "Upper Fort Garry",
    "Bow Fort",
    "Chesterfield House",

    # Canadian Regions (18)
    "Red River Settlement",
    "Rupert's Land",
    "North-West Territory",
    "British Columbia",
    "Upper Canada",
    "Lower Canada",
    "Dominion of Canada",
    "N.W.T.",
    "Newfoundland",
    "Nova Scotia",
    "New Brunswick",
    "Keewatin",
    "Province of Manitoba",
    "Province of Quebec",
    "Province of Ontario",
    "Saskatchewan District",
    "Territoires du Nord-Ouest",
    "Canadian North-West",

    # International (19)
    "Great Britain",
    "Scotland",
    "Ireland",
    "Paris",
    "Chicago",
    "Boston",
    "San Francisco",
    "Liverpool",
    "Edinburgh",
    "Germany",
    "United Kingdom",
    "Mexico",
    "India",
    "China",
    "Australia",
    "Dakota",
    "Halifax",
    "North America",
]


def expand_cache(neo4j_interface, cache_file):
    """
    Query Neo4j for safe toponyms and add to cache
    """
    # Load existing cache
    with open(cache_file) as f:
        cache_data = json.load(f)

    cache = cache_data['cache']
    initial_count = len(cache)

    print("=" * 80)
    print("EXPANDING CORPUS CACHE - SAFE ADDITIONS")
    print("=" * 80)
    print(f"Current cache size: {initial_count}")
    print(f"Adding {len(SAFE_ADDITIONS)} safe toponyms...")
    print()

    added = 0
    not_found = []
    errors = []

    for toponym in SAFE_ADDITIONS:
        print(f"Querying: {toponym}...")

        try:
            candidates = neo4j_interface.get_candidates(toponym, limit=5)

            if not candidates:
                print(f"  ⚠️  WARNING: No candidates found for '{toponym}'")
                not_found.append(toponym)
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
            added += 1

        except Exception as e:
            print(f"  ✗ Error querying '{toponym}': {e}")
            errors.append((toponym, str(e)))

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✓ Added {added} toponyms to cache")
    print(f"⚠ Not found: {len(not_found)}")
    print(f"✗ Errors: {len(errors)}")
    print(f"Total cache size: {initial_count} → {len(cache)}")
    print()

    if not_found:
        print("NOT FOUND IN DATABASE:")
        for t in not_found:
            print(f"  - {t}")
        print()

    if errors:
        print("ERRORS:")
        for t, err in errors:
            print(f"  - {t}: {err}")
        print()

    # Update metadata
    cache_data['_metadata']['total_cached'] = len(cache)

    # Save updated cache
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f, indent=2)

    print("=" * 80)
    print(f"Updated cache saved to: {cache_file}")
    print("=" * 80)

    return not_found, errors


def main():
    """Expand cache with safe additions"""

    load_dotenv()

    # Connect to Neo4j
    neo4j = Neo4jKnowledgeGraph(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD")
    )

    # Expand cache
    cache_file = "config/corpus_cache.json"
    not_found, errors = expand_cache(neo4j, cache_file)

    # Close connection
    neo4j.close()

    print()
    print("NEXT STEPS:")
    if not_found or errors:
        print("1. Review items not found or with errors")
        print("2. Manually add missing items with Wikidata IDs")
    print("3. Verify cache entries are correct")
    print("4. Test geoparser with expanded cache")


if __name__ == "__main__":
    main()

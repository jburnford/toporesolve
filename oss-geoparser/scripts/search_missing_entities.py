"""
Search Neo4j for missing entities with alternative names
"""

import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from knowledge_graph.neo4j_interface import Neo4jKnowledgeGraph

load_dotenv()

# Items not found - try alternative search terms
not_found = {
    'North Saskatchewan': ['North Saskatchewan River', 'Saskatchewan River North'],
    'South Saskatchewan': ['South Saskatchewan River', 'Saskatchewan River South'],
    'Columbia River': ['Columbia'],
    'Red Lake River': ['Red Lake'],
    'Lake of the Woods': ['Woods Lake', 'Lake Woods'],
    "Hudson's Bay": ['Hudson Bay', 'Hudsons Bay'],
    'Pacific Ocean': ['Pacific'],
    'Arctic Ocean': ['Arctic'],
    'Portage la Prairie': ['Portage'],
    'Fort Carlton': ['Carlton', 'Fort Carlton Provincial Park'],
    'Carlton House': ['Carlton'],
    'Edmonton House': ['Edmonton'],
    'York Fort': ['York Factory'],
    'Upper Fort Garry': ['Fort Garry Upper'],
    'Bow Fort': ['Bow'],
    'Chesterfield House': ['Chesterfield'],
    'Red River Settlement': ['Red River Colony', 'Red River'],
    "Rupert's Land": ['Ruperts Land'],
    'North-West Territory': ['Northwest Territory', 'Northwest Territories'],
    'Dominion of Canada': ['Canada Dominion'],
    'N.W.T.': ['NWT', 'Northwest Territories'],
    'Province of Manitoba': ['Manitoba Province'],
    'Province of Quebec': ['Quebec Province'],
    'Province of Ontario': ['Ontario Province'],
    'Saskatchewan District': ['Saskatchewan'],
    'Territoires du Nord-Ouest': ['Northwest Territories'],
    'Canadian North-West': ['North-West Canada', 'Canadian Northwest'],
    'North America': ['America North'],
}

neo4j = Neo4jKnowledgeGraph(
    uri=os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
    user=os.getenv('NEO4J_USER', 'neo4j'),
    password=os.getenv('NEO4J_PASSWORD')
)

print("=" * 80)
print("SEARCHING NEO4J FOR MISSING ENTITIES")
print("=" * 80)
print()

found = {}
still_missing = []

for original, alternatives in not_found.items():
    print(f"Searching: {original}")

    # Try all alternatives
    all_terms = [original] + alternatives
    candidates_found = []

    for term in all_terms:
        try:
            results = neo4j.get_candidates(term, limit=3)
            if results:
                candidates_found.extend(results)
                print(f"  ✓ Found with '{term}': {len(results)} candidates")
                for i, r in enumerate(results[:2], 1):
                    wikidata = r.get('wikidataId', 'None')
                    country = r.get('country', 'N/A')
                    admin1 = r.get('admin1', 'N/A')
                    geonames = r.get('geonameId', 'None')
                    print(f"    #{i}: {r['title']} ({country}, {admin1}) - GeoNames:{geonames}, Wikidata:{wikidata}")
                break
        except Exception as e:
            continue

    if candidates_found:
        found[original] = candidates_found[0]  # Best match
    else:
        print(f"  ✗ Not found in database")
        still_missing.append(original)
    print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Found in database: {len(found)}")
print(f"Still missing: {len(still_missing)}")
print()

if still_missing:
    print("STILL MISSING FROM DATABASE (NEED WIKIDATA IDS):")
    for item in still_missing:
        print(f"  - {item}")

neo4j.close()

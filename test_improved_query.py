"""Test improved case-insensitive query"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'models', 'historical-geoparser'))

from canadian_neo4j_rag import CanadianGeoparserRAG

rag = CanadianGeoparserRAG(
    neo4j_uri='bolt://localhost:7687',
    neo4j_user='neo4j',
    neo4j_password='york2005'
)

# Test problematic toponyms
test_cases = [
    'WASHINGTON',           # All caps
    'New Hampshire\'s',     # Possessive
    'Fairfax County\'s',    # Possessive + County
    'California',           # Normal case
    'Delaware',             # Should work now
    'Connecticut',          # Should work now
]

print("Testing improved query with case-insensitive matching:")
print("=" * 80)

for toponym in test_cases:
    candidates = rag.query_candidates(toponym, max_results=3)
    print(f"\n{toponym:25} -> {len(candidates)} candidates found")
    for i, c in enumerate(candidates[:3], 1):
        pop = c['population'] if c['population'] else 0
        print(f"  {i}. {c['name']:30} {c['countryCode']:2} {c['featureCode']:10} pop={pop:>10,}")

rag.close()

"""Test if problematic toponyms exist in Neo4j database"""
from neo4j import GraphDatabase
import os

driver = GraphDatabase.driver(
    'bolt://localhost:7687',
    auth=('neo4j', 'york2005')
)

test_cases = [
    'WASHINGTON',  # Should be state
    'California',  # Should be state
    'Delaware',    # Should be state
    'Connecticut', # Should be state
    'Rhode Island', # Should be state
    'Troy',        # Multiple Troys in US
    'Jackson',     # Multiple Jacksons
    'Newark',      # Multiple Newarks
    'Cambridge',   # Multiple Cambridges
]

print("Testing if toponyms exist in Neo4j database:\n")
print("=" * 80)

with driver.session() as session:
    for toponym in test_cases:
        # Try exact match
        query = """
        MATCH (p:Place)
        WHERE p.name = $toponym
           OR $toponym IN p.alternateNames
           OR p.asciiName = $toponym
        RETURN count(p) as count
        """
        result = session.run(query, toponym=toponym)
        count = result.single()['count']

        print(f"\n{toponym:20} -> {count:4} matches in database")

        # Show sample results
        if count > 0:
            query2 = """
            MATCH (p:Place)
            WHERE p.name = $toponym
               OR $toponym IN p.alternateNames
               OR p.asciiName = $toponym
            WITH p, COALESCE(p.population, 0) AS pop
            RETURN p.name, p.countryCode, p.featureCode, p.population
            ORDER BY pop DESC
            LIMIT 5
            """
            result2 = session.run(query2, toponym=toponym)
            for record in result2:
                pop = record['p.population'] if record['p.population'] else 0
                print(f"     -> {record['p.name']:30} {record['p.countryCode']:2} {record['p.featureCode']:10} pop={pop:>10,}")

driver.close()

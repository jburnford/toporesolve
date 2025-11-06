"""
Neo4j Query Utilities for Historical Toponym Disambiguation
Provides temporal querying capabilities for place names
"""

from neo4j import GraphDatabase
from typing import List, Dict, Optional
from datetime import datetime

class HistoricalPlaceQuerier:
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password):
        """Initialize connection to Neo4j"""
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    def close(self):
        """Close Neo4j connection"""
        self.driver.close()

    def find_places_by_name_and_date(self, toponym: str, year: str,
                                     max_results: int = 10) -> List[Dict]:
        """
        Find places that had a specific name in a given year

        Args:
            toponym: The place name to search for
            year: The year as string (e.g., "1916")
            max_results: Maximum number of results to return

        Returns:
            List of place dictionaries with metadata
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Place)-[r:HAS_NAME]->(h:HistoricalName)
                WHERE h.name = $toponym
                  AND (
                    // Name was valid in the given year
                    (h.valid_from <= $year AND (h.valid_to >= $year OR h.valid_to = 'present'))
                    OR
                    // No temporal info available (include as candidate)
                    (h.valid_from = 'unknown' OR h.valid_from IS NULL)
                  )
                RETURN DISTINCT
                    p.place_id as place_id,
                    p.name as current_name,
                    h.name as historical_name,
                    p.latitude as latitude,
                    p.longitude as longitude,
                    p.country_code as country_code,
                    p.feature_type as feature_type,
                    p.source as source,
                    h.valid_from as name_valid_from,
                    h.valid_to as name_valid_to,
                    h.name_type as name_type
                ORDER BY
                    CASE WHEN h.name_type = 'official' THEN 1 ELSE 2 END,
                    CASE WHEN p.source = 'wikidata' THEN 1 ELSE 2 END
                LIMIT $max_results
            """, toponym=toponym, year=year, max_results=max_results)

            places = []
            for record in result:
                place = {
                    'place_id': record['place_id'],
                    'current_name': record['current_name'],
                    'historical_name': record['historical_name'],
                    'latitude': record['latitude'],
                    'longitude': record['longitude'],
                    'country_code': record['country_code'],
                    'feature_type': record['feature_type'],
                    'source': record['source'],
                    'name_valid_from': record['name_valid_from'],
                    'name_valid_to': record['name_valid_to'],
                    'name_type': record['name_type']
                }
                places.append(place)

            return places

    def find_places_by_fuzzy_name(self, toponym: str, year: str,
                                   max_results: int = 10) -> List[Dict]:
        """
        Find places using fuzzy matching (for handling OCR errors)
        Uses Levenshtein distance or soundex in Neo4j
        """
        with self.driver.session() as session:
            # Use CONTAINS for simple fuzzy matching
            # For production, consider using apoc.text.levenshteinDistance
            result = session.run("""
                MATCH (p:Place)-[r:HAS_NAME]->(h:HistoricalName)
                WHERE toLower(h.name) CONTAINS toLower($toponym)
                  AND (
                    (h.valid_from <= $year AND (h.valid_to >= $year OR h.valid_to = 'present'))
                    OR (h.valid_from = 'unknown' OR h.valid_from IS NULL)
                  )
                RETURN DISTINCT
                    p.place_id as place_id,
                    p.name as current_name,
                    h.name as historical_name,
                    p.latitude as latitude,
                    p.longitude as longitude,
                    p.country_code as country_code,
                    p.feature_type as feature_type
                LIMIT $max_results
            """, toponym=toponym, year=year, max_results=max_results)

            return [dict(record) for record in result]

    def find_places_in_bounding_box(self, min_lat: float, max_lat: float,
                                     min_lon: float, max_lon: float,
                                     toponym: Optional[str] = None) -> List[Dict]:
        """
        Find places within a geographic bounding box
        Useful for geographic context filtering
        """
        with self.driver.session() as session:
            if toponym:
                result = session.run("""
                    MATCH (p:Place)-[:HAS_NAME]->(h:HistoricalName)
                    WHERE p.latitude >= $min_lat AND p.latitude <= $max_lat
                      AND p.longitude >= $min_lon AND p.longitude <= $max_lon
                      AND h.name = $toponym
                    RETURN DISTINCT p.place_id as place_id, p.name as name,
                           p.latitude as latitude, p.longitude as longitude,
                           p.country_code as country_code
                """, min_lat=min_lat, max_lat=max_lat,
                     min_lon=min_lon, max_lon=max_lon, toponym=toponym)
            else:
                result = session.run("""
                    MATCH (p:Place)
                    WHERE p.latitude >= $min_lat AND p.latitude <= $max_lat
                      AND p.longitude >= $min_lon AND p.longitude <= $max_lon
                    RETURN p.place_id as place_id, p.name as name,
                           p.latitude as latitude, p.longitude as longitude,
                           p.country_code as country_code
                    LIMIT 100
                """, min_lat=min_lat, max_lat=max_lat, min_lon=min_lon, max_lon=max_lon)

            return [dict(record) for record in result]

    def get_place_context(self, place_id: str, year: str) -> Dict:
        """
        Get rich context about a place including:
        - All historical names
        - Administrative hierarchy
        - Related places
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Place {place_id: $place_id})
                OPTIONAL MATCH (p)-[r:HAS_NAME]->(h:HistoricalName)
                WHERE h.valid_from <= $year
                  AND (h.valid_to >= $year OR h.valid_to = 'present')
                OPTIONAL MATCH (p)-[:PART_OF]->(admin:AdministrativeEntity)
                RETURN p,
                       collect(DISTINCT h) as historical_names,
                       collect(DISTINCT admin) as administrative_entities
            """, place_id=place_id, year=year)

            record = result.single()
            if not record:
                return None

            place = dict(record['p'])
            place['historical_names'] = [dict(h) for h in record['historical_names']]
            place['administrative_entities'] = [dict(a) for a in record['administrative_entities']]

            return place

    def find_name_changes(self, place_id: str) -> List[Dict]:
        """
        Get the history of name changes for a place
        Returns timeline of all names
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Place {place_id: $place_id})-[:HAS_NAME]->(h:HistoricalName)
                RETURN h.name as name,
                       h.valid_from as valid_from,
                       h.valid_to as valid_to,
                       h.name_type as name_type
                ORDER BY h.valid_from
            """, place_id=place_id)

            return [dict(record) for record in result]

    def get_statistics(self) -> Dict:
        """Get database statistics"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Place)
                OPTIONAL MATCH (p)-[:HAS_NAME]->(h:HistoricalName)
                RETURN
                    count(DISTINCT p) as total_places,
                    count(DISTINCT h) as total_historical_names,
                    count(DISTINCT p.country_code) as countries_covered,
                    count(DISTINCT CASE WHEN p.source = 'wikidata' THEN p END) as wikidata_places,
                    count(DISTINCT CASE WHEN p.source = 'geonames' THEN p END) as geonames_places
            """)

            return dict(result.single())


def test_queries():
    """Test the query utilities"""
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "your-password-here"

    querier = HistoricalPlaceQuerier(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

    try:
        # Test 1: Find Constantinople in 1900
        print("\n=== Test 1: Constantinople in 1900 ===")
        places = querier.find_places_by_name_and_date("Constantinople", "1900")
        for place in places:
            print(f"  {place['historical_name']} -> {place['current_name']}")
            print(f"    Coords: ({place['latitude']}, {place['longitude']})")
            print(f"    Valid: {place['name_valid_from']} to {place['name_valid_to']}\n")

        # Test 2: Find Paris in 1850
        print("\n=== Test 2: Paris in 1850 ===")
        places = querier.find_places_by_name_and_date("Paris", "1850", max_results=5)
        for place in places:
            print(f"  {place['historical_name']} ({place['country_code']})")
            print(f"    Coords: ({place['latitude']}, {place['longitude']})\n")

        # Test 3: Database statistics
        print("\n=== Test 3: Database Statistics ===")
        stats = querier.get_statistics()
        for key, value in stats.items():
            print(f"  {key}: {value}")

    finally:
        querier.close()


if __name__ == "__main__":
    test_queries()

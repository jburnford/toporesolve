"""
Wikidata Ingestion Pipeline for Historical Place Names
This script queries Wikidata SPARQL endpoint to retrieve historical place name information
and loads it into Neo4j.
"""

import requests
from neo4j import GraphDatabase
import json
from typing import List, Dict
import time

class WikidataIngestor:
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password):
        """Initialize connection to Neo4j"""
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.wikidata_endpoint = "https://query.wikidata.org/sparql"

    def close(self):
        """Close Neo4j connection"""
        self.driver.close()

    def query_wikidata(self, sparql_query: str) -> List[Dict]:
        """Execute SPARQL query against Wikidata"""
        headers = {
            'User-Agent': 'HistoricalGeoparser/1.0 (Research Project)',
            'Accept': 'application/json'
        }
        params = {
            'query': sparql_query,
            'format': 'json'
        }

        try:
            response = requests.get(
                self.wikidata_endpoint,
                params=params,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data['results']['bindings']
        except Exception as e:
            print(f"Error querying Wikidata: {e}")
            return []

    def get_places_with_historical_names(self, limit=1000):
        """
        Query Wikidata for places with historical names
        Focuses on places with inception dates and name changes
        """
        sparql_query = f"""
        SELECT DISTINCT ?place ?placeLabel ?coord ?inception ?dissolved
               ?historicalName ?nameStartDate ?nameEndDate
               ?countryCode ?featureType
        WHERE {{
          # Get places (cities, towns, etc)
          ?place wdt:P31/wdt:P279* wd:Q486972.  # Instance of human settlement

          # Get coordinates
          ?place wdt:P625 ?coord.

          # Get official name
          ?place rdfs:label ?placeLabel.
          FILTER(LANG(?placeLabel) = "en")

          # Get country
          OPTIONAL {{ ?place wdt:P17 ?country. ?country wdt:P298 ?countryCode. }}

          # Get inception date (when place was founded/established)
          OPTIONAL {{ ?place wdt:P571 ?inception. }}

          # Get dissolution date (if applicable)
          OPTIONAL {{ ?place wdt:P576 ?dissolved. }}

          # Get historical names with validity periods
          OPTIONAL {{
            ?place p:P1448 ?nameStatement.  # Official name statement
            ?nameStatement ps:P1448 ?historicalName.
            FILTER(LANG(?historicalName) = "en")

            # Start date of name validity
            OPTIONAL {{ ?nameStatement pq:P580 ?nameStartDate. }}

            # End date of name validity
            OPTIONAL {{ ?nameStatement pq:P582 ?nameEndDate. }}
          }}

          # Get feature type
          OPTIONAL {{ ?place wdt:P31 ?type. }}

          # Filter for places with historical relevance (1600-1950)
          FILTER(!BOUND(?inception) || YEAR(?inception) <= 1950)
          FILTER(!BOUND(?dissolved) || YEAR(?dissolved) >= 1600)
        }}
        LIMIT {limit}
        """

        print(f"Querying Wikidata for places with historical names...")
        results = self.query_wikidata(sparql_query)
        print(f"Retrieved {len(results)} results from Wikidata")
        return results

    def parse_wikidata_coordinates(self, coord_string: str) -> tuple:
        """Parse Wikidata coordinate string to (lat, lon)"""
        # Format: "Point(longitude latitude)"
        try:
            coord_string = coord_string.replace('Point(', '').replace(')', '')
            lon, lat = map(float, coord_string.split())
            return (lat, lon)
        except:
            return (None, None)

    def extract_qid(self, uri: str) -> str:
        """Extract Wikidata QID from URI"""
        return uri.split('/')[-1]

    def extract_year(self, date_string: str) -> str:
        """Extract year from ISO date string"""
        try:
            return date_string.split('T')[0].split('-')[0]
        except:
            return None

    def load_to_neo4j(self, wikidata_results: List[Dict]):
        """Load Wikidata results into Neo4j"""
        with self.driver.session() as session:
            for i, result in enumerate(wikidata_results):
                try:
                    # Extract data
                    place_uri = result.get('place', {}).get('value', '')
                    place_id = self.extract_qid(place_uri)
                    place_name = result.get('placeLabel', {}).get('value', '')
                    coord_string = result.get('coord', {}).get('value', '')
                    country_code = result.get('countryCode', {}).get('value', '')
                    inception = result.get('inception', {}).get('value', '')
                    dissolved = result.get('dissolved', {}).get('value', '')
                    historical_name = result.get('historicalName', {}).get('value', '')
                    name_start = result.get('nameStartDate', {}).get('value', '')
                    name_end = result.get('nameEndDate', {}).get('value', '')

                    # Parse coordinates
                    lat, lon = self.parse_wikidata_coordinates(coord_string)

                    if not place_id or lat is None or lon is None:
                        continue

                    # Extract years
                    inception_year = self.extract_year(inception) if inception else None
                    dissolved_year = self.extract_year(dissolved) if dissolved else None
                    name_start_year = self.extract_year(name_start) if name_start else None
                    name_end_year = self.extract_year(name_end) if name_end else None

                    # Create Place node
                    session.execute_write(
                        self._create_place_node,
                        place_id, place_name, lat, lon, country_code
                    )

                    # Create HistoricalName nodes
                    if historical_name:
                        name_id = f"{place_id}_name_{hash(historical_name) % 10000}"
                        session.execute_write(
                            self._create_historical_name_node,
                            name_id, historical_name, place_id,
                            name_start_year or inception_year,
                            name_end_year or dissolved_year or "present"
                        )

                    if (i + 1) % 100 == 0:
                        print(f"Processed {i + 1} / {len(wikidata_results)} places")

                except Exception as e:
                    print(f"Error processing result {i}: {e}")
                    continue

        print(f"Successfully loaded {len(wikidata_results)} places to Neo4j")

    @staticmethod
    def _create_place_node(tx, place_id, name, lat, lon, country_code):
        """Create or merge Place node"""
        query = """
        MERGE (p:Place {place_id: $place_id})
        ON CREATE SET
            p.name = $name,
            p.latitude = $lat,
            p.longitude = $lon,
            p.source = 'wikidata',
            p.country_code = $country_code,
            p.feature_type = 'GPE'
        ON MATCH SET
            p.name = $name,
            p.latitude = $lat,
            p.longitude = $lon
        """
        tx.run(query, place_id=place_id, name=name, lat=lat, lon=lon, country_code=country_code)

    @staticmethod
    def _create_historical_name_node(tx, name_id, name, place_id, valid_from, valid_to):
        """Create HistoricalName node and link to Place"""
        query = """
        MERGE (h:HistoricalName {name_id: $name_id})
        ON CREATE SET
            h.name = $name,
            h.language = 'en',
            h.valid_from = $valid_from,
            h.valid_to = $valid_to,
            h.name_type = 'official',
            h.script = 'latin'
        WITH h
        MATCH (p:Place {place_id: $place_id})
        MERGE (p)-[r:HAS_NAME]->(h)
        ON CREATE SET
            r.valid_from = $valid_from,
            r.valid_to = $valid_to
        """
        tx.run(query,
               name_id=name_id,
               name=name,
               place_id=place_id,
               valid_from=valid_from,
               valid_to=valid_to)


def main():
    """Main execution function"""
    # Neo4j connection details
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "your-password-here"  # Change this!

    # Initialize ingestor
    ingestor = WikidataIngestor(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

    try:
        # Query Wikidata
        results = ingestor.get_places_with_historical_names(limit=5000)

        # Load to Neo4j
        if results:
            ingestor.load_to_neo4j(results)
        else:
            print("No results retrieved from Wikidata")

    finally:
        ingestor.close()


if __name__ == "__main__":
    main()

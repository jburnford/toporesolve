"""
GeoNames Ingestion Pipeline
Downloads and loads GeoNames data into Neo4j
"""

import requests
import zipfile
import os
from neo4j import GraphDatabase
from typing import List, Dict
import csv

class GeoNamesIngestor:
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password):
        """Initialize connection to Neo4j"""
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.geonames_base_url = "http://download.geonames.org/export/dump/"
        self.data_dir = "data/geonames"

    def close(self):
        """Close Neo4j connection"""
        self.driver.close()

    def download_geonames_data(self, country_codes: List[str] = ['US', 'FR', 'GB', 'DE']):
        """
        Download GeoNames data for specified countries
        country_codes: List of ISO 2-letter country codes
        """
        os.makedirs(self.data_dir, exist_ok=True)

        for country_code in country_codes:
            filename = f"{country_code}.zip"
            url = f"{self.geonames_base_url}{filename}"
            output_path = os.path.join(self.data_dir, filename)

            if os.path.exists(output_path.replace('.zip', '.txt')):
                print(f"Data for {country_code} already exists, skipping download")
                continue

            print(f"Downloading GeoNames data for {country_code}...")
            try:
                response = requests.get(url, stream=True, timeout=60)
                response.raise_for_status()

                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                # Extract zip file
                with zipfile.ZipFile(output_path, 'r') as zip_ref:
                    zip_ref.extractall(self.data_dir)

                print(f"Downloaded and extracted {country_code}")
            except Exception as e:
                print(f"Error downloading {country_code}: {e}")

    def parse_geonames_file(self, filepath: str, limit: int = None) -> List[Dict]:
        """
        Parse GeoNames .txt file
        Format: http://download.geonames.org/export/dump/readme.txt
        """
        places = []

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')

            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break

                try:
                    place = {
                        'geonameid': row[0],
                        'name': row[1],
                        'asciiname': row[2],
                        'alternatenames': row[3].split(',') if row[3] else [],
                        'latitude': float(row[4]),
                        'longitude': float(row[5]),
                        'feature_class': row[6],
                        'feature_code': row[7],
                        'country_code': row[8],
                        'admin1_code': row[10],
                        'admin2_code': row[11],
                        'population': int(row[14]) if row[14] else 0,
                        'elevation': int(row[15]) if row[15] else None,
                        'modification_date': row[18]
                    }
                    places.append(place)

                except Exception as e:
                    print(f"Error parsing row {i}: {e}")
                    continue

        return places

    def load_to_neo4j(self, places: List[Dict]):
        """Load GeoNames places into Neo4j"""
        with self.driver.session() as session:
            for i, place in enumerate(places):
                try:
                    session.execute_write(self._create_geonames_place, place)

                    if (i + 1) % 1000 == 0:
                        print(f"Loaded {i + 1} / {len(places)} places")

                except Exception as e:
                    print(f"Error loading place {place.get('geonameid')}: {e}")
                    continue

        print(f"Successfully loaded {len(places)} GeoNames places to Neo4j")

    @staticmethod
    def _create_geonames_place(tx, place):
        """Create or merge GeoNames Place node"""
        # Determine feature type
        feature_class = place['feature_class']
        if feature_class == 'P':  # Populated place
            feature_type = 'GPE'
        elif feature_class in ['H', 'T']:  # Hydrographic or terrain
            feature_type = 'LOC'
        elif feature_class == 'S':  # Spot, building, farm
            feature_type = 'FAC'
        else:
            feature_type = 'LOC'

        # Create Place node
        query = """
        MERGE (p:Place {place_id: $place_id})
        ON CREATE SET
            p.name = $name,
            p.latitude = $latitude,
            p.longitude = $longitude,
            p.source = 'geonames',
            p.feature_type = $feature_type,
            p.feature_code = $feature_code,
            p.country_code = $country_code,
            p.population = $population
        ON MATCH SET
            p.name = $name,
            p.latitude = $latitude,
            p.longitude = $longitude
        """
        tx.run(query,
               place_id=f"geonames_{place['geonameid']}",
               name=place['name'],
               latitude=place['latitude'],
               longitude=place['longitude'],
               feature_type=feature_type,
               feature_code=place['feature_code'],
               country_code=place['country_code'],
               population=place['population'])

        # Create HistoricalName nodes for alternate names
        for alt_name in place['alternatenames'][:5]:  # Limit to 5 alternates
            if alt_name and alt_name != place['name']:
                name_query = """
                MERGE (h:HistoricalName {name_id: $name_id})
                ON CREATE SET
                    h.name = $name,
                    h.language = 'en',
                    h.valid_from = 'unknown',
                    h.valid_to = 'present',
                    h.name_type = 'alternate',
                    h.script = 'latin'
                WITH h
                MATCH (p:Place {place_id: $place_id})
                MERGE (p)-[:HAS_NAME]->(h)
                """
                tx.run(name_query,
                       name_id=f"geonames_{place['geonameid']}_alt_{hash(alt_name) % 10000}",
                       name=alt_name,
                       place_id=f"geonames_{place['geonameid']}")

    def link_wikidata_geonames(self):
        """
        Create SAME_AS relationships between Wikidata and GeoNames places
        based on name and coordinate proximity
        """
        with self.driver.session() as session:
            query = """
            MATCH (w:Place {source: 'wikidata'})
            MATCH (g:Place {source: 'geonames'})
            WHERE w.name = g.name
              AND abs(w.latitude - g.latitude) < 0.1
              AND abs(w.longitude - g.longitude) < 0.1
            MERGE (w)-[:SAME_AS]-(g)
            RETURN count(*) as links_created
            """
            result = session.run(query)
            links = result.single()['links_created']
            print(f"Created {links} SAME_AS links between Wikidata and GeoNames")


def main():
    """Main execution function"""
    # Neo4j connection details
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "your-password-here"  # Change this!

    # Countries to download (add more as needed)
    COUNTRIES = ['US', 'FR', 'GB', 'DE', 'IT', 'ES']

    # Initialize ingestor
    ingestor = GeoNamesIngestor(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

    try:
        # Download GeoNames data
        ingestor.download_geonames_data(COUNTRIES)

        # Parse and load each country
        for country in COUNTRIES:
            filepath = os.path.join(ingestor.data_dir, f"{country}.txt")
            if os.path.exists(filepath):
                print(f"\nProcessing {country}...")
                places = ingestor.parse_geonames_file(filepath, limit=10000)  # Limit for testing
                ingestor.load_to_neo4j(places)

        # Link Wikidata and GeoNames
        print("\nLinking Wikidata and GeoNames places...")
        ingestor.link_wikidata_geonames()

    finally:
        ingestor.close()


if __name__ == "__main__":
    main()

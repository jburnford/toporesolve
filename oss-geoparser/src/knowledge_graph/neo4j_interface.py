"""
Neo4j Knowledge Graph Interface

Wrapper around Canadian LOD Knowledge Graph with 556K+ places.
Provides clean interface for candidate retrieval and caching.
"""

import logging
from typing import List, Dict, Optional
from neo4j import GraphDatabase


class Neo4jKnowledgeGraph:
    """
    Interface to Canadian Neo4j LOD database

    Features:
    - 556K+ Canadian and global places
    - GeoNames and Wikidata IDs for LOD linking
    - Case-insensitive name matching
    - Population-based ranking
    - Admin hierarchy (country, province, etc.)
    """

    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize Neo4j connection

        Args:
            uri: Neo4j bolt URI (e.g., "bolt://localhost:7687")
            user: Database username
            password: Database password
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.logger = logging.getLogger(__name__)

    def close(self):
        """Close Neo4j connection"""
        self.driver.close()

    def normalize_toponym(self, toponym: str) -> str:
        """
        Normalize toponym for better matching

        Handles:
        - Possessives: "California's" -> "California"
        - Trailing punctuation
        - Extra whitespace
        """
        # Remove possessive 's
        if toponym.endswith("'s"):
            toponym = toponym[:-2]

        # Strip whitespace and punctuation
        toponym = toponym.strip().strip(".,;:")

        return toponym

    def get_candidates(
        self,
        toponym: str,
        limit: int = 10,
        country_filter: Optional[str] = None,
        feature_class_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Retrieve candidate places matching toponym

        Args:
            toponym: Place name to search for
            limit: Maximum number of candidates to return
            country_filter: Optional ISO country code (e.g., "CA" for Canada)
            feature_class_filter: Optional GeoNames feature class (e.g., "P" for populated places)

        Returns:
            List of candidate dictionaries with:
            - id: Internal ID for reference
            - geonameId: GeoNames ID
            - wikidataId: Wikidata ID
            - title: Place name
            - lat, lon: Coordinates
            - feature_class, feature_code: GeoNames classification
            - country, admin1, admin2: Administrative hierarchy
            - population: Population (if available)
            - alternateNames: List of alternate name forms
        """
        normalized = self.normalize_toponym(toponym)
        self.logger.info(f"Querying Neo4j for: '{toponym}' (normalized: '{normalized}')")

        # Generate case variants
        title_case = normalized.title()
        upper_case = normalized.upper()
        lower_case = normalized.lower()

        # Build query with optional filters
        filter_clause = ""
        params = {
            "title": title_case,
            "upper": upper_case,
            "lower": lower_case,
            "limit": limit
        }

        if country_filter:
            filter_clause += " AND p.countryCode = $country"
            params["country"] = country_filter

        if feature_class_filter:
            filter_clause += " AND p.featureClass = $featureClass"
            params["featureClass"] = feature_class_filter

        query = f"""
        MATCH (p:Place)
        WHERE (p.name IN [$title, $upper, $lower]
           OR p.asciiName IN [$title, $upper, $lower]
           OR $title IN p.alternateNames
           OR $upper IN p.alternateNames
           OR $lower IN p.alternateNames)
        {filter_clause}
        WITH p, COALESCE(p.population, 0) AS pop
        RETURN p.geonameId AS geonameId,
               p.wikidataId AS wikidataId,
               p.name AS title,
               p.alternateNames AS alternateNames,
               p.latitude AS lat,
               p.longitude AS lon,
               p.featureClass AS feature_class,
               p.featureCode AS feature_code,
               p.countryCode AS country,
               p.admin1Code AS admin1,
               p.admin2Code AS admin2,
               pop AS population
        ORDER BY pop DESC
        LIMIT $limit
        """

        try:
            with self.driver.session() as session:
                result = session.run(query, params)
                candidates = []

                for i, record in enumerate(result):
                    candidate = {
                        'id': i,
                        'geonameId': record['geonameId'],
                        'wikidataId': record.get('wikidataId'),
                        'title': record['title'],
                        'lat': record['lat'],
                        'lon': record['lon'],
                        'feature_class': record['feature_class'],
                        'feature_code': record['feature_code'],
                        'country': record['country'],
                        'admin1': record.get('admin1'),
                        'admin2': record.get('admin2'),
                        'population': record.get('population'),
                        'alternateNames': record.get('alternateNames', [])
                    }
                    candidates.append(candidate)

                self.logger.info(f"Found {len(candidates)} candidates for '{toponym}'")
                return candidates

        except Exception as e:
            self.logger.error(f"Neo4j query error for '{toponym}': {e}")
            return []

    def get_place_by_geoname_id(self, geoname_id: int) -> Optional[Dict]:
        """
        Retrieve place by GeoNames ID

        Args:
            geoname_id: GeoNames integer ID

        Returns:
            Place dictionary or None if not found
        """
        query = """
        MATCH (p:Place {geonameId: $geonameId})
        RETURN p.geonameId AS geonameId,
               p.wikidataId AS wikidataId,
               p.name AS title,
               p.alternateNames AS alternateNames,
               p.latitude AS lat,
               p.longitude AS lon,
               p.featureClass AS feature_class,
               p.featureCode AS feature_code,
               p.countryCode AS country,
               p.admin1Code AS admin1,
               p.admin2Code AS admin2,
               p.population AS population
        """

        try:
            with self.driver.session() as session:
                result = session.run(query, {"geonameId": geoname_id})
                record = result.single()

                if record:
                    return {
                        'id': 0,
                        'geonameId': record['geonameId'],
                        'wikidataId': record.get('wikidataId'),
                        'title': record['title'],
                        'lat': record['lat'],
                        'lon': record['lon'],
                        'feature_class': record['feature_class'],
                        'feature_code': record['feature_code'],
                        'country': record['country'],
                        'admin1': record.get('admin1'),
                        'admin2': record.get('admin2'),
                        'population': record.get('population'),
                        'alternateNames': record.get('alternateNames', [])
                    }
                return None

        except Exception as e:
            self.logger.error(f"Neo4j query error for GeoNames ID {geoname_id}: {e}")
            return None

    def get_nearby_places(
        self,
        lat: float,
        lon: float,
        radius_km: float = 50,
        limit: int = 20
    ) -> List[Dict]:
        """
        Find places within radius of coordinates

        Args:
            lat: Latitude
            lon: Longitude
            radius_km: Search radius in kilometers
            limit: Maximum results

        Returns:
            List of nearby places with distance
        """
        # Calculate approximate degree offset
        # 1 degree latitude ≈ 111 km
        # Longitude varies by latitude but this is rough approximation
        lat_offset = radius_km / 111.0
        lon_offset = radius_km / (111.0 * abs(float(lat)) if lat != 0 else 111.0)

        query = """
        MATCH (p:Place)
        WHERE p.latitude >= $minLat AND p.latitude <= $maxLat
          AND p.longitude >= $minLon AND p.longitude <= $maxLon
        WITH p,
             point({latitude: $lat, longitude: $lon}) AS searchPoint,
             point({latitude: p.latitude, longitude: p.longitude}) AS placePoint
        WITH p, distance(searchPoint, placePoint) / 1000.0 AS distanceKm
        WHERE distanceKm <= $radius
        RETURN p.geonameId AS geonameId,
               p.name AS title,
               p.latitude AS lat,
               p.longitude AS lon,
               p.countryCode AS country,
               p.population AS population,
               distanceKm
        ORDER BY distanceKm ASC
        LIMIT $limit
        """

        params = {
            "lat": lat,
            "lon": lon,
            "minLat": lat - lat_offset,
            "maxLat": lat + lat_offset,
            "minLon": lon - lon_offset,
            "maxLon": lon + lon_offset,
            "radius": radius_km,
            "limit": limit
        }

        try:
            with self.driver.session() as session:
                result = session.run(query, params)
                nearby = []

                for record in result:
                    place = {
                        'geonameId': record['geonameId'],
                        'title': record['title'],
                        'lat': record['lat'],
                        'lon': record['lon'],
                        'country': record['country'],
                        'population': record.get('population'),
                        'distance_km': record['distanceKm']
                    }
                    nearby.append(place)

                self.logger.info(f"Found {len(nearby)} places within {radius_km}km of ({lat}, {lon})")
                return nearby

        except Exception as e:
            self.logger.error(f"Neo4j nearby query error: {e}")
            return []

    def get_statistics(self) -> Dict:
        """
        Get knowledge graph statistics

        Returns:
            Dictionary with node/relationship counts
        """
        query = """
        MATCH (p:Place)
        RETURN count(p) AS total_places,
               count(DISTINCT p.countryCode) AS countries,
               sum(CASE WHEN p.featureClass = 'P' THEN 1 ELSE 0 END) AS populated_places
        """

        try:
            with self.driver.session() as session:
                result = session.run(query)
                record = result.single()

                return {
                    'total_places': record['total_places'],
                    'countries': record['countries'],
                    'populated_places': record['populated_places']
                }

        except Exception as e:
            self.logger.error(f"Neo4j statistics query error: {e}")
            return {}

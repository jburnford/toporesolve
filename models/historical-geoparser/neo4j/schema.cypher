// Neo4j Schema for Historical Toponym Disambiguation
// Run this file to set up the graph database schema

// ============================================================
// CONSTRAINTS (Unique IDs)
// ============================================================

CREATE CONSTRAINT place_id IF NOT EXISTS
FOR (p:Place) REQUIRE p.place_id IS UNIQUE;

CREATE CONSTRAINT admin_entity_id IF NOT EXISTS
FOR (a:AdministrativeEntity) REQUIRE a.entity_id IS UNIQUE;

CREATE CONSTRAINT historical_name_id IF NOT EXISTS
FOR (h:HistoricalName) REQUIRE h.name_id IS UNIQUE;

// ============================================================
// INDEXES (Performance optimization)
// ============================================================

CREATE INDEX place_name_idx IF NOT EXISTS FOR (p:Place) ON (p.name);
CREATE INDEX place_coords_idx IF NOT EXISTS FOR (p:Place) ON (p.latitude, p.longitude);
CREATE INDEX historical_name_idx IF NOT EXISTS FOR (h:HistoricalName) ON (h.name);
CREATE INDEX admin_name_idx IF NOT EXISTS FOR (a:AdministrativeEntity) ON (a.name);

// ============================================================
// EXAMPLE DATA INSERTION
// ============================================================

// Example 1: Constantinople -> Istanbul name change
CREATE (p:Place {
  place_id: "Q406",
  name: "Istanbul",
  latitude: 41.0082,
  longitude: 28.9784,
  source: "wikidata",
  feature_type: "GPE",
  country_code: "TR"
});

CREATE (h1:HistoricalName {
  name_id: "Q406_name_1",
  name: "Constantinople",
  language: "en",
  valid_from: "330",
  valid_to: "1930-03-28",
  name_type: "official",
  script: "latin"
});

CREATE (h2:HistoricalName {
  name_id: "Q406_name_2",
  name: "Istanbul",
  language: "en",
  valid_from: "1930-03-28",
  valid_to: "present",
  name_type: "official",
  script: "latin"
});

CREATE (h3:HistoricalName {
  name_id: "Q406_name_3",
  name: "Byzantium",
  language: "en",
  valid_from: "-657",
  valid_to: "330",
  name_type: "official",
  script: "latin"
});

MATCH (p:Place {place_id: "Q406"}), (h1:HistoricalName {name_id: "Q406_name_1"})
CREATE (p)-[:HAS_NAME {valid_from: "330", valid_to: "1930-03-28"}]->(h1);

MATCH (p:Place {place_id: "Q406"}), (h2:HistoricalName {name_id: "Q406_name_2"})
CREATE (p)-[:HAS_NAME {valid_from: "1930-03-28", valid_to: "present"}]->(h2);

MATCH (p:Place {place_id: "Q406"}), (h3:HistoricalName {name_id: "Q406_name_3"})
CREATE (p)-[:HAS_NAME {valid_from: "-657", valid_to: "330"}]->(h3);

// Example 2: Paris (multiple places with same name)
CREATE (p1:Place {
  place_id: "Q90",
  name: "Paris",
  latitude: 48.8566,
  longitude: 2.3522,
  source: "wikidata",
  feature_type: "GPE",
  country_code: "FR"
});

CREATE (p2:Place {
  place_id: "Q16555",
  name: "Paris",
  latitude: 33.6609,
  longitude: -95.5555,
  source: "wikidata",
  feature_type: "GPE",
  country_code: "US"
});

CREATE (h4:HistoricalName {
  name_id: "Q90_name_1",
  name: "Paris",
  language: "en",
  valid_from: "present",
  valid_to: "present",
  name_type: "official",
  script: "latin"
});

CREATE (h5:HistoricalName {
  name_id: "Q16555_name_1",
  name: "Paris",
  language: "en",
  valid_from: "1844",
  valid_to: "present",
  name_type: "official",
  script: "latin"
});

MATCH (p1:Place {place_id: "Q90"}), (h4:HistoricalName {name_id: "Q90_name_1"})
CREATE (p1)-[:HAS_NAME]->(h4);

MATCH (p2:Place {place_id: "Q16555"}), (h5:HistoricalName {name_id: "Q16555_name_1"})
CREATE (p2)-[:HAS_NAME]->(h5);

// ============================================================
// USEFUL QUERIES FOR HISTORICAL DISAMBIGUATION
// ============================================================

// Query 1: Find all historical names for a place at a specific date
// MATCH (p:Place)-[r:HAS_NAME]->(h:HistoricalName)
// WHERE p.place_id = "Q406"
//   AND r.valid_from <= "1900"
//   AND (r.valid_to >= "1900" OR r.valid_to = "present")
// RETURN p, h;

// Query 2: Find all places with a given name at a specific date
// MATCH (p:Place)-[r:HAS_NAME]->(h:HistoricalName)
// WHERE h.name = "Constantinople"
//   AND r.valid_from <= "1900"
//   AND (r.valid_to >= "1900" OR r.valid_to = "present")
// RETURN p, h;

// Query 3: Find places within geographic bounds
// MATCH (p:Place)
// WHERE p.latitude >= 40 AND p.latitude <= 42
//   AND p.longitude >= 28 AND p.longitude <= 30
// RETURN p;

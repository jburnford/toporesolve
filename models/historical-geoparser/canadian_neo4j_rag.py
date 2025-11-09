"""
Canadian Historical Geoparser with Neo4j RAG
Queries existing Canadian LOD Knowledge Graph for verified coordinates
"""

import os
import json
import logging
from typing import List, Dict, Optional
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class CanadianGeoparserRAG:
    """
    RAG-based geoparser using Canadian Neo4j LOD database

    Key advantages over pure LLM:
    1. Returns verified coordinates from database (not LLM hallucinations)
    2. Can say "not found" instead of making up data
    3. Provides rich LOD (GeoNames ID, Wikidata ID, relationships)
    4. Explainable source attribution
    """

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        """Initialize connection to Canadian Neo4j database"""
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

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
        - Title case normalization (but preserve for query)
        """
        # Remove possessive 's
        if toponym.endswith("'s"):
            toponym = toponym[:-2]

        # Strip whitespace and punctuation
        toponym = toponym.strip().strip(".,;:")

        return toponym

    def query_candidates(self, toponym: str, max_results: int = 10) -> List[Dict]:
        """
        Query Neo4j for candidate places matching toponym

        Returns list of candidates with:
        - geonameId, wikidataId (source IDs for LOD linking)
        - name, alternateNames (for matching)
        - latitude, longitude (verified coordinates)
        - featureClass, featureCode (entity type)
        - population, admin info (disambiguation context)

        Uses case-insensitive matching with multiple name variants
        """
        # Normalize input
        normalized = self.normalize_toponym(toponym)
        logging.info(f"Querying Neo4j for: '{toponym}' (normalized: '{normalized}')")

        # Generate multiple case variants for matching
        # Most GeoNames data uses Title Case
        title_case = normalized.title()
        upper_case = normalized.upper()
        lower_case = normalized.lower()

        # Fast query: Try exact matches first (uses indexes if available)
        # Only convert to lowercase for comparison, not scanning
        query = """
        MATCH (p:Place)
        WHERE p.name IN [$title, $upper, $lower]
           OR p.asciiName IN [$title, $upper, $lower]
           OR $title IN p.alternateNames
           OR $upper IN p.alternateNames
           OR $lower IN p.alternateNames
        WITH p, COALESCE(p.population, 0) AS pop
        RETURN p.geonameId AS geonameId,
               p.wikidataId AS wikidataId,
               p.name AS name,
               p.alternateNames AS alternateNames,
               p.latitude AS latitude,
               p.longitude AS longitude,
               p.featureClass AS featureClass,
               p.featureCode AS featureCode,
               p.population AS population,
               p.countryCode AS countryCode
        ORDER BY pop DESC
        LIMIT $max_results
        """

        with self.driver.session() as session:
            # Pass all case variants for matching
            result = session.run(query,
                               title=title_case,
                               upper=upper_case,
                               lower=lower_case,
                               max_results=max_results)
            candidates = []

            for record in result:
                candidate = {
                    'geonameId': record['geonameId'],
                    'wikidataId': record['wikidataId'],
                    'name': record['name'],
                    'alternateNames': record['alternateNames'] or [],
                    'latitude': record['latitude'],
                    'longitude': record['longitude'],
                    'featureClass': record['featureClass'],
                    'featureCode': record['featureCode'],
                    'population': record['population'],
                    'countryCode': record['countryCode']
                }
                candidates.append(candidate)

            logging.info(f"Neo4j returned {len(candidates)} candidates for '{toponym}'")
            for i, c in enumerate(candidates[:5], 1):  # Log first 5
                logging.info(f"  Candidate {i}: {c['name']} ({c['featureCode']}) - pop: {c['population']}, coords: ({c['latitude']}, {c['longitude']})")

            return candidates

    def format_candidates_for_llm(self, candidates: List[Dict]) -> str:
        """
        Format candidates for LLM prompt
        Provides factual options for LLM to choose from
        """
        if not candidates:
            return "NO_CANDIDATES_FOUND"

        formatted = "CANDIDATE LOCATIONS FROM DATABASE:\n\n"

        for i, c in enumerate(candidates, 1):
            formatted += f"[{i}] {c['name']}\n"
            formatted += f"    Coordinates: {c['latitude']}, {c['longitude']}\n"
            formatted += f"    GeoNames ID: {c['geonameId']}\n"

            if c['wikidataId']:
                formatted += f"    Wikidata ID: {c['wikidataId']}\n"

            if c['alternateNames']:
                alt_names = ', '.join(c['alternateNames'][:3])
                formatted += f"    Also known as: {alt_names}\n"

            if c['population']:
                formatted += f"    Population: {c['population']:,}\n"

            formatted += f"    Type: {c['featureCode']}\n"
            formatted += "\n"

        return formatted

    def disambiguate_with_llm(self, toponym: str, context: str, candidates: List[Dict],
                               llm_client, source_location: Optional[Dict] = None,
                               model: str = "openai/gpt-oss-120b") -> Dict:
        """
        Use LLM to select best candidate from database results

        Key instruction: LLM must choose from candidates or say "none match"
        LLM cannot invent coordinates

        Args:
            source_location: Optional dict with 'city' and 'state' of media source
        """

        if not candidates:
            return {
                'status': 'no_candidates',
                'message': f'No matches for "{toponym}" found in Canadian LOD database',
                'geonameId': None,
                'wikidataId': None,
                'latitude': None,
                'longitude': None,
                'source': 'neo4j_query_returned_empty'
            }

        candidates_text = self.format_candidates_for_llm(candidates)

        # Add source location context if provided
        source_context = ""
        if source_location and source_location.get('city') and source_location.get('state'):
            source_context = f"""
SOURCE LOCATION: This place name appears in media from {source_location['city']}, {source_location['state']}.
Consider geographic proximity to the source location when selecting among candidates.
"""

        prompt = f"""You are a geography expert helping to disambiguate place names using a VERIFIED DATABASE of locations.

PLACE NAME: {toponym}
{source_context}
CONTEXT:
{context}

{candidates_text}

CRITICAL INSTRUCTIONS:
1. You MUST select ONE of the numbered candidates above, OR state "NONE_MATCH" only if the context strongly suggests a completely different specific location
2. You CANNOT invent or guess coordinates - only use the verified database coordinates provided
3. When the source location is provided, prefer candidates that are geographically closer or more relevant to that region
4. Consider context clues: nearby cities, administrative level, population size, and geographic proximity

Respond in this EXACT JSON format:
{{
  "selected_candidate": <number 1-{len(candidates)} or "NONE_MATCH">,
  "reasoning": "<brief explanation of why you chose this candidate>",
  "confidence": <0.0 to 1.0>
}}

Return ONLY the JSON, no other text."""

        logging.info(f"=== LLM Prompt for '{toponym}' ===")
        logging.info(f"Source: {source_location.get('city', 'N/A')}, {source_location.get('state', 'N/A')}" if source_location else "Source: Not provided")
        logging.info(f"Candidates: {len(candidates)}")
        logging.info(f"\n{prompt}\n")

        # Try LLM call with retry on JSON parse failure
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = llm_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=500
                )

                response_text = response.choices[0].message.content.strip()

                logging.info(f"=== LLM Response (attempt {attempt + 1}) ===")
                logging.info(f"{response_text}")
                logging.info("=" * 50)

                # Parse JSON response
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()

                llm_decision = json.loads(response_text)
                logging.info(f"Parsed decision: {llm_decision}")
                break  # Success - exit retry loop

            except json.JSONDecodeError as e:
                if attempt < max_retries - 1:
                    # Retry with more explicit JSON instruction
                    prompt = prompt.replace(
                        "Return ONLY the JSON, no other text.",
                        "Return ONLY valid JSON with no markdown formatting, no other text. Example: {\"selected_candidate\": 1, \"reasoning\": \"...\", \"confidence\": 0.8}"
                    )
                    continue
                else:
                    # Final retry failed
                    return {
                        'status': 'error',
                        'message': f'JSON parse failed after {max_retries} attempts: {str(e)}',
                        'raw_response': response_text[:300],
                        'geonameId': None,
                        'wikidataId': None,
                        'latitude': None,
                        'longitude': None,
                        'source': 'json_parse_error'
                    }
            except Exception as e:
                return {
                    'status': 'error',
                    'message': f'LLM API error: {str(e)}',
                    'geonameId': None,
                    'wikidataId': None,
                    'latitude': None,
                    'longitude': None,
                    'source': 'llm_api_error'
                }

        # Process LLM decision (moved outside try block)
        try:
            selected = llm_decision.get('selected_candidate')

            logging.info(f"=== Final Decision for '{toponym}' ===")
            logging.info(f"Selected: {selected}")
            logging.info(f"Reasoning: {llm_decision.get('reasoning', 'N/A')}")
            logging.info(f"Confidence: {llm_decision.get('confidence', 'N/A')}")

            if selected == "NONE_MATCH" or selected is None:
                logging.info("Result: NONE_MATCH - LLM rejected all candidates")
                return {
                    'status': 'no_match',
                    'message': f'LLM determined none of {len(candidates)} candidates match context',
                    'reasoning': llm_decision.get('reasoning', ''),
                    'confidence': llm_decision.get('confidence', 0.0),
                    'candidates_reviewed': len(candidates),
                    'geonameId': None,
                    'wikidataId': None,
                    'latitude': None,
                    'longitude': None,
                    'source': 'llm_rejected_all_candidates'
                }

            # LLM selected a candidate
            selected_idx = int(selected) - 1
            if 0 <= selected_idx < len(candidates):
                chosen = candidates[selected_idx]
                logging.info(f"Result: SUCCESS - Selected candidate {selected}: {chosen['name']} at ({chosen['latitude']}, {chosen['longitude']})")
                return {
                    'status': 'success',
                    'geonameId': chosen['geonameId'],
                    'wikidataId': chosen['wikidataId'],
                    'name': chosen['name'],
                    'latitude': chosen['latitude'],
                    'longitude': chosen['longitude'],
                    'featureCode': chosen['featureCode'],
                    'population': chosen['population'],
                    'reasoning': llm_decision.get('reasoning', ''),
                    'confidence': llm_decision.get('confidence', 0.0),
                    'candidates_reviewed': len(candidates),
                    'source': 'neo4j_database',
                    'alternateNames': chosen['alternateNames']
                }
            else:
                return {
                    'status': 'error',
                    'message': f'LLM selected invalid candidate number: {selected}',
                    'geonameId': None,
                    'wikidataId': None,
                    'latitude': None,
                    'longitude': None,
                    'source': 'llm_error'
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Error processing LLM decision: {str(e)}',
                'geonameId': None,
                'wikidataId': None,
                'latitude': None,
                'longitude': None,
                'source': 'decision_processing_error'
            }

    def disambiguate(self, toponym: str, context: str, llm_client,
                     source_location: Optional[Dict] = None,
                     model: str = "openai/gpt-oss-120b") -> Dict:
        """
        Full RAG pipeline:
        1. Query Neo4j for candidates
        2. Format for LLM
        3. LLM selects best match
        4. Return verified coordinates with LOD metadata

        Args:
            source_location: Optional dict with 'city' and 'state' of media source
        """

        # Step 1: Query database
        candidates = self.query_candidates(toponym)

        # Step 2+3: LLM disambiguation with geographic context
        result = self.disambiguate_with_llm(toponym, context, candidates, llm_client,
                                            source_location, model)

        return result


def main():
    """Test the RAG system"""
    from openai import OpenAI

    # Initialize
    llm_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv('OPENROUTER_API_KEY')
    )

    rag = CanadianGeoparserRAG(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password=os.getenv('NEO4J_PASSWORD')
    )

    # Test cases
    test_cases = [
        {
            'toponym': 'Toronto',
            'context': 'The largest city in Ontario, home to the CN Tower and Raptors.'
        },
        {
            'toponym': 'Springfield',
            'context': 'The city is located in Massachusetts near Boston.'
        },
        {
            'toponym': 'Fort Garry',
            'context': 'The Red River Rebellion began near Fort Garry in 1869.'
        }
    ]

    print("Testing Canadian Historical Geoparser with RAG\n")
    print("="*70)

    for test in test_cases:
        print(f"\nToponym: {test['toponym']}")
        print(f"Context: {test['context'][:60]}...")

        result = rag.disambiguate(test['toponym'], test['context'], llm_client)

        print(f"Status: {result['status']}")
        if result['status'] == 'success':
            print(f"Coordinates: ({result['latitude']}, {result['longitude']})")
            print(f"GeoNames ID: {result['geonameId']}")
            if result['wikidataId']:
                print(f"Wikidata ID: {result['wikidataId']}")
            print(f"Confidence: {result['confidence']}")
            print(f"Reasoning: {result['reasoning'][:80]}...")
        else:
            print(f"Message: {result['message']}")

        print("-"*70)

    rag.close()


if __name__ == "__main__":
    main()

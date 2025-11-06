"""
RAG Pipeline for Historical Toponym Disambiguation
Combines Neo4j knowledge graph with LLM reasoning
"""

import os
import json
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neo4j.query_utils import HistoricalPlaceQuerier


class HistoricalGeoparserRAG:
    """
    RAG-based Historical Geoparser

    Pipeline:
    1. Extract toponym and date from context
    2. Query Neo4j for historical candidate locations
    3. Construct enriched prompt with candidates
    4. Let LLM disambiguate using context + candidates
    5. Return coordinates with explanation
    """

    def __init__(self, llm_client, neo4j_uri, neo4j_user, neo4j_password):
        """
        Initialize RAG pipeline

        Args:
            llm_client: OpenAI-compatible client (OpenRouter, OpenAI, etc.)
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
        """
        self.llm_client = llm_client
        self.querier = HistoricalPlaceQuerier(neo4j_uri, neo4j_user, neo4j_password)

    def close(self):
        """Close Neo4j connection"""
        self.querier.close()

    def extract_date_from_context(self, context: str) -> Optional[str]:
        """
        Extract year from context text
        Looks for patterns like: 1916, in 1850, during 1914-1918
        """
        # Pattern for 4-digit years between 1600-1950
        patterns = [
            r'\b(1[6-9]\d{2})\b',  # Years 1600-1999
        ]

        for pattern in patterns:
            match = re.search(pattern, context)
            if match:
                year = match.group(1)
                if 1600 <= int(year) <= 1950:
                    return year

        return None

    def query_knowledge_graph(self, toponym: str, year: str,
                              entity_type: Optional[str] = None) -> List[Dict]:
        """
        Query Neo4j for candidate locations

        Args:
            toponym: Place name to search for
            year: Year as string (e.g., "1916")
            entity_type: Optional entity type filter (GPE, LOC, FAC)

        Returns:
            List of candidate places with metadata
        """
        candidates = self.querier.find_places_by_name_and_date(toponym, year, max_results=10)

        # Filter by entity type if provided
        if entity_type:
            candidates = [c for c in candidates if c['feature_type'] == entity_type]

        # If no candidates found, try fuzzy matching
        if not candidates:
            candidates = self.querier.find_places_by_fuzzy_name(toponym, year, max_results=5)

        return candidates

    def format_candidates_for_prompt(self, candidates: List[Dict]) -> str:
        """
        Format candidate locations for LLM prompt
        Creates a structured list of options
        """
        if not candidates:
            return "No historical records found for this place name."

        formatted = "Historical location candidates:\n\n"

        for i, candidate in enumerate(candidates, 1):
            formatted += f"{i}. {candidate['historical_name']}"

            # Add current name if different
            if candidate['current_name'] != candidate['historical_name']:
                formatted += f" (now: {candidate['current_name']})"

            formatted += "\n"
            formatted += f"   - Coordinates: {candidate['latitude']}, {candidate['longitude']}\n"
            formatted += f"   - Country: {candidate['country_code']}\n"
            formatted += f"   - Type: {candidate['feature_type']}\n"

            # Add temporal validity info
            if candidate['name_valid_from'] and candidate['name_valid_from'] != 'unknown':
                formatted += f"   - Name valid: {candidate['name_valid_from']} to {candidate['name_valid_to']}\n"

            formatted += f"   - Source: {candidate['source']}\n\n"

        return formatted

    def construct_prompt(self, toponym: str, context: str, year: str,
                        entity_type: str, candidates: List[Dict]) -> str:
        """
        Construct enriched prompt for LLM with historical context
        """
        candidates_text = self.format_candidates_for_prompt(candidates)

        prompt = f"""You are a historical geography expert specializing in disambiguating place names from historical documents (1600-1950).

**Task**: Disambiguate the following toponym to precise coordinates as they would have been understood in the given year.

**Toponym**: {toponym}
**Entity Type**: {entity_type}
**Year**: {year}
**Context**: {context}

{candidates_text}

**Instructions**:
1. Analyze the context carefully to understand which location is being referenced
2. Consider the historical period ({year}) - place names and boundaries may have changed
3. If multiple candidates exist, use contextual clues to select the most likely one
4. Consider geographic proximity to other places mentioned in the context
5. Account for historical political contexts (e.g., colonial names, empire boundaries)

**Important considerations for {year}**:
- Use the place name and boundaries that existed in {year}
- Account for historical spelling variations and OCR errors
- Consider the political and administrative divisions of the time period

**Output format**:
latitude: <value>
longitude: <value>
explanation: <brief explanation of your reasoning, including which candidate you selected and why>

If you cannot confidently disambiguate the toponym, explain why and provide your best estimate."""

        return prompt

    def parse_llm_response(self, response_text: str) -> Tuple[Optional[float], Optional[float], str]:
        """
        Parse LLM response to extract coordinates and explanation

        Returns:
            (latitude, longitude, explanation)
        """
        # Extract coordinates
        lat_lon_pattern = r"latitude\s*:\s*([-+]?\d*\.?\d+)\s*,?\s*longitude\s*:\s*([-+]?\d*\.?\d+)"
        match = re.search(lat_lon_pattern, response_text, re.IGNORECASE)

        if match:
            latitude = float(match.group(1))
            longitude = float(match.group(2))
        else:
            latitude = None
            longitude = None

        # Extract explanation
        explanation_pattern = r"explanation\s*:\s*(.+?)(?:\n\n|\Z)"
        explanation_match = re.search(explanation_pattern, response_text, re.IGNORECASE | re.DOTALL)

        if explanation_match:
            explanation = explanation_match.group(1).strip()
        else:
            explanation = response_text

        return latitude, longitude, explanation

    def disambiguate(self, toponym: str, context: str, entity_type: str,
                    source_year: Optional[str] = None,
                    model: str = "qwen/qwen-2.5-72b-instruct") -> Dict:
        """
        Main disambiguation method

        Args:
            toponym: Place name to disambiguate
            context: Text context containing the toponym
            entity_type: Entity type (GPE, LOC, FAC)
            source_year: Optional year (will be extracted from context if not provided)
            model: LLM model to use

        Returns:
            Dictionary with results:
            {
                'toponym': str,
                'latitude': float,
                'longitude': float,
                'year': str,
                'candidates': List[Dict],
                'explanation': str,
                'model': str
            }
        """
        # Extract or use provided year
        year = source_year or self.extract_date_from_context(context)

        if not year:
            # Default to mid-point if no year found
            year = "1800"
            print(f"Warning: No year found in context, defaulting to {year}")

        # Query knowledge graph for candidates
        candidates = self.query_knowledge_graph(toponym, year, entity_type)

        # Construct prompt with RAG context
        prompt = self.construct_prompt(toponym, context, year, entity_type, candidates)

        # Call LLM
        try:
            response = self.llm_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.1  # Low temperature for consistency
            )

            response_text = response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error calling LLM: {e}")
            response_text = ""

        # Parse response
        latitude, longitude, explanation = self.parse_llm_response(response_text)

        return {
            'toponym': toponym,
            'latitude': latitude,
            'longitude': longitude,
            'year': year,
            'candidates': candidates,
            'explanation': explanation,
            'model': model,
            'raw_response': response_text
        }

    def batch_disambiguate(self, toponyms: List[Dict], model: str,
                          output_file: str = None) -> List[Dict]:
        """
        Batch process multiple toponyms

        Args:
            toponyms: List of dicts with keys: toponym, context, entity_type, year (optional)
            model: LLM model to use
            output_file: Optional path to save results

        Returns:
            List of disambiguation results
        """
        results = []

        for i, item in enumerate(toponyms):
            print(f"Processing {i+1}/{len(toponyms)}: {item['toponym']}")

            try:
                result = self.disambiguate(
                    toponym=item['toponym'],
                    context=item['context'],
                    entity_type=item['entity_type'],
                    source_year=item.get('year'),
                    model=model
                )
                results.append(result)

            except Exception as e:
                print(f"Error processing {item['toponym']}: {e}")
                results.append({
                    'toponym': item['toponym'],
                    'latitude': None,
                    'longitude': None,
                    'error': str(e)
                })

        # Save results if output file specified
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"Results saved to {output_file}")

        return results


def example_usage():
    """Example usage of the RAG pipeline"""
    from openai import OpenAI

    # Initialize OpenRouter client
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY")
    )

    # Initialize RAG pipeline
    geoparser = HistoricalGeoparserRAG(
        llm_client=client,
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="your-password-here"
    )

    try:
        # Example 1: Constantinople in 1900
        result = geoparser.disambiguate(
            toponym="Constantinople",
            context="The Ottoman Empire's capital Constantinople faced economic challenges in 1900.",
            entity_type="GPE",
            source_year="1900",
            model="qwen/qwen-2.5-72b-instruct"
        )

        print("\n=== Result ===")
        print(f"Toponym: {result['toponym']}")
        print(f"Year: {result['year']}")
        print(f"Coordinates: ({result['latitude']}, {result['longitude']})")
        print(f"Candidates found: {len(result['candidates'])}")
        print(f"Explanation: {result['explanation']}")

    finally:
        geoparser.close()


if __name__ == "__main__":
    example_usage()

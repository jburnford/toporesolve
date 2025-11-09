"""
RAG-enhanced disambiguation using Canadian Neo4j + GPT-OSS-120B
Follows same pattern as openrouter-gpt-oss.py but with Neo4j knowledge graph
"""

import re
import json
import argparse
import os
import sys
from openai import OpenAI
from dotenv import load_dotenv

# Add path for RAG module
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'historical-geoparser'))
from canadian_neo4j_rag import CanadianGeoparserRAG

# Load environment variables
load_dotenv()


def disambiguate_entity_with_coords(entity_type, entity, sentence, city, state, rag_system, llm_client):
    """
    Disambiguate entity using RAG (Neo4j + LLM)
    Returns coordinates from verified database, not LLM hallucinations
    """

    # Use RAG system with geographic context
    source_location = {'city': city, 'state': state}
    result = rag_system.disambiguate(entity, sentence, llm_client, source_location)

    return {
        "latitude": result.get('latitude'),
        "longitude": result.get('longitude'),
        "response_text": result.get('reasoning', ''),
        "geonameId": result.get('geonameId'),
        "wikidataId": result.get('wikidataId'),
        "confidence": result.get('confidence'),
        "status": result.get('status'),
        "source": result.get('source'),
        "candidates_reviewed": result.get('candidates_reviewed', 0)
    }


def process_jsonl(input_file, output_file, entity_type):
    """
    Process JSONL file with RAG-enhanced disambiguation
    """

    # Initialize
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment")

    llm_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
    )

    rag_system = CanadianGeoparserRAG(
        neo4j_uri=os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        neo4j_user=os.getenv('NEO4J_USER', 'neo4j'),
        neo4j_password=os.getenv('NEO4J_PASSWORD')
    )

    results = []

    with open(input_file, 'r', encoding='utf-8') as file:
        for line in file:
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"JSONDecodeError: {e} for line: {line}")
                continue

            entity = data['entity']
            city = data['media_dets']['location_name']
            state = data['media_dets']['state']

            # Combine all sentences into one
            combined_sentence = ". ".join(sent_obj['sent'] for sent_obj in data['context']['sents'])

            if entity in combined_sentence:
                print(f"Processing: {entity} (from {city}, {state})")
                try:
                    disambiguated_info = disambiguate_entity_with_coords(
                        entity_type, entity, combined_sentence, city, state,
                        rag_system, llm_client
                    )
                    result = {
                        'entity': entity,
                        'disambiguated_info': disambiguated_info,
                        'source': data
                    }
                    results.append(result)
                except Exception as e:
                    print(f"Error processing {entity}: {str(e)}")
                    continue

    # Close Neo4j connection
    rag_system.close()

    with open(output_file, 'w', encoding='utf-8') as outfile:
        json.dump(results, outfile, indent=4, ensure_ascii=False)

    print(f"\nProcessed {len(results)} entities. Results saved to {output_file}")

    # Print summary statistics
    successful = sum(1 for r in results if r['disambiguated_info']['status'] == 'success')
    no_candidates = sum(1 for r in results if r['disambiguated_info']['status'] == 'no_candidates')
    no_match = sum(1 for r in results if r['disambiguated_info']['status'] == 'no_match')
    errors = sum(1 for r in results if r['disambiguated_info']['status'] == 'error')

    print(f"\nSummary:")
    print(f"  Successful: {successful}/{len(results)} ({successful/len(results)*100:.1f}%)")
    print(f"  No candidates in DB: {no_candidates}")
    print(f"  LLM rejected all: {no_match}")
    print(f"  Errors: {errors}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Disambiguate entities using RAG (Neo4j + GPT-OSS-120B)")

    # Define command-line arguments
    parser.add_argument('--input_file', help="Path to the input JSONL file")
    parser.add_argument('--output_file', help="Path to the output JSON file")
    parser.add_argument('--entity_type', choices=['geopolitical (GPE)', 'location (LOC)', 'facility (FAC)'],
                       help="either of 'geopolitical (GPE)', 'location (LOC)', 'facility (FAC)")

    args = parser.parse_args()

    process_jsonl(args.input_file, args.output_file, args.entity_type)

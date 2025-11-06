"""
DRAC Batch Inference Script
Optimized for large-scale processing on DRAC clusters using vLLM
"""

import os
import sys
import json
import argparse
from typing import List, Dict
from pathlib import Path
import torch
from tqdm import tqdm

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from neo4j.query_utils import HistoricalPlaceQuerier
from rag_pipeline import HistoricalGeoparserRAG


class DRACInferenceEngine:
    """
    Optimized inference engine for DRAC clusters
    Uses vLLM for fast batched inference
    """

    def __init__(self, model_name: str, neo4j_uri: str,
                 neo4j_user: str, neo4j_password: str,
                 use_vllm: bool = True):
        """
        Initialize inference engine

        Args:
            model_name: HuggingFace model name
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            use_vllm: Use vLLM for faster inference (recommended)
        """
        self.model_name = model_name
        self.use_vllm = use_vllm

        print(f"Initializing inference engine...")
        print(f"Model: {model_name}")
        print(f"Using vLLM: {use_vllm}")
        print(f"Available GPUs: {torch.cuda.device_count()}")

        # Initialize Neo4j connection
        self.querier = HistoricalPlaceQuerier(neo4j_uri, neo4j_user, neo4j_password)

        # Initialize LLM
        if use_vllm:
            self._init_vllm()
        else:
            self._init_transformers()

    def _init_vllm(self):
        """Initialize vLLM engine for fast inference"""
        try:
            from vllm import LLM, SamplingParams

            print("Loading model with vLLM...")

            # Configure vLLM
            self.llm = LLM(
                model=self.model_name,
                tensor_parallel_size=torch.cuda.device_count(),  # Use all GPUs
                max_model_len=8192,  # Adjust based on model
                gpu_memory_utilization=0.9,
                dtype="float16",  # or "bfloat16"
            )

            self.sampling_params = SamplingParams(
                temperature=0.1,  # Low for consistency
                top_p=0.95,
                max_tokens=500,
            )

            print(f"✓ Model loaded successfully with vLLM")

        except ImportError:
            print("Warning: vLLM not available, falling back to transformers")
            self.use_vllm = False
            self._init_transformers()

    def _init_transformers(self):
        """Initialize with transformers (fallback)"""
        from transformers import AutoTokenizer, AutoModelForCausalLM

        print("Loading model with transformers...")

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=torch.float16,
            device_map="auto",
        )

        print(f"✓ Model loaded successfully with transformers")

    def create_prompts(self, toponyms: List[Dict]) -> List[str]:
        """
        Create prompts for batch processing

        Args:
            toponyms: List of dicts with keys: toponym, context, entity_type, year

        Returns:
            List of prompts
        """
        prompts = []

        for item in toponyms:
            toponym = item['toponym']
            context = item['context']
            entity_type = item.get('entity_type', 'GPE')
            year = item.get('year', '1800')

            # Query Neo4j for candidates
            candidates = self.querier.find_places_by_name_and_date(
                toponym, year, max_results=10
            )

            # Format candidates
            candidates_text = self._format_candidates(candidates)

            # Create prompt
            prompt = f"""You are a historical geography expert. Disambiguate the following place name:

Toponym: {toponym}
Type: {entity_type}
Year: {year}
Context: {context}

{candidates_text}

Provide coordinates as they existed in {year}.
Format: latitude: X.XX, longitude: Y.YY"""

            prompts.append(prompt)

        return prompts

    def _format_candidates(self, candidates: List[Dict]) -> str:
        """Format candidates for prompt"""
        if not candidates:
            return "No historical records found."

        text = "Historical candidates:\n"
        for i, c in enumerate(candidates[:5], 1):
            text += f"{i}. {c.get('historical_name', c.get('current_name'))}"
            text += f" ({c['latitude']}, {c['longitude']})\n"

        return text

    def batch_inference(self, prompts: List[str]) -> List[str]:
        """
        Run batched inference

        Args:
            prompts: List of prompts

        Returns:
            List of responses
        """
        if self.use_vllm:
            outputs = self.llm.generate(prompts, self.sampling_params)
            return [output.outputs[0].text for output in outputs]
        else:
            # Transformers batched inference
            responses = []
            for prompt in tqdm(prompts, desc="Generating"):
                inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=500,
                    temperature=0.1,
                    do_sample=True,
                )
                response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                responses.append(response)

            return responses

    def parse_response(self, response: str) -> Dict:
        """Parse LLM response to extract coordinates"""
        import re

        lat_lon_pattern = r"latitude\s*:\s*([-+]?\d*\.?\d+)\s*,?\s*longitude\s*:\s*([-+]?\d*\.?\d+)"
        match = re.search(lat_lon_pattern, response, re.IGNORECASE)

        if match:
            return {
                'latitude': float(match.group(1)),
                'longitude': float(match.group(2)),
                'raw_response': response
            }
        else:
            return {
                'latitude': None,
                'longitude': None,
                'raw_response': response
            }

    def process_file(self, input_file: str, output_file: str,
                    batch_size: int = 32):
        """
        Process input file and save results

        Args:
            input_file: Path to input JSONL file
            output_file: Path to output JSON file
            batch_size: Batch size for inference
        """
        print(f"\nProcessing: {input_file}")
        print(f"Output: {output_file}")

        # Load input data
        toponyms = []
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                toponyms.append(json.loads(line))

        print(f"Loaded {len(toponyms)} toponyms")

        # Process in batches
        all_results = []

        for i in range(0, len(toponyms), batch_size):
            batch = toponyms[i:i+batch_size]
            print(f"\nProcessing batch {i//batch_size + 1}/{(len(toponyms)-1)//batch_size + 1}")

            # Create prompts
            prompts = self.create_prompts(batch)

            # Run inference
            responses = self.batch_inference(prompts)

            # Parse responses
            for toponym, response in zip(batch, responses):
                result = self.parse_response(response)
                result['toponym'] = toponym['toponym']
                result['year'] = toponym.get('year')
                result['source'] = toponym
                all_results.append(result)

        # Save results
        print(f"\nSaving results to: {output_file}")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)

        # Print statistics
        successful = sum(1 for r in all_results if r['latitude'] is not None)
        print(f"\n✓ Processing complete!")
        print(f"Total: {len(all_results)}")
        print(f"Successful: {successful} ({successful/len(all_results)*100:.1f}%)")

    def close(self):
        """Clean up resources"""
        self.querier.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="DRAC batch inference for historical geoparser")

    parser.add_argument('--model', required=True, help="HuggingFace model name")
    parser.add_argument('--input', required=True, help="Input JSONL file")
    parser.add_argument('--output', required=True, help="Output JSON file")
    parser.add_argument('--batch_size', type=int, default=32, help="Batch size")
    parser.add_argument('--neo4j_uri', required=True, help="Neo4j URI")
    parser.add_argument('--neo4j_user', required=True, help="Neo4j username")
    parser.add_argument('--neo4j_password', required=True, help="Neo4j password")
    parser.add_argument('--no-vllm', action='store_true', help="Don't use vLLM")

    args = parser.parse_args()

    # Initialize engine
    engine = DRACInferenceEngine(
        model_name=args.model,
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        use_vllm=not args.no_vllm
    )

    try:
        # Process file
        engine.process_file(
            input_file=args.input,
            output_file=args.output,
            batch_size=args.batch_size
        )

    finally:
        engine.close()


if __name__ == "__main__":
    main()

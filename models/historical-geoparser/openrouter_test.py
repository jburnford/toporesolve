"""
OpenRouter Testing Framework
Test multiple open-weight models for historical toponym disambiguation
"""

import os
import json
import time
from typing import List, Dict
from openai import OpenAI

from rag_pipeline import HistoricalGeoparserRAG


class OpenRouterModelTester:
    """
    Test and compare multiple models via OpenRouter
    """

    # Models to test (ordered by expected performance)
    MODELS = [
        "qwen/qwen-2.5-72b-instruct",           # Best reasoning
        "meta-llama/llama-3.1-70b-instruct",    # Strong baseline
        "mistralai/mixtral-8x22b-instruct",     # Large context
        "cohere/command-r-plus",                # RAG-optimized
        "meta-llama/llama-3.1-8b-instruct",     # Fast/lightweight
        "mistralai/mistral-7b-instruct-v0.3",   # Baseline
    ]

    def __init__(self, api_key: str, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        """Initialize tester with OpenRouter credentials"""
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )

        self.rag_pipeline = HistoricalGeoparserRAG(
            llm_client=self.client,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password
        )

    def close(self):
        """Close Neo4j connection"""
        self.rag_pipeline.close()

    def create_test_cases(self) -> List[Dict]:
        """
        Create test cases covering different historical periods and challenges
        """
        return [
            {
                'toponym': 'Constantinople',
                'context': 'The Ottoman Empire\'s capital Constantinople faced economic challenges in 1900.',
                'entity_type': 'GPE',
                'year': '1900',
                'expected_lat': 41.0082,
                'expected_lon': 28.9784,
                'challenge': 'Historical name change (Constantinople → Istanbul 1930)'
            },
            {
                'toponym': 'Leningrad',
                'context': 'Leningrad endured a brutal siege during World War II in 1942.',
                'entity_type': 'GPE',
                'year': '1942',
                'expected_lat': 59.9343,
                'expected_lon': 30.3351,
                'challenge': 'Historical name (Leningrad → Saint Petersburg 1991)'
            },
            {
                'toponym': 'Verdun',
                'context': 'The battle near Verdun in 1916 was one of the longest of World War I.',
                'entity_type': 'GPE',
                'year': '1916',
                'expected_lat': 49.1589,
                'expected_lon': 5.3817,
                'challenge': 'Ambiguous (multiple places named Verdun)'
            },
            {
                'toponym': 'Paris',
                'context': 'The peace negotiations in Paris in 1919 led to the Treaty of Versailles.',
                'entity_type': 'GPE',
                'year': '1919',
                'expected_lat': 48.8566,
                'expected_lon': 2.3522,
                'challenge': 'Highly ambiguous (Paris, France vs Paris, Texas)'
            },
            {
                'toponym': 'Prague',
                'context': 'The Defenestration of Prague in 1618 sparked the Thirty Years\' War.',
                'entity_type': 'GPE',
                'year': '1618',
                'expected_lat': 50.0755,
                'expected_lon': 14.4378,
                'challenge': 'Early historical period (1600s)'
            },
            {
                'toponym': 'Bombay',
                'context': 'The textile industry in Bombay flourished during the 1920s.',
                'entity_type': 'GPE',
                'year': '1920',
                'expected_lat': 19.0760,
                'expected_lon': 72.8777,
                'challenge': 'Colonial name (Bombay → Mumbai 1995)'
            },
            {
                'toponym': 'Stalingrad',
                'context': 'The Battle of Stalingrad in 1942 was a turning point in World War II.',
                'entity_type': 'GPE',
                'year': '1942',
                'expected_lat': 48.6990,
                'expected_lon': 44.5018,
                'challenge': 'Soviet-era name (Stalingrad → Volgograd 1961)'
            },
            {
                'toponym': 'Ceylon',
                'context': 'Tea production in Ceylon expanded rapidly in the 1880s.',
                'entity_type': 'GPE',
                'year': '1880',
                'expected_lat': 7.8731,
                'expected_lon': 80.7718,
                'challenge': 'Colonial name (Ceylon → Sri Lanka 1972)'
            }
        ]

    def calculate_distance_error(self, lat1: float, lon1: float,
                                 lat2: float, lon2: float) -> float:
        """
        Calculate distance error in kilometers using Haversine formula
        """
        from math import radians, sin, cos, sqrt, atan2

        R = 6371  # Earth's radius in km

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))

        return R * c

    def test_model(self, model: str, test_cases: List[Dict]) -> Dict:
        """
        Test a single model on all test cases

        Returns:
            Dict with results and metrics
        """
        print(f"\n{'='*60}")
        print(f"Testing: {model}")
        print(f"{'='*60}")

        results = []
        total_distance_error = 0
        successful = 0
        failed = 0
        total_time = 0

        for i, test_case in enumerate(test_cases):
            print(f"\n[{i+1}/{len(test_cases)}] {test_case['toponym']} ({test_case['year']})")
            print(f"  Challenge: {test_case['challenge']}")

            start_time = time.time()

            try:
                result = self.rag_pipeline.disambiguate(
                    toponym=test_case['toponym'],
                    context=test_case['context'],
                    entity_type=test_case['entity_type'],
                    source_year=test_case['year'],
                    model=model
                )

                elapsed = time.time() - start_time
                total_time += elapsed

                # Calculate error
                if result['latitude'] and result['longitude']:
                    distance_error = self.calculate_distance_error(
                        result['latitude'], result['longitude'],
                        test_case['expected_lat'], test_case['expected_lon']
                    )
                    total_distance_error += distance_error

                    # Consider success if within 25km (same as evaluation metric)
                    is_correct = distance_error <= 25

                    if is_correct:
                        successful += 1
                        print(f"  ✓ CORRECT (error: {distance_error:.2f} km)")
                    else:
                        print(f"  ✗ INCORRECT (error: {distance_error:.2f} km)")

                    result['distance_error_km'] = distance_error
                    result['is_correct'] = is_correct
                else:
                    failed += 1
                    print(f"  ✗ FAILED (no coordinates returned)")
                    result['distance_error_km'] = None
                    result['is_correct'] = False

                result['elapsed_seconds'] = elapsed
                result['test_case'] = test_case
                results.append(result)

            except Exception as e:
                failed += 1
                print(f"  ✗ ERROR: {e}")
                results.append({
                    'toponym': test_case['toponym'],
                    'error': str(e),
                    'elapsed_seconds': time.time() - start_time,
                    'is_correct': False
                })

        # Calculate metrics
        total_cases = len(test_cases)
        accuracy = successful / total_cases if total_cases > 0 else 0
        avg_distance_error = total_distance_error / successful if successful > 0 else None
        avg_time = total_time / total_cases if total_cases > 0 else 0

        metrics = {
            'model': model,
            'total_cases': total_cases,
            'successful': successful,
            'failed': failed,
            'accuracy': accuracy,
            'avg_distance_error_km': avg_distance_error,
            'avg_time_seconds': avg_time,
            'total_time_seconds': total_time
        }

        # Print summary
        print(f"\n{'='*60}")
        print(f"RESULTS FOR {model}")
        print(f"{'='*60}")
        print(f"Accuracy: {accuracy*100:.1f}% ({successful}/{total_cases})")
        print(f"Failed: {failed}/{total_cases}")
        if avg_distance_error:
            print(f"Avg Distance Error: {avg_distance_error:.2f} km")
        print(f"Avg Time: {avg_time:.2f}s")
        print(f"Total Time: {total_time:.2f}s")

        return {
            'metrics': metrics,
            'results': results
        }

    def run_comparison(self, models: List[str] = None,
                      output_file: str = 'openrouter_comparison_results.json'):
        """
        Run comparison across multiple models

        Args:
            models: List of model names to test (None = test all)
            output_file: Path to save results
        """
        models_to_test = models or self.MODELS
        test_cases = self.create_test_cases()

        print(f"\n{'='*60}")
        print(f"OPENROUTER MODEL COMPARISON")
        print(f"{'='*60}")
        print(f"Testing {len(models_to_test)} models on {len(test_cases)} cases")
        print(f"Models: {', '.join([m.split('/')[-1] for m in models_to_test])}")

        all_results = []

        for model in models_to_test:
            try:
                result = self.test_model(model, test_cases)
                all_results.append(result)

                # Small delay between models to avoid rate limiting
                time.sleep(2)

            except Exception as e:
                print(f"Error testing {model}: {e}")
                continue

        # Create comparison summary
        summary = self._create_summary(all_results)

        # Save results
        output = {
            'test_cases': test_cases,
            'results': all_results,
            'summary': summary
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n{'='*60}")
        print(f"Results saved to: {output_file}")
        print(f"{'='*60}")

        self._print_summary(summary)

        return output

    def _create_summary(self, results: List[Dict]) -> Dict:
        """Create comparison summary table"""
        summary = {
            'models': [],
            'best_accuracy': None,
            'best_speed': None,
            'best_overall': None
        }

        for result in results:
            metrics = result['metrics']
            summary['models'].append(metrics)

        # Sort by accuracy
        sorted_by_accuracy = sorted(summary['models'], key=lambda x: x['accuracy'], reverse=True)
        summary['best_accuracy'] = sorted_by_accuracy[0]['model'] if sorted_by_accuracy else None

        # Sort by speed
        sorted_by_speed = sorted(summary['models'], key=lambda x: x['avg_time_seconds'])
        summary['best_speed'] = sorted_by_speed[0]['model'] if sorted_by_speed else None

        # Best overall (accuracy * 2 - normalized_time)
        for model in summary['models']:
            score = model['accuracy'] * 2 - (model['avg_time_seconds'] / 30)  # Normalize to ~30s
            model['overall_score'] = score

        sorted_by_overall = sorted(summary['models'], key=lambda x: x['overall_score'], reverse=True)
        summary['best_overall'] = sorted_by_overall[0]['model'] if sorted_by_overall else None

        return summary

    def _print_summary(self, summary: Dict):
        """Print comparison summary table"""
        print("\n" + "="*80)
        print("MODEL COMPARISON SUMMARY")
        print("="*80)
        print(f"{'Model':<40} {'Accuracy':>10} {'Avg Error':>12} {'Avg Time':>10}")
        print("-"*80)

        for metrics in sorted(summary['models'], key=lambda x: x['accuracy'], reverse=True):
            model_name = metrics['model'].split('/')[-1][:38]
            accuracy = f"{metrics['accuracy']*100:.1f}%"
            error = f"{metrics['avg_distance_error_km']:.1f} km" if metrics['avg_distance_error_km'] else "N/A"
            time_str = f"{metrics['avg_time_seconds']:.1f}s"

            print(f"{model_name:<40} {accuracy:>10} {error:>12} {time_str:>10}")

        print("-"*80)
        print(f"\nBest Accuracy: {summary['best_accuracy'].split('/')[-1]}")
        print(f"Best Speed: {summary['best_speed'].split('/')[-1]}")
        print(f"Best Overall: {summary['best_overall'].split('/')[-1]}")


def main():
    """Main execution"""
    # Configuration
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "your-password-here")

    if not OPENROUTER_API_KEY:
        print("Error: OPENROUTER_API_KEY environment variable not set")
        print("Set it with: export OPENROUTER_API_KEY=your-key-here")
        return

    # Initialize tester
    tester = OpenRouterModelTester(
        api_key=OPENROUTER_API_KEY,
        neo4j_uri=NEO4J_URI,
        neo4j_user=NEO4J_USER,
        neo4j_password=NEO4J_PASSWORD
    )

    try:
        # Run comparison (start with top 3 models for quick test)
        quick_test_models = [
            "qwen/qwen-2.5-72b-instruct",
            "meta-llama/llama-3.1-70b-instruct",
            "meta-llama/llama-3.1-8b-instruct",  # Fast baseline
        ]

        results = tester.run_comparison(
            models=quick_test_models,
            output_file='openrouter_test_results.json'
        )

        print("\n✓ Testing complete!")
        print(f"Review detailed results in: openrouter_test_results.json")

    finally:
        tester.close()


if __name__ == "__main__":
    main()

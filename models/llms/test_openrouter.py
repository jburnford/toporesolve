"""
Quick test script to verify OpenRouter integration works
Tests on just 5 samples from the gold standard
"""

import json
import os
import sys

# Import the disambiguation function
import importlib.util
spec = importlib.util.spec_from_file_location("openrouter_gpt_oss",
    os.path.join(os.path.dirname(__file__), "openrouter-gpt-oss.py"))
openrouter_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(openrouter_module)
disambiguate_entity_with_coords = openrouter_module.disambiguate_entity_with_coords

def test_openrouter():
    """Test OpenRouter API with a few samples"""

    # Load 5 samples from GPE gold standard
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(script_dir))
    input_file = os.path.join(repo_root, "data/gold_standards/GPE_2024_05_21T134100Z.jsonl")
    samples = []

    print("Loading test samples...")
    with open(input_file, 'r') as f:
        for i, line in enumerate(f):
            if i >= 5:  # Just take 5 samples
                break
            samples.append(json.loads(line))

    print(f"\nTesting OpenRouter with {len(samples)} samples...\n")
    print("="*60)

    results = []

    for i, data in enumerate(samples):
        entity = data['entity']
        city = data['media_dets']['location_name']
        state = data['media_dets']['state']
        expected_coords = data['lat_long']

        # Combine sentences
        combined_sentence = ". ".join(sent_obj['sent'] for sent_obj in data['context']['sents'])

        print(f"\n[{i+1}/5] Entity: {entity}")
        print(f"  Source: {city}, {state}")
        print(f"  Expected: {expected_coords}")
        print(f"  Context: {combined_sentence[:100]}...")

        try:
            result = disambiguate_entity_with_coords(
                'geopolitical (GPE)',
                entity,
                combined_sentence,
                city,
                state
            )

            predicted = (result['latitude'], result['longitude'])
            print(f"  Predicted: {predicted}")
            print(f"  Response: {result.get('response_text', 'N/A')[:100]}...")

            results.append({
                'entity': entity,
                'expected': expected_coords,
                'predicted': predicted,
                'success': True
            })

        except Exception as e:
            print(f"  ERROR: {str(e)}")
            results.append({
                'entity': entity,
                'expected': expected_coords,
                'success': False,
                'error': str(e)
            })

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    successful = sum(1 for r in results if r['success'])
    print(f"Successful: {successful}/{len(results)}")

    if successful > 0:
        print("\n✓ OpenRouter integration is working!")
        print("You can now run the full script with:")
        print("  python models/llms/openrouter-gpt-oss.py --input_file <path> --output_file <path> --entity_type 'geopolitical (GPE)'")
    else:
        print("\n✗ OpenRouter integration has issues. Check API key and errors above.")

    return results


if __name__ == "__main__":
    test_openrouter()

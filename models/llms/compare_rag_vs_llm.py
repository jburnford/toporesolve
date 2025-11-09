"""
Compare RAG vs Pure LLM disambiguation results
Uses 25-mile radius threshold for matching
"""
import json
import math
import argparse

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in miles between two lat/lon points"""
    if None in [lat1, lon1, lat2, lon2]:
        return None

    R = 3959  # Earth radius in miles

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c

def evaluate_results(results_file, gold_standard_file, threshold_miles=25):
    """Evaluate disambiguation results against gold standard"""

    # Load results
    with open(results_file, 'r') as f:
        results = json.load(f)

    # Load gold standard
    gold_standard = {}
    with open(gold_standard_file, 'r') as f:
        for line in f:
            gs = json.loads(line)
            gold_standard[gs['entity']] = gs['lat_long']

    # Evaluate
    matches = 0
    no_coords = 0
    total = 0

    distances = []

    for result in results:
        entity = result['entity']
        pred_lat = result['disambiguated_info'].get('latitude')
        pred_lon = result['disambiguated_info'].get('longitude')

        if entity not in gold_standard:
            continue

        total += 1
        gold_lat, gold_lon = gold_standard[entity]

        if pred_lat is None or pred_lon is None:
            no_coords += 1
            continue

        distance = haversine_distance(gold_lat, gold_lon, pred_lat, pred_lon)
        if distance is not None:
            distances.append(distance)
            if distance <= threshold_miles:
                matches += 1

    # Calculate metrics
    accuracy = matches / total if total > 0 else 0
    avg_distance = sum(distances) / len(distances) if distances else None

    return {
        'total': total,
        'matches': matches,
        'no_coords': no_coords,
        'accuracy': accuracy,
        'avg_distance': avg_distance,
        'distances': distances
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rag', required=True, help='RAG results JSON file')
    parser.add_argument('--llm', required=True, help='Pure LLM results JSON file')
    parser.add_argument('--gold', required=True, help='Gold standard JSONL file')

    args = parser.parse_args()

    print("=" * 70)
    print("DISAMBIGUATION COMPARISON: RAG vs Pure LLM")
    print("=" * 70)
    print()

    # Evaluate RAG
    print("RAG (Neo4j + GPT-OSS-120B):")
    rag_results = evaluate_results(args.rag, args.gold)
    print(f"  Total samples: {rag_results['total']}")
    print(f"  Matches within 25 miles: {rag_results['matches']}/{rag_results['total']}")
    print(f"  Accuracy: {rag_results['accuracy']*100:.1f}%")
    print(f"  No coordinates returned: {rag_results['no_coords']}")
    if rag_results['avg_distance']:
        print(f"  Average distance: {rag_results['avg_distance']:.1f} miles")
    print()

    # Evaluate Pure LLM
    print("Pure LLM (GPT-OSS-120B):")
    llm_results = evaluate_results(args.llm, args.gold)
    print(f"  Total samples: {llm_results['total']}")
    print(f"  Matches within 25 miles: {llm_results['matches']}/{llm_results['total']}")
    print(f"  Accuracy: {llm_results['accuracy']*100:.1f}%")
    print(f"  No coordinates returned: {llm_results['no_coords']}")
    if llm_results['avg_distance']:
        print(f"  Average distance: {llm_results['avg_distance']:.1f} miles")
    print()

    # Comparison
    print("=" * 70)
    print("COMPARISON:")
    print(f"  RAG accuracy: {rag_results['accuracy']*100:.1f}%")
    print(f"  Pure LLM accuracy: {llm_results['accuracy']*100:.1f}%")

    improvement = rag_results['accuracy'] - llm_results['accuracy']
    if improvement > 0:
        print(f"  RAG is {improvement*100:.1f} percentage points BETTER")
    elif improvement < 0:
        print(f"  RAG is {abs(improvement)*100:.1f} percentage points WORSE")
    else:
        print("  No difference")

    print()
    print("KEY INSIGHT:")
    print("  RAG advantage: Returns 'no candidates' instead of hallucinating")
    print(f"  RAG refused to answer: {rag_results['no_coords']} times")
    print(f"  Pure LLM refused to answer: {llm_results['no_coords']} times")
    print("=" * 70)

if __name__ == '__main__':
    main()

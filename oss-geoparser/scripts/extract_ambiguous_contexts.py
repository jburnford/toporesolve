"""
Extract all contexts for an ambiguous toponym to analyze with LLM
"""

import sys
import os
import json
import re
from pathlib import Path

def extract_contexts(toponym, corpus_dir, window=150):
    """
    Extract all contexts for a given toponym

    Args:
        toponym: The toponym to search for (case-insensitive)
        corpus_dir: Directory containing corpus documents
        window: Characters before and after to include in context

    Returns:
        List of context dictionaries
    """
    corpus_path = Path(corpus_dir)
    contexts = []

    # Create a regex pattern for word boundaries
    pattern = re.compile(r'\b' + re.escape(toponym) + r'\b', re.IGNORECASE)

    # Process all text files
    for doc_file in sorted(corpus_path.glob("*.txt")):
        doc_id = doc_file.stem

        with open(doc_file) as f:
            text = f.read()

        # Find all matches
        for match in pattern.finditer(text):
            start = match.start()
            end = match.end()

            # Extract context window
            context_start = max(0, start - window)
            context_end = min(len(text), end + window)

            context = text[context_start:context_end].strip()

            contexts.append({
                'document': doc_id,
                'toponym': match.group(),
                'start': start,
                'end': end,
                'context': context
            })

    return contexts


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_ambiguous_contexts.py <toponym> [corpus_dir] [output_file]")
        print("Example: python extract_ambiguous_contexts.py London")
        sys.exit(1)

    toponym = sys.argv[1]
    corpus_dir = sys.argv[2] if len(sys.argv) > 2 else "data/corpus/sample_100"
    output_file = sys.argv[3] if len(sys.argv) > 3 else f"results/{toponym.lower()}_contexts.json"

    print(f"Extracting contexts for: {toponym}")
    print(f"Corpus directory: {corpus_dir}")
    print()

    contexts = extract_contexts(toponym, corpus_dir)

    print(f"Found {len(contexts)} occurrences")
    print()

    # Show first few contexts
    for i, ctx in enumerate(contexts[:5], 1):
        print(f"{i}. Document: {ctx['document']}")
        print(f"   Context: {ctx['context']}")
        print()

    if len(contexts) > 5:
        print(f"... and {len(contexts) - 5} more")
        print()

    # Save to file
    with open(output_file, 'w') as f:
        json.dump({
            'toponym': toponym,
            'total_contexts': len(contexts),
            'contexts': contexts
        }, f, indent=2)

    print(f"Saved all contexts to: {output_file}")


if __name__ == "__main__":
    main()

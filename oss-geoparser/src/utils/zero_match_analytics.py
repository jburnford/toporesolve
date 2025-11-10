"""
Zero-Match Analytics for Human Review Workflow

Tracks toponyms that returned 0 candidates from knowledge graph.
Generates reports sorted by frequency to prioritize human review.

Human review workflow:
1. Review high-frequency zero-match toponyms
2. Decide action:
   a) Add to ambiguous_terms.txt (ungroundable)
   b) Create mapping in historical_aliases.json (variant name)
   c) Flag for database addition (missing entity)
"""

from collections import defaultdict
from typing import List, Dict, Optional
import json


class ZeroMatchTracker:
    """
    Track toponyms with zero candidates for human review

    Accumulates data across entire document processing run
    to identify patterns and prioritize review.
    """

    def __init__(self):
        """Initialize tracker"""
        self.zero_matches = defaultdict(lambda: {
            'count': 0,
            'contexts': []  # Sample contexts for review
        })

    def record_zero_match(self, toponym: str, context: Optional[str] = None):
        """
        Record a toponym that returned 0 candidates

        Args:
            toponym: Name that had no matches
            context: Sample context (stores up to 3 for review)
        """
        self.zero_matches[toponym]['count'] += 1

        # Store up to 3 sample contexts for human review
        if context and len(self.zero_matches[toponym]['contexts']) < 3:
            # Truncate long contexts
            truncated = context[:200] + "..." if len(context) > 200 else context
            self.zero_matches[toponym]['contexts'].append(truncated)

    def get_statistics(self) -> Dict:
        """
        Get statistics on zero-match toponyms

        Returns:
            Dictionary with counts and examples
        """
        return {
            'total_unique_toponyms': len(self.zero_matches),
            'total_occurrences': sum(data['count'] for data in self.zero_matches.values()),
            'toponyms': dict(self.zero_matches)
        }

    def generate_review_report(self, min_frequency: int = 1) -> List[Dict]:
        """
        Generate human review report sorted by frequency

        Args:
            min_frequency: Minimum occurrence count to include

        Returns:
            List of toponyms sorted by frequency (most common first)
        """
        # Filter by minimum frequency and sort
        filtered = [
            {
                'toponym': name,
                'frequency': data['count'],
                'contexts': data['contexts']
            }
            for name, data in self.zero_matches.items()
            if data['count'] >= min_frequency
        ]

        # Sort by frequency (descending)
        filtered.sort(key=lambda x: x['frequency'], reverse=True)

        return filtered

    def export_for_review(self, output_path: str, min_frequency: int = 5):
        """
        Export review-ready report to JSON

        Args:
            output_path: Where to save the review report
            min_frequency: Only include toponyms appearing at least N times
        """
        report = self.generate_review_report(min_frequency=min_frequency)

        output = {
            'metadata': {
                'description': 'Zero-match toponyms for human review',
                'total_unique': len(self.zero_matches),
                'total_occurrences': sum(data['count'] for data in self.zero_matches.values()),
                'min_frequency': min_frequency,
                'items_in_report': len(report)
            },
            'instructions': {
                'workflow': [
                    '1. Review each toponym starting from highest frequency',
                    '2. Check sample contexts to understand usage',
                    '3. Decide action:',
                    '   a) FILTER: Add to config/ambiguous_terms.txt (ungroundable)',
                    '   b) MAP: Add to config/historical_aliases.json (variant name)',
                    '   c) CREATE: Flag for database addition (missing entity)',
                    '4. Document decision in "action" field'
                ],
                'priority': 'High-frequency items have biggest impact on coverage'
            },
            'review_items': report
        }

        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)

        return output_path

    def get_top_n(self, n: int = 20) -> List[Dict]:
        """
        Get top N most frequent zero-match toponyms

        Args:
            n: Number of items to return

        Returns:
            List of top N items sorted by frequency
        """
        report = self.generate_review_report(min_frequency=1)
        return report[:n]

    def print_summary(self, top_n: int = 10):
        """
        Print summary of zero-match analytics

        Args:
            top_n: How many top items to show
        """
        stats = self.get_statistics()
        top_items = self.get_top_n(n=top_n)

        print("\n" + "="*80)
        print("ZERO-MATCH ANALYTICS SUMMARY")
        print("="*80)
        print(f"Total unique toponyms with zero matches: {stats['total_unique_toponyms']}")
        print(f"Total zero-match occurrences: {stats['total_occurrences']}")
        print(f"\nTop {top_n} Most Frequent Zero-Matches:")
        print("-"*80)

        for i, item in enumerate(top_items, 1):
            print(f"\n{i}. '{item['toponym']}' - {item['frequency']} occurrences")
            if item['contexts']:
                print(f"   Sample: {item['contexts'][0]}")

        print("\n" + "="*80)

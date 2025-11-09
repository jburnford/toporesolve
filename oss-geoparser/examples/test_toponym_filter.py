"""
Test the toponym filter on Saskatchewan XML data

Demonstrates filtering of ungroundable toponyms
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.toponym_filter import ToponymFilter


def test_filter():
    """Test filter on various toponym types"""

    filter = ToponymFilter(strict_mode=False)

    # Test cases: (toponym, context, expected_groundable)
    test_cases = [
        # Should PASS (groundable)
        ("London", "visited London, England", True),
        ("Point Lake", "camped at Point Lake", True),
        ("Fort Enterprise", "departed from Fort Enterprise", True),
        ("Saskatchewan", "in Saskatchewan province", True),
        ("Toronto", "traveled to Toronto", True),

        # Should FAIL (not groundable)
        ("the river", "crossed the river", False),
        ("the lake", "on the lake", False),
        ("north", "traveled north", False),
        ("the place", "at the place", False),
        ("Mr. Smith", "Mr. Smith said", False),
        ("a", "a village", False),

        # Ambiguous abbreviations (fail in strict mode)
        ("N.Y.", "from N.Y.", False),  # No context to disambiguate
        ("N.Y.", "from N.Y., New York", True),  # Context helps

        # Generic with "the"
        ("the fort", "arrived at the fort", False),
        ("Fort Garry", "arrived at Fort Garry", True),  # Specific name OK
    ]

    print("=" * 80)
    print("TOPONYM FILTER TEST")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    for toponym, context, expected in test_cases:
        is_groundable, reason = filter.is_groundable(toponym, context)

        status = "✓" if is_groundable == expected else "✗"
        if is_groundable == expected:
            passed += 1
        else:
            failed += 1

        result = "GROUNDABLE" if is_groundable else f"FILTERED ({reason.value if reason else 'unknown'})"

        print(f"{status} '{toponym:20}' → {result:40} (expected: {'OK' if expected else 'FILTER'})")

    print()
    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 80)


if __name__ == "__main__":
    test_filter()

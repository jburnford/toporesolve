"""
Ambiguity Detection for Historical Toponyms
Identifies cases that require LLM disambiguation vs simple lookup
"""

from typing import List, Dict, Tuple, Optional
from enum import Enum
import re


class AmbiguityLevel(Enum):
    """Classification of toponym ambiguity"""
    UNAMBIGUOUS = 1  # Single clear match, high confidence
    LOW_AMBIGUITY = 2  # 2-3 candidates, clear context
    MODERATE_AMBIGUITY = 3  # Multiple candidates or unclear context
    HIGH_AMBIGUITY = 4  # Many candidates + weak context
    UNKNOWN = 5  # No candidates found in knowledge graph


class AmbiguityDetector:
    """
    Detects and scores ambiguity for historical toponyms
    """

    def __init__(self, querier):
        """
        Args:
            querier: HistoricalPlaceQuerier instance for Neo4j access
        """
        self.querier = querier

        # Common ambiguous place names (from experience)
        self.known_ambiguous = {
            'Paris', 'Springfield', 'Washington', 'London', 'Manchester',
            'Cambridge', 'Oxford', 'Plymouth', 'Portland', 'Salem',
            'Richmond', 'Chester', 'Newport', 'Kingston'
        }

    def detect_ambiguity(self, toponym: str, context: str, year: str,
                        entity_type: Optional[str] = None) -> Dict:
        """
        Comprehensive ambiguity detection

        Returns:
            {
                'ambiguity_level': AmbiguityLevel,
                'ambiguity_score': float (0-1, higher = more ambiguous),
                'signals': Dict of individual signal scores,
                'recommendation': str ('llm_required', 'traditional_ok', 'lookup_only'),
                'explanation': str
            }
        """
        signals = {}

        # Signal 1: Query knowledge graph for candidates
        candidates = self.querier.find_places_by_name_and_date(toponym, year, max_results=20)
        num_candidates = len(candidates)

        signals['multiple_candidates'] = self._score_candidate_count(num_candidates)
        signals['no_candidates'] = 1.0 if num_candidates == 0 else 0.0

        # Signal 2: Geographic spread of candidates
        if num_candidates > 1:
            signals['geographic_spread'] = self._calculate_geographic_spread(candidates)
        else:
            signals['geographic_spread'] = 0.0

        # Signal 3: Known ambiguous name
        signals['known_ambiguous'] = 1.0 if toponym in self.known_ambiguous else 0.0

        # Signal 4: Context quality/length
        signals['weak_context'] = self._score_context_quality(context, toponym)

        # Signal 5: Temporal uncertainty
        signals['temporal_uncertainty'] = self._score_temporal_info(candidates, year)

        # Signal 6: Conflicting sources (Wikidata vs GeoNames)
        if num_candidates > 1:
            signals['conflicting_sources'] = self._detect_source_conflicts(candidates)
        else:
            signals['conflicting_sources'] = 0.0

        # Signal 7: OCR/spelling variants likely
        signals['ocr_artifacts'] = self._detect_ocr_artifacts(toponym, context)

        # Signal 8: Historical name changes
        signals['name_changes'] = self._detect_historical_names(candidates, toponym)

        # Calculate overall ambiguity score
        ambiguity_score = self._calculate_ambiguity_score(signals)

        # Determine ambiguity level
        ambiguity_level = self._classify_ambiguity_level(ambiguity_score, num_candidates)

        # Generate recommendation
        recommendation, explanation = self._generate_recommendation(
            ambiguity_level, ambiguity_score, num_candidates, signals
        )

        return {
            'ambiguity_level': ambiguity_level.name,
            'ambiguity_score': ambiguity_score,
            'num_candidates': num_candidates,
            'signals': signals,
            'recommendation': recommendation,
            'explanation': explanation,
            'candidates_summary': self._summarize_candidates(candidates)
        }

    def _score_candidate_count(self, count: int) -> float:
        """Score based on number of candidates (more = more ambiguous)"""
        if count == 0:
            return 0.0  # Different signal
        elif count == 1:
            return 0.0  # Unambiguous
        elif count == 2:
            return 0.3
        elif count <= 5:
            return 0.6
        else:
            return 1.0  # Highly ambiguous

    def _calculate_geographic_spread(self, candidates: List[Dict]) -> float:
        """
        Calculate geographic spread of candidates
        Returns score 0-1 (higher = more spread out = more ambiguous)
        """
        if len(candidates) < 2:
            return 0.0

        # Get coordinates
        coords = [(c['latitude'], c['longitude']) for c in candidates
                  if c.get('latitude') and c.get('longitude')]

        if len(coords) < 2:
            return 0.0

        # Calculate variance in coordinates
        lats = [c[0] for c in coords]
        lons = [c[1] for c in coords]

        lat_range = max(lats) - min(lats)
        lon_range = max(lons) - min(lons)

        # If spread across >10 degrees in either direction, highly ambiguous
        total_spread = (lat_range + lon_range) / 2

        if total_spread > 20:  # Different continents
            return 1.0
        elif total_spread > 5:  # Different countries
            return 0.7
        elif total_spread > 1:  # Different regions
            return 0.4
        else:  # Same region
            return 0.1

    def _score_context_quality(self, context: str, toponym: str) -> float:
        """
        Score context quality (weaker context = higher ambiguity)
        Returns 0-1 (higher = weaker context)
        """
        # Count words around toponym
        words = context.split()

        if len(words) < 10:
            return 1.0  # Very weak context
        elif len(words) < 30:
            return 0.6
        elif len(words) < 50:
            return 0.3
        else:
            return 0.1  # Strong context

    def _score_temporal_info(self, candidates: List[Dict], query_year: str) -> float:
        """
        Score temporal uncertainty
        Returns 0-1 (higher = more uncertain)
        """
        if not candidates:
            return 1.0

        # Check how many candidates have temporal info
        with_temporal_info = sum(1 for c in candidates
                                if c.get('name_valid_from') and
                                   c['name_valid_from'] != 'unknown')

        if with_temporal_info == 0:
            return 0.8  # No temporal info
        elif with_temporal_info < len(candidates) / 2:
            return 0.5  # Partial temporal info
        else:
            return 0.1  # Most have temporal info

    def _detect_source_conflicts(self, candidates: List[Dict]) -> float:
        """
        Detect if Wikidata and GeoNames give conflicting information
        Returns 0-1 (higher = more conflict)
        """
        wikidata_places = [c for c in candidates if c.get('source') == 'wikidata']
        geonames_places = [c for c in candidates if c.get('source') == 'geonames']

        if not wikidata_places or not geonames_places:
            return 0.0  # No conflict if only one source

        # Check if they point to similar locations
        # This is a simplified check - could be more sophisticated
        if len(wikidata_places) != len(geonames_places):
            return 0.5  # Different number of candidates

        return 0.3  # Some potential conflict

    def _detect_ocr_artifacts(self, toponym: str, context: str) -> float:
        """
        Detect likely OCR errors (common in historical texts)
        Returns 0-1 (higher = more likely OCR issues)
        """
        score = 0.0

        # Check for unusual character patterns
        if re.search(r'[0-9]', toponym):  # Numbers in place name (unusual)
            score += 0.3

        # Check for l/I confusion, O/0 confusion (common OCR errors)
        if re.search(r'[Il1]{2,}|[O0]{2,}', toponym):
            score += 0.2

        # Check for unusual capitalization
        if toponym.isupper() and len(toponym) > 3:
            score += 0.1

        # Check for special characters
        if re.search(r'[^a-zA-Z\s\-\']', toponym):
            score += 0.2

        return min(score, 1.0)

    def _detect_historical_names(self, candidates: List[Dict], toponym: str) -> float:
        """
        Detect if this is a historical name that changed
        Returns 0-1 (higher = more likely historical name)
        """
        if not candidates:
            return 0.0

        # Check if any candidate has different current name
        for candidate in candidates:
            if candidate.get('current_name') and candidate['current_name'] != toponym:
                return 0.8  # High likelihood of historical name

        return 0.0

    def _calculate_ambiguity_score(self, signals: Dict) -> float:
        """
        Combine all signals into overall ambiguity score
        Returns 0-1 (higher = more ambiguous)
        """
        # Weighted combination of signals
        weights = {
            'multiple_candidates': 0.25,
            'no_candidates': 0.20,
            'geographic_spread': 0.20,
            'known_ambiguous': 0.10,
            'weak_context': 0.10,
            'temporal_uncertainty': 0.05,
            'conflicting_sources': 0.05,
            'ocr_artifacts': 0.03,
            'name_changes': 0.02
        }

        score = sum(signals.get(key, 0) * weight
                   for key, weight in weights.items())

        return min(score, 1.0)

    def _classify_ambiguity_level(self, score: float, num_candidates: int) -> AmbiguityLevel:
        """Classify into discrete ambiguity levels"""
        if num_candidates == 0:
            return AmbiguityLevel.UNKNOWN

        if score < 0.2 and num_candidates == 1:
            return AmbiguityLevel.UNAMBIGUOUS
        elif score < 0.4:
            return AmbiguityLevel.LOW_AMBIGUITY
        elif score < 0.6:
            return AmbiguityLevel.MODERATE_AMBIGUITY
        else:
            return AmbiguityLevel.HIGH_AMBIGUITY

    def _generate_recommendation(self, level: AmbiguityLevel, score: float,
                                num_candidates: int, signals: Dict) -> Tuple[str, str]:
        """
        Generate recommendation for disambiguation strategy

        Returns:
            (recommendation, explanation)
        """
        if level == AmbiguityLevel.UNAMBIGUOUS:
            return (
                "lookup_only",
                f"Single clear candidate (score: {score:.2f}). Direct lookup sufficient."
            )

        elif level == AmbiguityLevel.LOW_AMBIGUITY:
            if signals.get('weak_context', 0) > 0.5:
                return (
                    "llm_required",
                    f"{num_candidates} candidates with weak context. LLM needed for disambiguation."
                )
            else:
                return (
                    "traditional_ok",
                    f"{num_candidates} candidates but strong context. Traditional geoparser may work."
                )

        elif level == AmbiguityLevel.MODERATE_AMBIGUITY:
            return (
                "llm_required",
                f"Moderate ambiguity (score: {score:.2f}, {num_candidates} candidates). "
                f"LLM recommended for reliable disambiguation."
            )

        elif level == AmbiguityLevel.HIGH_AMBIGUITY:
            return (
                "llm_required",
                f"High ambiguity (score: {score:.2f}, {num_candidates} candidates). "
                f"LLM essential with RAG from knowledge graph."
            )

        else:  # UNKNOWN
            return (
                "llm_required",
                f"No candidates found in knowledge graph. LLM may find alternative names or spellings."
            )

    def _summarize_candidates(self, candidates: List[Dict]) -> List[Dict]:
        """Create summary of candidates for display"""
        return [
            {
                'name': c.get('historical_name', c.get('current_name')),
                'country': c.get('country_code'),
                'coords': (c.get('latitude'), c.get('longitude')),
                'source': c.get('source')
            }
            for c in candidates[:5]  # Top 5 only
        ]

    def batch_analyze(self, toponyms: List[Dict]) -> Dict:
        """
        Analyze a batch of toponyms and provide statistics

        Args:
            toponyms: List of dicts with keys: toponym, context, year

        Returns:
            Statistics and classifications
        """
        results = []
        stats = {
            'total': len(toponyms),
            'unambiguous': 0,
            'low_ambiguity': 0,
            'moderate_ambiguity': 0,
            'high_ambiguity': 0,
            'unknown': 0,
            'llm_required': 0,
            'traditional_ok': 0,
            'lookup_only': 0
        }

        for item in toponyms:
            analysis = self.detect_ambiguity(
                toponym=item['toponym'],
                context=item['context'],
                year=item.get('year', '1800')
            )
            results.append(analysis)

            # Update stats
            level = analysis['ambiguity_level']
            stats[level.lower()] += 1

            recommendation = analysis['recommendation']
            stats[recommendation] += 1

        print("\n" + "="*60)
        print("AMBIGUITY ANALYSIS SUMMARY")
        print("="*60)
        print(f"Total toponyms: {stats['total']}")
        print(f"\nAmbiguity Levels:")
        print(f"  Unambiguous: {stats['unambiguous']} ({stats['unambiguous']/stats['total']*100:.1f}%)")
        print(f"  Low: {stats['low_ambiguity']} ({stats['low_ambiguity']/stats['total']*100:.1f}%)")
        print(f"  Moderate: {stats['moderate_ambiguity']} ({stats['moderate_ambiguity']/stats['total']*100:.1f}%)")
        print(f"  High: {stats['high_ambiguity']} ({stats['high_ambiguity']/stats['total']*100:.1f}%)")
        print(f"  Unknown: {stats['unknown']} ({stats['unknown']/stats['total']*100:.1f}%)")
        print(f"\nRecommendations:")
        print(f"  Lookup only: {stats['lookup_only']} ({stats['lookup_only']/stats['total']*100:.1f}%)")
        print(f"  Traditional OK: {stats['traditional_ok']} ({stats['traditional_ok']/stats['total']*100:.1f}%)")
        print(f"  LLM required: {stats['llm_required']} ({stats['llm_required']/stats['total']*100:.1f}%)")
        print(f"\n→ Estimated LLM calls needed: {stats['llm_required']} / {stats['total']} ({stats['llm_required']/stats['total']*100:.1f}%)")

        return {
            'results': results,
            'statistics': stats
        }


def test_ambiguity_detection():
    """Test the ambiguity detector"""
    from neo4j.query_utils import HistoricalPlaceQuerier

    querier = HistoricalPlaceQuerier(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="your-password-here"
    )

    detector = AmbiguityDetector(querier)

    test_cases = [
        {
            'toponym': 'Paris',
            'context': 'The peace conference in Paris concluded in 1919.',
            'year': '1919'
        },
        {
            'toponym': 'Constantinople',
            'context': 'Constantinople was the capital of the Ottoman Empire in 1900.',
            'year': '1900'
        },
        {
            'toponym': 'Smalltown',
            'context': 'A minor incident occurred in Smalltown in 1875.',
            'year': '1875'
        }
    ]

    print("\n" + "="*60)
    print("TESTING AMBIGUITY DETECTION")
    print("="*60)

    for test in test_cases:
        analysis = detector.detect_ambiguity(**test)

        print(f"\n{test['toponym']} ({test['year']})")
        print(f"  Ambiguity Level: {analysis['ambiguity_level']}")
        print(f"  Ambiguity Score: {analysis['ambiguity_score']:.2f}")
        print(f"  Candidates: {analysis['num_candidates']}")
        print(f"  Recommendation: {analysis['recommendation']}")
        print(f"  Explanation: {analysis['explanation']}")

    # Batch analysis
    print("\n" + "="*60)
    stats = detector.batch_analyze(test_cases)

    querier.close()


if __name__ == "__main__":
    test_ambiguity_detection()

"""
Hybrid Historical Geoparser
Combines traditional geoparsers with LLM correction for optimal cost/accuracy

Strategy:
1. Use Edinburgh Geoparser (with historical gazetteers) as first pass
2. Validate results against Neo4j knowledge graph
3. For low-confidence or failed cases, use LLM with RAG
"""

import os
import json
from typing import Dict, List, Optional, Tuple
from enum import Enum

from rag_pipeline import HistoricalGeoparserRAG


class DisambiguationStrategy(Enum):
    """Which system was used for final disambiguation"""
    TRADITIONAL_HIGH_CONFIDENCE = "traditional_high_confidence"
    TRADITIONAL_VALIDATED = "traditional_validated"
    LLM_CORRECTION = "llm_correction"
    LLM_DIRECT = "llm_direct"


class HybridHistoricalGeoparser:
    """
    Hybrid system combining traditional geoparsers with LLM-based disambiguation
    """

    def __init__(self, rag_pipeline: HistoricalGeoparserRAG,
                 use_edinburgh: bool = True,
                 confidence_threshold: float = 0.7):
        """
        Initialize hybrid geoparser

        Args:
            rag_pipeline: Pre-configured RAG pipeline with LLM and Neo4j
            use_edinburgh: Whether to use Edinburgh geoparser as first pass
            confidence_threshold: Minimum confidence to accept traditional result
        """
        self.rag_pipeline = rag_pipeline
        self.use_edinburgh = use_edinburgh
        self.confidence_threshold = confidence_threshold

        # Statistics
        self.stats = {
            'total_processed': 0,
            'traditional_accepted': 0,
            'traditional_validated': 0,
            'llm_corrections': 0,
            'llm_direct': 0,
            'failed': 0
        }

    def call_edinburgh_geoparser(self, text: str, toponym: str,
                                 year: str) -> Optional[Dict]:
        """
        Call Edinburgh Geoparser with appropriate historical gazetteer

        Args:
            text: Context text
            toponym: Place name to resolve
            year: Year for temporal context

        Returns:
            Dict with coordinates and confidence, or None if failed
        """
        # Determine which gazetteer to use based on time period
        if int(year) < 1600:
            gazetteer = "plplus"  # Pleiades+ for ancient/early modern
        elif int(year) < 1800:
            gazetteer = "deep"  # DEEP for historical England
        else:
            gazetteer = "geonames"  # GeoNames for modern period

        try:
            # This is a placeholder - you'd implement actual Edinburgh API call
            # For now, return None to force LLM usage
            # In production, you'd parse Edinburgh XML output
            return None

        except Exception as e:
            print(f"Edinburgh geoparser error: {e}")
            return None

    def validate_against_neo4j(self, toponym: str, coords: Tuple[float, float],
                               year: str) -> Tuple[bool, float]:
        """
        Validate traditional geoparser result against Neo4j knowledge graph

        Args:
            toponym: Place name
            coords: (latitude, longitude) from traditional geoparser
            year: Year for temporal context

        Returns:
            (is_valid, confidence_score)
        """
        lat, lon = coords

        # Query Neo4j for candidates
        candidates = self.rag_pipeline.query_knowledge_graph(toponym, year)

        if not candidates:
            return False, 0.0

        # Check if any candidate is close to the traditional result
        # Consider "close" as within 25km (similar to evaluation metric)
        DISTANCE_THRESHOLD_KM = 25

        for candidate in candidates:
            c_lat = candidate['latitude']
            c_lon = candidate['longitude']

            # Simple distance calculation (for more accuracy, use geopy)
            lat_diff = abs(lat - c_lat)
            lon_diff = abs(lon - c_lon)

            # Rough approximation: 1 degree ≈ 111km at equator
            distance_km = ((lat_diff ** 2 + lon_diff ** 2) ** 0.5) * 111

            if distance_km <= DISTANCE_THRESHOLD_KM:
                # Found a match in knowledge graph
                confidence = 1.0 - (distance_km / DISTANCE_THRESHOLD_KM)
                return True, confidence

        return False, 0.0

    def disambiguate(self, toponym: str, context: str, entity_type: str,
                    source_year: Optional[str] = None,
                    model: str = "qwen/qwen-2.5-72b-instruct") -> Dict:
        """
        Main disambiguation method using hybrid approach

        Args:
            toponym: Place name to disambiguate
            context: Text context containing the toponym
            entity_type: Entity type (GPE, LOC, FAC)
            source_year: Optional year (will be extracted if not provided)
            model: LLM model to use for corrections/fallback

        Returns:
            Disambiguation result with strategy used
        """
        self.stats['total_processed'] += 1

        # Extract year if not provided
        year = source_year or self.rag_pipeline.extract_date_from_context(context)
        if not year:
            year = "1800"

        strategy = None
        latitude = None
        longitude = None
        explanation = ""

        # Step 1: Try traditional geoparser (Edinburgh)
        if self.use_edinburgh:
            trad_result = self.call_edinburgh_geoparser(context, toponym, year)

            if trad_result:
                coords = (trad_result['latitude'], trad_result['longitude'])
                confidence = trad_result.get('confidence', 0.5)

                # Step 2: Validate against Neo4j
                is_valid, validation_confidence = self.validate_against_neo4j(
                    toponym, coords, year
                )

                # Accept if high confidence OR validated
                if confidence >= self.confidence_threshold and is_valid:
                    latitude, longitude = coords
                    strategy = DisambiguationStrategy.TRADITIONAL_HIGH_CONFIDENCE
                    explanation = f"Edinburgh geoparser result (confidence: {confidence:.2f}), validated against historical records"
                    self.stats['traditional_accepted'] += 1

                elif is_valid and validation_confidence > 0.5:
                    latitude, longitude = coords
                    strategy = DisambiguationStrategy.TRADITIONAL_VALIDATED
                    explanation = f"Edinburgh result validated against Neo4j (validation confidence: {validation_confidence:.2f})"
                    self.stats['traditional_validated'] += 1

        # Step 3: Use LLM if traditional failed or low confidence
        if strategy is None:
            llm_result = self.rag_pipeline.disambiguate(
                toponym=toponym,
                context=context,
                entity_type=entity_type,
                source_year=year,
                model=model
            )

            latitude = llm_result['latitude']
            longitude = llm_result['longitude']
            explanation = llm_result['explanation']

            if trad_result:
                strategy = DisambiguationStrategy.LLM_CORRECTION
                explanation = f"LLM correction of traditional result. {explanation}"
                self.stats['llm_corrections'] += 1
            else:
                strategy = DisambiguationStrategy.LLM_DIRECT
                self.stats['llm_direct'] += 1

        # Track failures
        if latitude is None or longitude is None:
            self.stats['failed'] += 1

        return {
            'toponym': toponym,
            'latitude': latitude,
            'longitude': longitude,
            'year': year,
            'entity_type': entity_type,
            'strategy': strategy.value if strategy else 'failed',
            'explanation': explanation,
            'model': model
        }

    def batch_process(self, toponyms: List[Dict], model: str,
                     output_file: str = None) -> List[Dict]:
        """
        Batch process toponyms with hybrid approach

        Args:
            toponyms: List of dicts with keys: toponym, context, entity_type, year
            model: LLM model to use
            output_file: Optional path to save results

        Returns:
            List of results
        """
        results = []

        for i, item in enumerate(toponyms):
            print(f"\nProcessing {i+1}/{len(toponyms)}: {item['toponym']}")

            result = self.disambiguate(
                toponym=item['toponym'],
                context=item['context'],
                entity_type=item['entity_type'],
                source_year=item.get('year'),
                model=model
            )

            print(f"  Strategy: {result['strategy']}")
            results.append(result)

        # Print statistics
        print("\n" + "="*60)
        print("HYBRID PIPELINE STATISTICS")
        print("="*60)
        total = self.stats['total_processed']
        print(f"Total processed: {total}")
        print(f"Traditional accepted: {self.stats['traditional_accepted']} ({self.stats['traditional_accepted']/total*100:.1f}%)")
        print(f"Traditional validated: {self.stats['traditional_validated']} ({self.stats['traditional_validated']/total*100:.1f}%)")
        print(f"LLM corrections: {self.stats['llm_corrections']} ({self.stats['llm_corrections']/total*100:.1f}%)")
        print(f"LLM direct: {self.stats['llm_direct']} ({self.stats['llm_direct']/total*100:.1f}%)")
        print(f"Failed: {self.stats['failed']} ({self.stats['failed']/total*100:.1f}%)")

        # Calculate cost savings
        llm_calls = self.stats['llm_corrections'] + self.stats['llm_direct']
        saved_calls = total - llm_calls
        print(f"\nLLM calls saved: {saved_calls} ({saved_calls/total*100:.1f}%)")

        # Save results
        if output_file:
            output = {
                'results': results,
                'statistics': self.stats
            }
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            print(f"\nResults saved to {output_file}")

        return results

    def get_statistics(self) -> Dict:
        """Get processing statistics"""
        return self.stats.copy()


def compare_strategies():
    """
    Compare pure LLM vs hybrid approach on test dataset
    """
    from openai import OpenAI

    # Initialize
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY")
    )

    rag = HistoricalGeoparserRAG(
        llm_client=client,
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="your-password-here"
    )

    hybrid = HybridHistoricalGeoparser(
        rag_pipeline=rag,
        use_edinburgh=True,
        confidence_threshold=0.7
    )

    # Test cases
    test_cases = [
        {
            'toponym': 'Constantinople',
            'context': 'The Ottoman capital Constantinople faced unrest in 1900.',
            'entity_type': 'GPE',
            'year': '1900'
        },
        {
            'toponym': 'Verdun',
            'context': 'The battle near Verdun in 1916 claimed many lives.',
            'entity_type': 'GPE',
            'year': '1916'
        },
        {
            'toponym': 'Leningrad',
            'context': 'Leningrad endured a brutal siege in 1942.',
            'entity_type': 'GPE',
            'year': '1942'
        }
    ]

    print("="*60)
    print("COMPARING PURE LLM vs HYBRID APPROACH")
    print("="*60)

    # Process with hybrid
    results = hybrid.batch_process(test_cases, model="qwen/qwen-2.5-72b-instruct")

    # Display results
    for result in results:
        print(f"\n{result['toponym']} ({result['year']})")
        print(f"  Coordinates: ({result['latitude']}, {result['longitude']})")
        print(f"  Strategy: {result['strategy']}")
        print(f"  Explanation: {result['explanation'][:100]}...")

    rag.close()


if __name__ == "__main__":
    compare_strategies()

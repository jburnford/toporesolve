"""
Multi-Context RAG Disambiguator

Builds on proven RAG v3 foundation with multi-context awareness:
- Uses context clustering to detect multiple referents
- Presents multiple diverse contexts to LLM
- Includes co-occurrence network information
- Full provenance tracking and explainability
"""

import json
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import sys
import os

# Import from existing modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from parsers.xml_parser import LocationMention, LocationContext
from clustering.context_clusterer import ContextClusterer, ContextCluster


@dataclass
class DisambiguationResult:
    """Result of disambiguation with full provenance"""
    toponym: str
    selected_candidate: Optional[Dict]
    confidence: str  # 'high', 'medium', 'low'
    reasoning: str
    clusters_detected: int
    has_multiple_referents: bool
    all_candidates: List[Dict]
    contexts_used: List[str]
    nearby_locations: List[str]
    source_location: Optional[Dict] = None


class MultiContextDisambiguator:
    """
    Enhanced RAG disambiguator with multi-context support

    Key improvements over basic RAG:
    1. Context clustering to detect multiple referents
    2. Multiple context examples in LLM prompt
    3. Co-occurrence network awareness
    4. Geographic coherence reasoning
    5. Full explainability and provenance
    """

    def __init__(
        self,
        neo4j_interface,
        llm_client,
        context_clusterer: Optional[ContextClusterer] = None,
        model: str = "openai/gpt-oss-120b",
        max_contexts_per_cluster: int = 3,
        max_candidates: int = 10
    ):
        """
        Args:
            neo4j_interface: Neo4j knowledge graph interface
            llm_client: OpenRouter LLM client
            context_clusterer: Optional custom clusterer (default: standard settings)
            model: LLM model to use
            max_contexts_per_cluster: Max contexts to show LLM per cluster
            max_candidates: Max candidates to retrieve from Neo4j
        """
        self.neo4j = neo4j_interface
        self.llm_client = llm_client
        self.clusterer = context_clusterer or ContextClusterer(
            similarity_threshold=0.3,
            min_cluster_size=1
        )
        self.model = model
        self.max_contexts_per_cluster = max_contexts_per_cluster
        self.max_candidates = max_candidates

        self.logger = logging.getLogger(__name__)

    def disambiguate(
        self,
        mention: LocationMention,
        source_location: Optional[Dict] = None,
        cluster_id: Optional[int] = None
    ) -> DisambiguationResult:
        """
        Disambiguate a location mention using multi-context RAG

        Args:
            mention: LocationMention with all contexts
            source_location: Optional geographic source (e.g., newspaper location)
            cluster_id: If provided, disambiguate specific cluster only

        Returns:
            DisambiguationResult with selected candidate and provenance
        """
        self.logger.info(f"Disambiguating '{mention.name}' ({mention.mention_count} mentions)")

        # Step 1: Cluster contexts to detect multiple referents
        clusters = self.clusterer.cluster_contexts(mention)
        has_multiple, _ = self.clusterer.detect_multiple_referents(mention)

        self.logger.info(f"Detected {len(clusters)} clusters (multiple referents: {has_multiple})")

        # Step 2: Select which cluster to disambiguate
        if cluster_id is not None and cluster_id < len(clusters):
            target_cluster = clusters[cluster_id]
        else:
            # Use largest cluster (most supported interpretation)
            target_cluster = clusters[0] if clusters else None

        if not target_cluster:
            return DisambiguationResult(
                toponym=mention.name,
                selected_candidate=None,
                confidence='low',
                reasoning="No valid contexts found",
                clusters_detected=0,
                has_multiple_referents=False,
                all_candidates=[],
                contexts_used=[],
                nearby_locations=[]
            )

        # Step 3: Select representative contexts from cluster
        representative_contexts = self.clusterer.select_representative_contexts(
            target_cluster,
            max_contexts=self.max_contexts_per_cluster
        )

        self.logger.info(f"Using {len(representative_contexts)} representative contexts")

        # Step 4: Retrieve candidates from Neo4j
        candidates = self.neo4j.get_candidates(
            mention.name,
            limit=self.max_candidates
        )

        self.logger.info(f"Retrieved {len(candidates)} candidates from Neo4j")

        if not candidates:
            # Track zero-match for analytics (if tracker enabled)
            if hasattr(self, 'zero_match_tracker') and self.zero_match_tracker:
                sample_context = representative_contexts[0].text if representative_contexts else None
                self.zero_match_tracker.record_zero_match(mention.name, context=sample_context)

            return DisambiguationResult(
                toponym=mention.name,
                selected_candidate=None,
                confidence='low',
                reasoning="No candidates found in knowledge graph",
                clusters_detected=len(clusters),
                has_multiple_referents=has_multiple,
                all_candidates=[],
                contexts_used=[ctx.text for ctx in representative_contexts],
                nearby_locations=list(target_cluster.nearby_locations)
            )

        # Step 5: Use LLM to select best candidate with multi-context reasoning
        selected, reasoning = self._disambiguate_with_llm(
            toponym=mention.name,
            contexts=representative_contexts,
            candidates=candidates,
            nearby_locations=list(target_cluster.nearby_locations),
            source_location=source_location,
            cluster_confidence=target_cluster.confidence
        )

        # Step 6: Determine overall confidence
        confidence = self._calculate_confidence(
            cluster_confidence=target_cluster.confidence,
            num_candidates=len(candidates),
            num_contexts=len(representative_contexts),
            has_multiple_referents=has_multiple
        )

        return DisambiguationResult(
            toponym=mention.name,
            selected_candidate=selected,
            confidence=confidence,
            reasoning=reasoning,
            clusters_detected=len(clusters),
            has_multiple_referents=has_multiple,
            all_candidates=candidates,
            contexts_used=[ctx.text for ctx in representative_contexts],
            nearby_locations=list(target_cluster.nearby_locations),
            source_location=source_location
        )

    def _disambiguate_with_llm(
        self,
        toponym: str,
        contexts: List[LocationContext],
        candidates: List[Dict],
        nearby_locations: List[str],
        source_location: Optional[Dict],
        cluster_confidence: str
    ) -> Tuple[Optional[Dict], str]:
        """
        Use LLM to select best candidate from multi-context evidence

        Returns:
            (selected_candidate, reasoning)
        """
        # Build multi-context prompt
        prompt = self._build_multi_context_prompt(
            toponym=toponym,
            contexts=contexts,
            candidates=candidates,
            nearby_locations=nearby_locations,
            source_location=source_location,
            cluster_confidence=cluster_confidence
        )

        # Call LLM with retry logic (from RAG v3)
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert historical geographer specializing in toponym disambiguation."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.1
                )

                response_text = response.choices[0].message.content.strip()

                # Log full LLM response for debugging/analysis
                self.logger.info(f"LLM Response for '{toponym}':")
                self.logger.info(f"  Raw response: {response_text[:500]}..." if len(response_text) > 500 else f"  Raw response: {response_text}")

                # Extract JSON from response
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()

                llm_decision = json.loads(response_text)

                # Log parsed decision
                self.logger.info(f"  Parsed decision: selected_id={llm_decision.get('selected_id')}, confidence={llm_decision.get('confidence', 'N/A')}")

                # Find selected candidate
                selected_id = llm_decision.get('selected_id')
                reasoning = llm_decision.get('reasoning', 'No reasoning provided')
                llm_confidence = llm_decision.get('confidence', 'medium').lower()

                if selected_id is None:
                    self.logger.info(f"  Decision: No candidate selected")
                    return (None, reasoning)

                # PRECISION-FIRST: Reject low-confidence selections
                # Better to return null than risk false positive
                if llm_confidence == 'low':
                    self.logger.warning(f"  Decision: Rejecting low-confidence selection for precision")
                    return (None, f"Low confidence: {reasoning}")

                selected = next((c for c in candidates if c.get('id') == selected_id), None)
                if selected:
                    self.logger.info(f"  Decision: Selected '{selected.get('title')}' ({selected.get('lat')}, {selected.get('lon')})")
                return (selected, reasoning)

            except json.JSONDecodeError as e:
                self.logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    # Retry with more explicit formatting instruction
                    prompt = prompt.replace(
                        "Return ONLY the JSON",
                        "Return ONLY valid JSON with no markdown formatting, no backticks, no explanation"
                    )
                    continue
                else:
                    self.logger.error(f"Failed to parse LLM response after {max_retries} attempts")
                    return (None, f"LLM response parsing failed: {str(e)}")
            except Exception as e:
                self.logger.error(f"LLM error: {e}")
                return (None, f"LLM error: {str(e)}")

        return (None, "Failed to get valid LLM response")

    def _build_multi_context_prompt(
        self,
        toponym: str,
        contexts: List[LocationContext],
        candidates: List[Dict],
        nearby_locations: List[str],
        source_location: Optional[Dict],
        cluster_confidence: str
    ) -> str:
        """
        Build enhanced prompt with multiple contexts and co-occurrence info
        """
        # Source location context
        source_context = ""
        if source_location and source_location.get('city') and source_location.get('state'):
            source_context = f"""
SOURCE LOCATION: This place name appears in media from {source_location['city']}, {source_location['state']}.
Consider geographic proximity to the source location when selecting among candidates.
"""

        # Multiple contexts section
        contexts_section = "CONTEXTS (multiple uses in document):\n\n"
        for i, ctx in enumerate(contexts, 1):
            contexts_section += f"{i}. {ctx.text}\n\n"

        # Nearby locations (co-occurrence network)
        nearby_section = ""
        if nearby_locations:
            nearby_section = f"""
NEARBY LOCATIONS (mentioned in same contexts):
{', '.join(nearby_locations[:15])}

These co-occurring locations suggest the geographic region being discussed.
"""

        # Cluster confidence
        confidence_note = ""
        if cluster_confidence == 'high':
            confidence_note = "Note: All contexts show strong geographic coherence (likely single referent)."
        elif cluster_confidence == 'medium':
            confidence_note = "Note: Moderate geographic coherence detected in contexts."
        else:
            confidence_note = "Note: Low geographic coherence - contexts may refer to different places with same name."

        # Candidates section with explicit feature type labeling
        candidates_section = "CANDIDATE LOCATIONS:\n\n"
        for i, cand in enumerate(candidates, 1):
            candidates_section += f"ID: {cand.get('id', f'cand_{i}')}\n"
            candidates_section += f"Name: {cand.get('title', 'Unknown')}\n"

            # Make feature type very explicit to avoid state/city confusion
            if cand.get('feature_class'):
                feature_label = self._explain_feature_type(cand['feature_class'], cand.get('feature_code'))
                candidates_section += f"**TYPE: {feature_label}**\n"

            candidates_section += f"Location: {cand.get('admin1', 'N/A')}, {cand.get('country', 'N/A')}\n"

            if cand.get('lat') and cand.get('lon'):
                candidates_section += f"Coordinates: {cand['lat']}, {cand['lon']}\n"

            if cand.get('population'):
                candidates_section += f"Population: {cand['population']:,}\n"

            candidates_section += "\n"

        # Full prompt
        prompt = f"""You are disambiguating the place name "{toponym}" mentioned in a historical document.

{source_context}
{contexts_section}
{nearby_section}
{confidence_note}

{candidates_section}

CRITICAL DISAMBIGUATION RULES (PRECISION-FIRST APPROACH):

⚠️ **PRIORITY: AVOID FALSE POSITIVES** ⚠️
False positives (wrong locations) are worse than false negatives (no answer).
When in doubt, return null rather than guess incorrectly.

1. **HIERARCHICAL LOCATION PARSING**:
   - If context says "in [City], [State]" → SELECT THE CITY, not the state
   - If context says "in [City], [Country]" → SELECT THE CITY, not the country
   - Examples:
     ✓ "Seattle, Washington" → Select Seattle (CITY/TOWN), NOT Washington (STATE)
     ✓ "Charleston, West Virginia" → Select Charleston (CITY), NOT West Virginia (STATE)
     ✗ "native of Pennsylvania" → State (STATE) is appropriate here (no specific city)

2. **FEATURE TYPE PRIORITY**:
   - PPL/PPLA (CITY/TOWN) is MORE SPECIFIC than ADM1 (STATE) or PCLI (COUNTRY)
   - When context implies a specific location, prefer more specific types:
     - CITY/TOWN > COUNTY > STATE > COUNTRY
   - Only choose broader types when context genuinely refers to the whole region

3. **AVOID STATE/COUNTRY CENTROIDS**:
   - STATE CENTROID PROBLEM: "Seattle, Washington" should NOT select Washington state
   - INTERNATIONAL CENTROID PROBLEM: "Concert in Chile" → likely Santiago, not Chile centroid
   - RULE: If context mentions an EVENT (concert, conference, meeting) in a COUNTRY →
     prefer the CAPITAL CITY over country centroid, OR return null if no capital in candidates

4. **GEOGRAPHIC COHERENCE REQUIREMENT**:
   - Use nearby locations to VALIDATE your selection, not just inform it
   - If nearby locations conflict with your selection → return null
   - Example: If selecting "London, UK" but all nearby locations are Canadian → return null

5. **CONFIDENCE THRESHOLD**:
   - Only select a candidate if you have STRONG evidence from context
   - Weak signals (vague context, no nearby locations, ambiguous references) → return null
   - Better to miss an answer than to be wrong

TASK: Select the most likely candidate with HIGH CONFIDENCE:
1. Check if context mentions city + state/country → select city (NOT state/country)
2. For events in countries → prefer capital cities if available, else return null
3. VALIDATE geographic coherence with nearby locations (must match!)
4. Consider proximity to source location (if provided)
5. Ensure feature type matches context specificity
6. **If any doubt exists → return null**

Return ONLY a JSON object with:
{{
  "selected_id": <candidate_id or null>,
  "confidence": "<high/medium/low>",
  "reasoning": "<explanation including: which rule applied, why this is the correct choice, why you're confident>"
}}
"""

        return prompt

    def _explain_feature_type(self, feature_class: str, feature_code: Optional[str] = None) -> str:
        """
        Make feature types explicit to avoid state/city confusion

        Args:
            feature_class: GeoNames feature class (P, A, L, etc.)
            feature_code: Optional feature code for more specificity

        Returns:
            Human-readable feature type description
        """
        # Primary mappings
        if feature_class == 'P':
            if feature_code in ['PPL', 'PPLA', 'PPLA2', 'PPLA3', 'PPLA4']:
                return 'CITY/TOWN (populated place)'
            elif feature_code == 'PPLC':
                return 'CAPITAL CITY (national capital)'
            else:
                return 'POPULATED PLACE (city/town/village)'

        elif feature_class == 'A':
            if feature_code == 'ADM1':
                return 'STATE/PROVINCE (first-level administrative division)'
            elif feature_code == 'ADM2':
                return 'COUNTY/DISTRICT (second-level administrative division)'
            elif feature_code == 'PCLI':
                return 'COUNTRY (independent political entity)'
            elif feature_code == 'ADMD':
                return 'ADMINISTRATIVE DIVISION'
            else:
                return 'ADMINISTRATIVE AREA'

        elif feature_class == 'H':
            return 'WATER FEATURE (river, lake, ocean, etc.)'

        elif feature_class == 'T':
            return 'TERRAIN FEATURE (mountain, valley, etc.)'

        elif feature_class == 'L':
            return 'LANDSCAPE/REGION (park, forest, etc.)'

        elif feature_class == 'S':
            return 'STRUCTURE/FACILITY (building, monument, etc.)'

        else:
            return f'{feature_class} (see GeoNames classification)'

    def _calculate_confidence(
        self,
        cluster_confidence: str,
        num_candidates: int,
        num_contexts: int,
        has_multiple_referents: bool
    ) -> str:
        """
        Calculate overall confidence in disambiguation
        """
        # Start with cluster confidence
        if cluster_confidence == 'high' and not has_multiple_referents and num_candidates <= 5:
            return 'high'
        elif cluster_confidence == 'low' or has_multiple_referents or num_candidates > 20:
            return 'low'
        else:
            return 'medium'

    def disambiguate_all_clusters(
        self,
        mention: LocationMention,
        source_location: Optional[Dict] = None
    ) -> List[DisambiguationResult]:
        """
        Disambiguate all detected clusters (for multi-referent cases)

        Returns list of DisambiguationResult, one per cluster
        """
        clusters = self.clusterer.cluster_contexts(mention)
        has_multiple, _ = self.clusterer.detect_multiple_referents(mention)

        if not has_multiple or len(clusters) == 1:
            # Single referent - just return one result
            return [self.disambiguate(mention, source_location)]

        # Multiple referents - disambiguate each cluster
        results = []
        for i, cluster in enumerate(clusters):
            self.logger.info(f"Disambiguating cluster {i+1}/{len(clusters)} ({cluster.support} contexts)")
            result = self.disambiguate(mention, source_location, cluster_id=i)
            results.append(result)

        return results

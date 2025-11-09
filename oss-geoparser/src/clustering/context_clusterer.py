"""
Context clustering for intelligent context selection

Groups contexts by geographic coherence to:
1. Detect multiple referents (London ON vs London UK)
2. Select maximally informative contexts
3. Build co-occurrence networks
"""

from typing import List, Dict, Tuple
from dataclasses import dataclass
import sys
import os

# Import parser types
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from parsers.xml_parser import LocationContext, LocationMention


@dataclass
class ContextCluster:
    """A cluster of contexts referring to the same geographic location"""
    contexts: List[LocationContext]
    nearby_locations: set  # Union of all nearby locations in cluster
    support: int  # Number of contexts supporting this interpretation
    confidence: str  # 'high', 'medium', 'low'


class ContextClusterer:
    """
    Cluster contexts by geographic coherence

    Uses nearby location co-occurrence to group contexts that
    likely refer to the same place.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.3,
        min_cluster_size: int = 1
    ):
        """
        Args:
            similarity_threshold: Minimum Jaccard similarity to group contexts
            min_cluster_size: Minimum contexts to form a cluster
        """
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size

    def cluster_contexts(
        self,
        mention: LocationMention
    ) -> List[ContextCluster]:
        """
        Cluster contexts by geographic coherence

        Returns:
            List of ContextCluster objects, sorted by support (largest first)
        """
        if not mention.contexts:
            return []

        if len(mention.contexts) == 1:
            # Only one context - no clustering needed
            return [ContextCluster(
                contexts=mention.contexts,
                nearby_locations=set(mention.contexts[0].nearby_locations),
                support=1,
                confidence='high'
            )]

        # Agglomerative clustering based on nearby location similarity
        clusters = []

        for context in mention.contexts:
            nearby_set = set(context.nearby_locations)

            # Try to add to existing cluster
            added = False
            best_cluster = None
            best_similarity = 0

            for cluster in clusters:
                similarity = self._cluster_similarity(nearby_set, cluster.nearby_locations)

                if similarity >= self.similarity_threshold and similarity > best_similarity:
                    best_similarity = similarity
                    best_cluster = cluster

            if best_cluster is not None:
                # Add to best matching cluster
                best_cluster.contexts.append(context)
                best_cluster.nearby_locations.update(nearby_set)
                best_cluster.support += 1
                added = True

            if not added:
                # Create new cluster
                clusters.append(ContextCluster(
                    contexts=[context],
                    nearby_locations=nearby_set,
                    support=1,
                    confidence='low'  # Will be updated
                ))

        # Sort clusters by support (largest first)
        clusters.sort(key=lambda c: c.support, reverse=True)

        # Assign confidence levels
        total_contexts = len(mention.contexts)
        for cluster in clusters:
            proportion = cluster.support / total_contexts

            if proportion >= 0.6:
                cluster.confidence = 'high'
            elif proportion >= 0.3:
                cluster.confidence = 'medium'
            else:
                cluster.confidence = 'low'

        return clusters

    def select_representative_contexts(
        self,
        cluster: ContextCluster,
        max_contexts: int = 3
    ) -> List[LocationContext]:
        """
        Select most informative contexts from a cluster

        Selection criteria:
        1. Most nearby locations mentioned (most geographic information)
        2. Longest text (more detail)
        3. Diverse positions in document
        """
        if len(cluster.contexts) <= max_contexts:
            return cluster.contexts

        # Score each context
        scored_contexts = []
        for ctx in cluster.contexts:
            score = self._context_informativeness_score(ctx)
            scored_contexts.append((score, ctx))

        # Sort by score and take top N
        scored_contexts.sort(reverse=True, key=lambda x: x[0])

        # Also ensure diversity in document position
        selected = []
        used_positions = set()

        for score, ctx in scored_contexts:
            if len(selected) >= max_contexts:
                break

            # Check if position is significantly different from used positions
            position_bucket = round(ctx.position_in_doc * 10)  # 10 buckets

            if position_bucket not in used_positions or len(selected) < max_contexts // 2:
                selected.append(ctx)
                used_positions.add(position_bucket)

        # If we still need more, add highest scoring regardless of position
        for score, ctx in scored_contexts:
            if len(selected) >= max_contexts:
                break
            if ctx not in selected:
                selected.append(ctx)

        return selected[:max_contexts]

    def detect_multiple_referents(
        self,
        mention: LocationMention
    ) -> Tuple[bool, List[ContextCluster]]:
        """
        Detect if location name refers to multiple places in document

        Returns:
            (has_multiple_referents, clusters)
        """
        clusters = self.cluster_contexts(mention)

        # Multiple referents if:
        # 1. More than one cluster
        # 2. Second cluster has reasonable support (>20% of mentions)
        if len(clusters) < 2:
            return (False, clusters)

        total_contexts = sum(c.support for c in clusters)
        second_cluster_proportion = clusters[1].support / total_contexts

        has_multiple = second_cluster_proportion >= 0.2

        return (has_multiple, clusters)

    def _cluster_similarity(self, set1: set, set2: set) -> float:
        """
        Calculate similarity between a set and a cluster's nearby locations

        Uses Jaccard similarity
        """
        if not set1 and not set2:
            return 1.0
        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def _context_informativeness_score(self, context: LocationContext) -> float:
        """
        Score context by informativeness

        Factors:
        - Number of nearby locations mentioned
        - Length of text
        - Specificity (dates, numbers, proper nouns)
        """
        score = 0.0

        # Nearby locations (most important)
        score += len(context.nearby_locations) * 2.0

        # Text length (normalized)
        score += min(len(context.text) / 500.0, 1.0)

        # Count of numbers (dates, coordinates, etc.)
        import re
        numbers = re.findall(r'\b\d{2,4}\b', context.text)
        score += len(numbers) * 0.5

        # Count of capitalized words (proper nouns, place names)
        cap_words = re.findall(r'\b[A-Z][a-z]+\b', context.text)
        score += min(len(cap_words) / 10.0, 1.0)

        return score

    def build_cooccurrence_network(
        self,
        mentions: List[LocationMention]
    ) -> Dict[str, Dict[str, int]]:
        """
        Build co-occurrence network of locations

        Returns:
            Dict mapping location -> {nearby_location: count}
        """
        network = {}

        for mention in mentions:
            if mention.name not in network:
                network[mention.name] = {}

            for context in mention.contexts:
                for nearby in context.nearby_locations:
                    if nearby not in network[mention.name]:
                        network[mention.name][nearby] = 0
                    network[mention.name][nearby] += 1

        return network

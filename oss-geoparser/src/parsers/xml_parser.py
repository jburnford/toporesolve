"""
XML Parser for Saskatchewan historical document location data

Parses NER output XML files with location mentions and contexts.
Extracts nearby locations for co-occurrence analysis.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from dataclasses import dataclass
import re


@dataclass
class LocationContext:
    """Single context where a location is mentioned"""
    text: str
    nearby_locations: List[str]
    position_in_doc: float  # 0.0 to 1.0


@dataclass
class LocationMention:
    """A location mentioned in a document with all its contexts"""
    name: str
    mention_count: int
    contexts: List[LocationContext]
    document_id: str
    all_doc_locations: List[str]  # All locations in the document


class SaskatchewanXMLParser:
    """
    Parse Saskatchewan historical document XML files

    Input format:
    <document id="P000992" source_file="..." location_count="11">
      <locations>
        <location name="London" mention_count="5">
          <context>...text...</context>
          <context>...text...</context>
        </location>
      </locations>
    </document>
    """

    def __init__(self, extract_nearby: bool = True, context_window: int = 100):
        """
        Args:
            extract_nearby: Whether to extract nearby location mentions from context
            context_window: Characters around location mention to search for nearby places
        """
        self.extract_nearby = extract_nearby
        self.context_window = context_window

    def parse_file(self, xml_path: str) -> List[LocationMention]:
        """
        Parse XML file and extract location mentions with contexts

        Returns:
            List of LocationMention objects with context clustering ready
        """
        tree = ET.parse(xml_path)
        root = tree.getroot()

        document_id = root.get('id', 'unknown')

        # First pass: get all location names in document
        all_locations = []
        locations_elem = root.find('locations')
        if locations_elem is not None:
            for loc in locations_elem.findall('location'):
                all_locations.append(loc.get('name'))

        # Second pass: build LocationMention objects with nearby analysis
        mentions = []
        if locations_elem is not None:
            total_contexts = sum(len(loc.findall('context'))
                               for loc in locations_elem.findall('location'))

            for loc in locations_elem.findall('location'):
                name = loc.get('name')
                mention_count = int(loc.get('mention_count', 0))

                contexts = []
                context_elements = loc.findall('context')

                for idx, ctx in enumerate(context_elements):
                    text = ctx.text or ""

                    # Calculate position in document (0.0 to 1.0)
                    position = idx / len(context_elements) if context_elements else 0.5

                    # Extract nearby locations from context
                    nearby = self._extract_nearby_locations(
                        text, name, all_locations
                    ) if self.extract_nearby else []

                    contexts.append(LocationContext(
                        text=text,
                        nearby_locations=nearby,
                        position_in_doc=position
                    ))

                mentions.append(LocationMention(
                    name=name,
                    mention_count=mention_count,
                    contexts=contexts,
                    document_id=document_id,
                    all_doc_locations=all_locations
                ))

        return mentions

    def _extract_nearby_locations(
        self,
        context: str,
        target_location: str,
        all_doc_locations: List[str]
    ) -> List[str]:
        """
        Extract other location names mentioned near the target location

        Uses simple string matching to find other known locations
        in the context around the target.
        """
        nearby = []

        # Find position of target location in context
        target_pos = context.lower().find(target_location.lower())
        if target_pos == -1:
            # Target not found, search entire context
            search_text = context
        else:
            # Search within window around target
            start = max(0, target_pos - self.context_window)
            end = min(len(context), target_pos + len(target_location) + self.context_window)
            search_text = context[start:end]

        # Find other locations in search window
        for loc in all_doc_locations:
            if loc == target_location:
                continue  # Skip self

            # Case-insensitive match
            if loc.lower() in search_text.lower():
                nearby.append(loc)

        return nearby

    def parse_directory(self, dir_path: str, pattern: str = "*.locations.xml") -> Dict[str, List[LocationMention]]:
        """
        Parse all XML files in a directory

        Returns:
            Dict mapping document_id to list of LocationMentions
        """
        import glob
        import os

        results = {}
        files = glob.glob(os.path.join(dir_path, pattern))

        for xml_file in files:
            mentions = self.parse_file(xml_file)
            if mentions:
                doc_id = mentions[0].document_id
                results[doc_id] = mentions

        return results

    def get_multi_referent_candidates(
        self,
        mention: LocationMention,
        similarity_threshold: float = 0.3
    ) -> List[List[LocationContext]]:
        """
        Detect if location name likely refers to multiple places in document

        Clusters contexts by nearby_locations similarity.
        Returns list of context clusters.

        Args:
            mention: The location mention to analyze
            similarity_threshold: Minimum Jaccard similarity to group contexts

        Returns:
            List of context clusters (each cluster is a list of contexts)
        """
        if len(mention.contexts) < 2:
            return [mention.contexts]  # Only one context, can't have multiple referents

        # Use simple agglomerative clustering based on nearby locations
        clusters = []

        for context in mention.contexts:
            # Try to add to existing cluster
            added = False
            for cluster in clusters:
                # Calculate similarity with cluster (avg of all contexts in cluster)
                similarities = []
                for cluster_ctx in cluster:
                    sim = self._jaccard_similarity(
                        set(context.nearby_locations),
                        set(cluster_ctx.nearby_locations)
                    )
                    similarities.append(sim)

                avg_sim = sum(similarities) / len(similarities) if similarities else 0

                if avg_sim >= similarity_threshold:
                    cluster.append(context)
                    added = True
                    break

            if not added:
                # Create new cluster
                clusters.append([context])

        return clusters

    def _jaccard_similarity(self, set1: set, set2: set) -> float:
        """Calculate Jaccard similarity between two sets"""
        if not set1 and not set2:
            return 1.0
        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

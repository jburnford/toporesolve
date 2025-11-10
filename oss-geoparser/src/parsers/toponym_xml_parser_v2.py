"""
Toponym XML Parser for Simplified Format (v2)

Parses the new simplified toponym XML format with:
- Full text preservation (paragraphs separated from entities)
- Paragraph-level structure with character offsets
- On-the-fly proximity entity calculation (no pre-extracted nearby entities)
- Document-level character offsets for precise location
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple, Set
from dataclasses import dataclass
import sys
import os

# Import base types
sys.path.append(os.path.dirname(__file__))
from xml_parser import LocationContext, LocationMention


@dataclass
class ToponymMention:
    """Single mention of a toponym in the document"""
    paragraph_id: str
    char_start: int
    char_end: int
    nearby_toponyms: List[str]


class ToponymXMLParserV2:
    """
    Parser for simplified toponym XML format (v2)

    New Format:
    <document>
      <text>
        <paragraph id="p0" char_start="0" char_end="10">...</paragraph>
      </text>
      <entities>
        <toponyms>
          <toponym name="London" mention_count="5">
            <mention paragraph_id="p0" char_start="5" char_end="11"/>
          </toponym>
        </toponyms>
      </entities>
    </document>

    Features:
    - Extracts toponyms from <entities><toponyms> section
    - Loads full paragraph text from <text> section
    - Calculates proximity entities on-the-fly within 500-char window
    - No pre-extracted nearby entities in XML
    - Character-offset based context extraction
    """

    def __init__(self, context_paragraphs: int = 2, proximity_window: int = 500):
        """
        Args:
            context_paragraphs: Number of paragraphs before/after to include in context
            proximity_window: Character distance for proximity entity calculation
        """
        self.context_paragraphs = context_paragraphs
        self.proximity_window = proximity_window
        self.paragraphs = {}  # paragraph_id -> text
        self.paragraph_order = []  # ordered list of paragraph IDs

    def parse_file(self, xml_path: str) -> List[LocationMention]:
        """
        Parse toponym XML file

        Args:
            xml_path: Path to toponym XML file

        Returns:
            List of LocationMention objects (one per unique toponym)
        """
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Parse document metadata
        document_id = root.get('id')

        # Step 1: Load all paragraphs into memory
        self._load_paragraphs(root)

        # Step 2: Collect ALL toponym mentions (for proximity calculation)
        all_mentions = self._collect_all_mentions(root)

        # Step 3: Get unique toponym names
        unique_toponyms = self._get_unique_toponyms(all_mentions)

        # Step 4: Parse toponyms element
        toponyms_elem = root.find('.//toponyms')
        if toponyms_elem is None:
            return []

        mentions = []
        for toponym_elem in toponyms_elem.findall('toponym'):
            toponym_name = toponym_elem.get('name')
            mention_count = int(toponym_elem.get('mention_count', 0))

            # Parse all mentions of this toponym
            contexts = []
            for mention_elem in toponym_elem.findall('mention'):
                paragraph_id = mention_elem.get('paragraph_id')
                char_start = int(mention_elem.get('char_start'))
                char_end = int(mention_elem.get('char_end'))

                # Calculate proximity entities
                nearby_toponyms = self._calculate_proximity_entities(
                    char_start, char_end, toponym_name, all_mentions
                )

                # Build context text
                context_text = self._build_context_text(
                    paragraph_id, char_start, char_end
                )

                # Create LocationContext
                context = LocationContext(
                    text=context_text,
                    nearby_locations=nearby_toponyms,
                    position_in_doc=self._calculate_position(paragraph_id)
                )
                contexts.append(context)

            # Create LocationMention
            mention = LocationMention(
                name=toponym_name,
                mention_count=mention_count,
                contexts=contexts,
                document_id=document_id,
                all_doc_locations=unique_toponyms
            )
            mentions.append(mention)

        return mentions

    def _load_paragraphs(self, root):
        """Load all paragraphs into memory"""
        text_elem = root.find('text')
        if text_elem is None:
            return

        for para in text_elem.findall('paragraph'):
            para_id = para.get('id')
            para_text = para.text or ''
            self.paragraphs[para_id] = para_text
            self.paragraph_order.append(para_id)

    def _collect_all_mentions(self, root) -> List[Tuple[str, str, int, int]]:
        """
        Collect all toponym mentions in document

        Returns:
            List of (name, paragraph_id, char_start, char_end) tuples
        """
        all_mentions = []

        toponyms_elem = root.find('.//toponyms')
        if toponyms_elem is None:
            return all_mentions

        for toponym_elem in toponyms_elem.findall('toponym'):
            name = toponym_elem.get('name')
            for mention_elem in toponym_elem.findall('mention'):
                para_id = mention_elem.get('paragraph_id')
                char_start = int(mention_elem.get('char_start'))
                char_end = int(mention_elem.get('char_end'))
                all_mentions.append((name, para_id, char_start, char_end))

        return all_mentions

    def _get_unique_toponyms(self, all_mentions: List[Tuple[str, str, int, int]]) -> List[str]:
        """Get list of unique toponym names"""
        return list(set(name for name, _, _, _ in all_mentions))

    def _calculate_proximity_entities(
        self,
        mention_start: int,
        mention_end: int,
        target_name: str,
        all_mentions: List[Tuple[str, str, int, int]]
    ) -> List[str]:
        """
        Calculate toponyms near a mention (within proximity_window characters)

        Args:
            mention_start: Document-level char offset (start)
            mention_end: Document-level char offset (end)
            target_name: Name of the target toponym (to exclude self-mentions)
            all_mentions: List of (name, para_id, start, end) for all toponyms

        Returns:
            List of nearby toponym names (unique)
        """
        nearby = []

        for name, para_id, start, end in all_mentions:
            # Skip self-mention (exact same location)
            if start == mention_start and end == mention_end:
                continue

            # Calculate distance (document-level offsets)
            # Distance is the gap between the two mentions
            distance = min(
                abs(start - mention_end),  # Distance from end of target to start of other
                abs(end - mention_start)   # Distance from end of other to start of target
            )

            if distance <= self.proximity_window:
                nearby.append(name)

        # Return unique names, preserving order
        seen = set()
        unique_nearby = []
        for name in nearby:
            if name not in seen:
                seen.add(name)
                unique_nearby.append(name)

        return unique_nearby

    def _build_context_text(self, paragraph_id: str, char_start: int, char_end: int) -> str:
        """
        Build context text including N paragraphs before/after

        Args:
            paragraph_id: ID of paragraph containing the mention
            char_start: Character offset of mention start (not used currently)
            char_end: Character offset of mention end (not used currently)

        Returns:
            Context text (target paragraph + surrounding paragraphs)
        """
        try:
            para_index = self.paragraph_order.index(paragraph_id)
        except ValueError:
            return ""

        # Calculate range of paragraphs to include
        start_index = max(0, para_index - self.context_paragraphs)
        end_index = min(len(self.paragraph_order), para_index + self.context_paragraphs + 1)

        # Build context from paragraphs
        context_parts = []
        for i in range(start_index, end_index):
            para_id = self.paragraph_order[i]
            para_text = self.paragraphs.get(para_id, '')
            context_parts.append(para_text)

        return ' '.join(context_parts)

    def _calculate_position(self, paragraph_id: str) -> float:
        """Calculate position in document (0.0 to 1.0)"""
        try:
            para_index = self.paragraph_order.index(paragraph_id)
            return para_index / max(len(self.paragraph_order) - 1, 1)
        except ValueError:
            return 0.5

    def _get_all_toponyms(self, root) -> List[str]:
        """Get list of all unique toponym names in document"""
        toponyms_elem = root.find('.//toponyms')
        if toponyms_elem is None:
            return []

        return [t.get('name') for t in toponyms_elem.findall('toponym') if t.get('name')]


# Alias for backward compatibility
ToponymXMLParser = ToponymXMLParserV2

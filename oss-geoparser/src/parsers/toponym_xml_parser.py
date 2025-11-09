"""
Toponym XML Parser for Improved Format

Parses the new toponym-specific XML format with:
- Full text preservation (no duplicate paragraphs)
- Paragraph-level structure with character offsets
- Nearby entities pre-extracted within 500-char window
- Organized by entity type (toponyms, water bodies, landforms, etc.)
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
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
    nearby_water_bodies: List[str]
    nearby_landforms: List[str]
    nearby_admin_regions: List[str]
    nearby_routes: List[str]


class ToponymXMLParser:
    """
    Parser for improved toponym XML format

    Features:
    - Extracts toponyms only (settlements)
    - Accesses full paragraph text via paragraph IDs
    - Uses pre-extracted nearby entities (500-char window)
    - No duplicate paragraphs
    - Character-offset based context extraction
    """

    def __init__(self, context_paragraphs: int = 2):
        """
        Args:
            context_paragraphs: Number of paragraphs before/after to include in context
        """
        self.context_paragraphs = context_paragraphs
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

        # Step 2: Parse toponyms (settlements only)
        toponyms_elem = root.find('.//toponyms')
        if toponyms_elem is None:
            return []

        mentions = []
        for toponym_elem in toponyms_elem.findall('toponym'):
            toponym_name = toponym_elem.get('name')
            mention_count = int(toponym_elem.get('mention_count', 0))

            # Parse all mentions of this toponym
            toponym_mentions = self._parse_toponym_mentions(toponym_elem)

            # Build LocationContext objects
            contexts = []
            for tm in toponym_mentions:
                context_text = self._build_context_text(
                    tm.paragraph_id,
                    tm.char_start,
                    tm.char_end
                )

                # Combine all nearby entity types
                # Excluding landforms and routes as they're not groundable
                nearby_locations = list(set(
                    tm.nearby_toponyms +
                    tm.nearby_water_bodies +
                    tm.nearby_admin_regions
                ))

                # Calculate position in document (0.0 to 1.0)
                position = self._calculate_position(tm.paragraph_id)

                context = LocationContext(
                    text=context_text,
                    nearby_locations=nearby_locations,
                    position_in_doc=position
                )
                contexts.append(context)

            # Create LocationMention
            mention = LocationMention(
                name=toponym_name,
                mention_count=mention_count,
                contexts=contexts,
                document_id=document_id,
                all_doc_locations=self._get_all_toponyms(root)
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

    def _parse_toponym_mentions(self, toponym_elem) -> List[ToponymMention]:
        """Parse all mentions of a single toponym"""
        mentions = []

        for mention_elem in toponym_elem.findall('mention'):
            paragraph_id = mention_elem.get('paragraph_id')
            char_start = int(mention_elem.get('char_start'))
            char_end = int(mention_elem.get('char_end'))

            # Extract nearby entities (already done in XML!)
            nearby_entities = mention_elem.find('nearby_entities')

            nearby_toponyms = []
            nearby_water_bodies = []
            nearby_landforms = []
            nearby_admin_regions = []
            nearby_routes = []

            if nearby_entities is not None:
                # Toponyms
                toponyms_elem = nearby_entities.find('.//toponyms')
                if toponyms_elem is not None:
                    nearby_toponyms = [t.text for t in toponyms_elem.findall('toponym') if t.text]

                # Water bodies
                water_elem = nearby_entities.find('.//water_bodys')  # Note: water_bodys (typo in XML?)
                if water_elem is not None:
                    nearby_water_bodies = [w.text for w in water_elem.findall('water_body') if w.text]

                # Landforms
                landforms_elem = nearby_entities.find('.//landforms')
                if landforms_elem is not None:
                    nearby_landforms = [l.text for l in landforms_elem.findall('landform') if l.text]

                # Administrative regions
                admin_elem = nearby_entities.find('.//administrative_regions')
                if admin_elem is not None:
                    nearby_admin_regions = [a.text for a in admin_elem.findall('administrative_region') if a.text]

                # Routes
                routes_elem = nearby_entities.find('.//routes')
                if routes_elem is not None:
                    nearby_routes = [r.text for r in routes_elem.findall('route') if r.text]

            mention = ToponymMention(
                paragraph_id=paragraph_id,
                char_start=char_start,
                char_end=char_end,
                nearby_toponyms=nearby_toponyms,
                nearby_water_bodies=nearby_water_bodies,
                nearby_landforms=nearby_landforms,
                nearby_admin_regions=nearby_admin_regions,
                nearby_routes=nearby_routes
            )
            mentions.append(mention)

        return mentions

    def _build_context_text(self, paragraph_id: str, char_start: int, char_end: int) -> str:
        """
        Build context text including N paragraphs before/after

        Args:
            paragraph_id: ID of paragraph containing the mention
            char_start: Character offset of mention start
            char_end: Character offset of mention end

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

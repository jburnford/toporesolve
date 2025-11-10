"""
Toponym filtering to identify ungroundable locations

Filters out:
- Generic descriptors ("the river", "the lake", "the mountain")
- Relative references ("north", "south", "here", "there")
- Non-specific locations ("the place", "the area", "the region")
- Abbreviations without context ("N.Y.", "U.S.", "Calif.")
- Person names misidentified as locations
"""

import re
from typing import Tuple, Optional
from enum import Enum


class FilterReason(Enum):
    """Reasons why a toponym cannot be grounded"""
    GENERIC_DESCRIPTOR = "generic_descriptor"
    RELATIVE_REFERENCE = "relative_reference"
    NON_SPECIFIC = "non_specific"
    AMBIGUOUS_ABBREVIATION = "ambiguous_abbreviation"
    TOO_SHORT = "too_short"
    NUMERIC_ONLY = "numeric_only"
    LIKELY_PERSON_NAME = "likely_person_name"
    BLACKLISTED = "blacklisted"
    AMBIGUOUS_TERM = "ambiguous_term"  # Terms too ambiguous to ground reliably


class ToponymFilter:
    """
    Filter ungroundable toponyms before disambiguation

    Saves API costs by rejecting toponyms that:
    1. Cannot be matched to a specific place
    2. Are too ambiguous without additional context
    3. Are likely NER errors
    """

    def __init__(self, strict_mode: bool = False, ambiguous_terms_file: Optional[str] = None):
        """
        Args:
            strict_mode: If True, apply stricter filtering (fewer false positives)
            ambiguous_terms_file: Optional path to file with ambiguous terms (one per line)
        """
        self.strict_mode = strict_mode

        # Generic descriptors (with "the")
        self.generic_descriptors = {
            'the river', 'the lake', 'the mountain', 'the hill', 'the valley',
            'the creek', 'the stream', 'the bay', 'the island', 'the peninsula',
            'the rapids', 'the falls', 'the portage', 'the trail', 'the road',
            'the bridge', 'the pass', 'the canyon', 'the plateau', 'the ridge',
            'the forest', 'the woods', 'the prairie', 'the plains', 'the desert',
            'the coast', 'the shore', 'the beach', 'the harbor', 'the port',
            'the settlement', 'the village', 'the town', 'the city', 'the fort',
            'the post', 'the station', 'the camp', 'the encampment'
        }

        # Relative/directional references
        self.relative_references = {
            'north', 'south', 'east', 'west', 'northeast', 'northwest',
            'southeast', 'southwest', 'northern', 'southern', 'eastern', 'western',
            'here', 'there', 'yonder', 'beyond', 'above', 'below',
            'upstream', 'downstream', 'upriver', 'downriver'
        }

        # Non-specific locations
        self.non_specific = {
            'the place', 'the area', 'the region', 'the district', 'the territory',
            'the country', 'the land', 'the locality', 'the vicinity', 'the neighborhood',
            'the site', 'the spot', 'the location', 'the position'
        }

        # Problematic abbreviations (need more context)
        self.ambiguous_abbreviations = {
            'N.Y.', 'U.S.', 'U.K.', 'B.C.', 'D.C.', 'Calif.', 'Penn.', 'Mass.',
            'Conn.', 'N.C.', 'S.C.', 'N.D.', 'S.D.', 'La.', 'Ont.', 'Que.',
            'N.W.T.', 'Alta.', 'Sask.', 'Man.', 'N.B.', 'P.E.I.', 'N.S.'
        }

        # Blacklist of common NER errors
        self.blacklist = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'from',
            'up', 'down', 'out', 'over', 'under', 'about', 'after', 'before'
        }

        # Common person name indicators (titles, suffixes)
        self.person_indicators = {
            'mr.', 'mrs.', 'ms.', 'miss', 'dr.', 'prof.', 'sir', 'lady', 'lord',
            'capt.', 'captain', 'lt.', 'col.', 'gen.', 'rev.', 'father', 'brother'
        }

        # Ambiguous terms - too generic to reliably ground
        # These are common words that appear as toponyms but have many candidates
        # Start with obvious examples; can be expanded based on data analysis
        self.ambiguous_terms = {
            # Generic geographic features (without "the")
            'fort', 'river', 'lake', 'mountain', 'hill', 'creek', 'island',
            'bay', 'valley', 'falls', 'rapids', 'portage', 'pass', 'bridge',

            # Generic settlement types
            'city', 'town', 'village', 'settlement', 'post', 'station', 'camp',

            # Directional/regional terms
            'north', 'south', 'east', 'west', 'central', 'upper', 'lower',
            'new', 'old', 'great', 'little', 'big', 'small',

            # Common ambiguous words
            'union', 'junction', 'center', 'centre', 'cross', 'corner',
            'point', 'head', 'mouth', 'landing', 'springs', 'wells'
        }

        # Load custom ambiguous terms from file if provided
        if ambiguous_terms_file:
            self._load_ambiguous_terms(ambiguous_terms_file)

    def _load_ambiguous_terms(self, filepath: str):
        """Load additional ambiguous terms from file (one per line)"""
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    term = line.strip().lower()
                    if term and not term.startswith('#'):  # Skip empty lines and comments
                        self.ambiguous_terms.add(term)
        except FileNotFoundError:
            pass  # File is optional

    def is_groundable(self, toponym: str, context: Optional[str] = None) -> Tuple[bool, Optional[FilterReason]]:
        """
        Check if toponym can be grounded to a specific location

        Returns:
            (is_groundable, reason_if_not)
        """
        normalized = toponym.strip().lower()

        # Check blacklist
        if normalized in self.blacklist:
            return (False, FilterReason.BLACKLISTED)

        # Check too short (single letter or number)
        if len(normalized) <= 1:
            return (False, FilterReason.TOO_SHORT)

        # Check numeric only
        if normalized.replace('.', '').replace(',', '').isdigit():
            return (False, FilterReason.NUMERIC_ONLY)

        # Check generic descriptors
        if normalized in self.generic_descriptors:
            return (False, FilterReason.GENERIC_DESCRIPTOR)

        # Check if starts with "the " and has generic geographic term
        if normalized.startswith('the '):
            suffix = normalized[4:]  # Remove "the "
            if self._is_generic_geographic_term(suffix):
                return (False, FilterReason.GENERIC_DESCRIPTOR)

        # Check relative references
        if normalized in self.relative_references:
            return (False, FilterReason.RELATIVE_REFERENCE)

        # Check non-specific locations
        if normalized in self.non_specific:
            return (False, FilterReason.NON_SPECIFIC)

        # Check ambiguous abbreviations (only in strict mode or without context)
        if self.strict_mode or context is None:
            if toponym in self.ambiguous_abbreviations:
                # Allow if context helps disambiguate
                if context and self._context_disambiguates_abbreviation(toponym, context):
                    pass  # Continue to other checks
                else:
                    return (False, FilterReason.AMBIGUOUS_ABBREVIATION)

        # Check for person name indicators
        if context and self._likely_person_name(toponym, context):
            return (False, FilterReason.LIKELY_PERSON_NAME)

        # Check ambiguous terms (too generic to ground reliably)
        if normalized in self.ambiguous_terms:
            return (False, FilterReason.AMBIGUOUS_TERM)

        # Passed all filters
        return (True, None)

    def _is_generic_geographic_term(self, term: str) -> bool:
        """Check if term is a generic geographic feature"""
        generic_terms = {
            'river', 'lake', 'mountain', 'hill', 'valley', 'creek', 'stream',
            'bay', 'island', 'rapids', 'falls', 'portage', 'trail', 'road',
            'bridge', 'pass', 'canyon', 'plateau', 'ridge', 'forest', 'woods',
            'prairie', 'plains', 'desert', 'coast', 'shore', 'beach', 'harbor',
            'settlement', 'village', 'town', 'city', 'fort', 'post', 'station'
        }
        return term in generic_terms

    def _context_disambiguates_abbreviation(self, abbrev: str, context: str) -> bool:
        """
        Check if context provides enough information to disambiguate abbreviation

        e.g., "N.Y." with "New York" nearby, or "U.S." with "United States"
        """
        context_lower = context.lower()

        # Mapping of abbreviations to their full forms
        expansions = {
            'N.Y.': ['new york'],
            'U.S.': ['united states', 'america'],
            'U.K.': ['united kingdom', 'britain', 'england'],
            'B.C.': ['british columbia'],
            'D.C.': ['district of columbia', 'washington'],
            'Calif.': ['california'],
            'Penn.': ['pennsylvania'],
            'Mass.': ['massachusetts'],
            'Ont.': ['ontario'],
            'Que.': ['quebec'],
            'Sask.': ['saskatchewan'],
            'Man.': ['manitoba'],
            'Alta.': ['alberta']
        }

        if abbrev in expansions:
            for expansion in expansions[abbrev]:
                if expansion in context_lower:
                    return True

        return False

    def _likely_person_name(self, toponym: str, context: str) -> bool:
        """
        Check if toponym is likely a person name based on context

        Looks for:
        - Title/prefix before name (Mr., Dr., Captain, etc.)
        - Possessive usage (Smith's, Johnson's)
        - Verb patterns ("Smith said", "Johnson reported")
        """
        # Check for titles in context near the toponym
        context_lower = context.lower()
        toponym_lower = toponym.lower()

        # Find position of toponym in context
        pos = context_lower.find(toponym_lower)
        if pos == -1:
            return False

        # Check 50 characters before toponym for titles
        start = max(0, pos - 50)
        prefix = context_lower[start:pos]

        for indicator in self.person_indicators:
            if indicator in prefix:
                # Check if indicator is close to toponym (within 20 chars)
                indicator_pos = prefix.rfind(indicator)
                if pos - start - indicator_pos < 20:
                    return True

        # Check for possessive usage
        end = min(len(context), pos + len(toponym) + 2)
        if context[pos:end].endswith("'s"):
            # Could be location possessive (e.g., "Canada's") or person
            # Person more likely if preceded by title
            return any(indicator in prefix[-30:] for indicator in self.person_indicators)

        # Check for verb patterns suggesting person
        suffix_end = min(len(context), pos + len(toponym) + 30)
        suffix = context_lower[pos + len(toponym):suffix_end]

        person_verbs = [' said', ' stated', ' reported', ' wrote', ' argued', ' claimed']
        if any(verb in suffix for verb in person_verbs):
            return True

        return False

    def filter_mentions(self, mentions: list) -> Tuple[list, list]:
        """
        Filter list of location mentions

        Args:
            mentions: List of LocationMention objects

        Returns:
            (groundable_mentions, filtered_mentions_with_reasons)
        """
        groundable = []
        filtered = []

        for mention in mentions:
            # Check with first context as sample
            context = mention.contexts[0].text if mention.contexts else None

            is_ok, reason = self.is_groundable(mention.name, context)

            if is_ok:
                groundable.append(mention)
            else:
                filtered.append({
                    'mention': mention,
                    'reason': reason.value if reason else 'unknown',
                    'name': mention.name
                })

        return (groundable, filtered)

    def get_filter_statistics(self, filtered: list) -> dict:
        """Get statistics on why toponyms were filtered"""
        stats = {}
        for item in filtered:
            reason = item['reason']
            if reason not in stats:
                stats[reason] = []
            stats[reason].append(item['name'])

        return {
            reason: {
                'count': len(names),
                'examples': names[:10]  # First 10 examples
            }
            for reason, names in stats.items()
        }

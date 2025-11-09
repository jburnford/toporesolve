"""
Test script for ToponymXMLParser

Validates parsing of improved XML format with:
- Full text preservation (no duplicates)
- Paragraph structure with character offsets
- Pre-extracted nearby entities
- Organized entity types
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from parsers.toponym_xml_parser import ToponymXMLParser


def main():
    """Test ToponymXMLParser on sample XML"""

    xml_path = "/home/jic823/saskatchewan_toponyms_xml/P000045.toponym.xml"

    if not os.path.exists(xml_path):
        print(f"Error: XML file not found: {xml_path}")
        return

    print(f"{'='*80}")
    print("Testing ToponymXMLParser")
    print(f"{'='*80}\n")

    # Initialize parser
    parser = ToponymXMLParser(context_paragraphs=2)

    # Parse file
    print("Parsing XML file...")
    mentions = parser.parse_file(xml_path)

    print(f"\n✓ Successfully parsed {len(mentions)} unique toponyms\n")

    # Show summary statistics
    total_contexts = sum(len(m.contexts) for m in mentions)
    print(f"{'='*80}")
    print("PARSING SUMMARY")
    print(f"{'='*80}")
    print(f"Unique toponyms: {len(mentions)}")
    print(f"Total contexts: {total_contexts}")
    print(f"Average contexts per toponym: {total_contexts / len(mentions):.1f}")
    print(f"Paragraphs loaded: {len(parser.paragraphs)}")

    # Show sample toponyms
    print(f"\n{'='*80}")
    print("SAMPLE TOPONYMS (first 5)")
    print(f"{'='*80}\n")

    for i, mention in enumerate(mentions[:5], 1):
        print(f"--- {i}. {mention.name} ---")
        print(f"Mention count: {mention.mention_count}")
        print(f"Number of contexts: {len(mention.contexts)}")
        print(f"Document ID: {mention.document_id}")
        print(f"All document locations: {len(mention.all_doc_locations)} total")

        if mention.contexts:
            # Show first context
            ctx = mention.contexts[0]
            print(f"\nFirst context:")
            print(f"  Text preview: {ctx.text[:200]}...")
            print(f"  Nearby locations: {', '.join(ctx.nearby_locations[:5])}")
            if len(ctx.nearby_locations) > 5:
                print(f"    ... and {len(ctx.nearby_locations) - 5} more")
            print(f"  Position in doc: {ctx.position_in_doc:.2f}")

        print()

    # Detailed examination of one toponym with multiple mentions
    print(f"{'='*80}")
    print("DETAILED EXAMINATION: Toponym with Multiple Mentions")
    print(f"{'='*80}\n")

    # Find a toponym with multiple mentions
    multi_mention = next((m for m in mentions if m.mention_count > 5), None)

    if multi_mention:
        print(f"Toponym: {multi_mention.name}")
        print(f"Total mentions: {multi_mention.mention_count}")
        print(f"Contexts extracted: {len(multi_mention.contexts)}")

        print(f"\nAll contexts:")
        for i, ctx in enumerate(multi_mention.contexts, 1):
            print(f"\n  Context {i}:")
            print(f"    Position: {ctx.position_in_doc:.2f}")
            print(f"    Text: {ctx.text[:150]}...")
            print(f"    Nearby: {', '.join(ctx.nearby_locations[:3])}")
            if len(ctx.nearby_locations) > 3:
                print(f"      ... and {len(ctx.nearby_locations) - 3} more")
    else:
        print("No toponyms with >5 mentions found")

    # Check for duplicate contexts
    print(f"\n{'='*80}")
    print("CHECKING FOR DUPLICATE CONTEXTS")
    print(f"{'='*80}\n")

    duplicates_found = False
    for mention in mentions[:10]:  # Check first 10
        context_texts = [ctx.text for ctx in mention.contexts]
        unique_texts = set(context_texts)

        if len(context_texts) != len(unique_texts):
            print(f"⚠ {mention.name}: {len(context_texts)} contexts, {len(unique_texts)} unique")
            duplicates_found = True

    if not duplicates_found:
        print("✓ No duplicate contexts found in sample")

    # Show nearby entity type distribution
    print(f"\n{'='*80}")
    print("NEARBY ENTITY ANALYSIS")
    print(f"{'='*80}\n")

    sample = mentions[0]
    if sample.contexts:
        ctx = sample.contexts[0]
        print(f"Sample toponym: {sample.name}")
        print(f"Nearby locations: {len(ctx.nearby_locations)}")
        print(f"Examples: {', '.join(ctx.nearby_locations[:10])}")

    print(f"\n{'='*80}")
    print("✓ ToponymXMLParser Test Complete")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()

"""
OSS-Geoparser: Advanced Multi-Context Toponym Disambiguation

Main orchestrator that integrates:
- XML parsing with nearby location extraction
- Optional toponym filtering
- Context clustering for multi-referent detection
- Enhanced RAG disambiguation with GPT-OSS-120B
- Full provenance and explainability
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import json
import sys
import os

# Import components
sys.path.append(os.path.dirname(__file__))
from parsers.xml_parser import SaskatchewanXMLParser, LocationMention
from parsers.toponym_xml_parser import ToponymXMLParser
from utils.toponym_filter import ToponymFilter
from clustering.context_clusterer import ContextClusterer
from disambiguation.multi_context_rag import MultiContextDisambiguator, DisambiguationResult
from knowledge_graph.neo4j_interface import Neo4jKnowledgeGraph


@dataclass
class GeoparseResult:
    """Complete geoparse result for a document"""
    document_id: str
    total_mentions: int
    filtered_mentions: int
    processed_mentions: int
    multi_referent_detected: int
    results: List[Dict]  # Serialized DisambiguationResults
    filter_statistics: Optional[Dict] = None


class OSSGeoparser:
    """
    Main geoparser orchestrator

    Pipeline:
    1. Parse XML → LocationMentions with contexts
    2. Filter ungroundable toponyms (optional)
    3. Cluster contexts to detect multiple referents
    4. Disambiguate using enhanced RAG + LLM
    5. Return results with full provenance
    """

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        llm_client,
        enable_filtering: bool = True,
        filter_strict_mode: bool = False,
        model: str = "openai/gpt-oss-120b",
        max_contexts_per_cluster: int = 3,
        max_candidates: int = 10,
        similarity_threshold: float = 0.3,
        xml_format: str = "toponym"  # "saskatchewan" or "toponym"
    ):
        """
        Initialize geoparser with all components

        Args:
            neo4j_uri: Neo4j database URI
            neo4j_user: Database username
            neo4j_password: Database password
            llm_client: OpenRouter LLM client
            enable_filtering: Whether to filter ungroundable toponyms
            filter_strict_mode: Stricter toponym filtering
            model: LLM model to use
            max_contexts_per_cluster: Max contexts to show LLM
            max_candidates: Max candidates from Neo4j
            similarity_threshold: Jaccard threshold for context clustering
            xml_format: XML format ("saskatchewan" for old format, "toponym" for new improved format)
        """
        self.logger = logging.getLogger(__name__)

        # Initialize parser based on XML format
        if xml_format == "toponym":
            self.parser = ToponymXMLParser(context_paragraphs=2)
            self.logger.info("Using ToponymXMLParser (improved format)")
        else:
            self.parser = SaskatchewanXMLParser()
            self.logger.info("Using SaskatchewanXMLParser (legacy format)")

        self.filter_enabled = enable_filtering
        if enable_filtering:
            self.filter = ToponymFilter(strict_mode=filter_strict_mode)
            self.logger.info("Toponym filtering: ENABLED")
        else:
            self.filter = None
            self.logger.info("Toponym filtering: DISABLED")

        self.clusterer = ContextClusterer(
            similarity_threshold=similarity_threshold,
            min_cluster_size=1
        )

        self.neo4j = Neo4jKnowledgeGraph(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password
        )

        self.disambiguator = MultiContextDisambiguator(
            neo4j_interface=self.neo4j,
            llm_client=llm_client,
            context_clusterer=self.clusterer,
            model=model,
            max_contexts_per_cluster=max_contexts_per_cluster,
            max_candidates=max_candidates
        )

        self.logger.info("OSS-Geoparser initialized successfully")

    def close(self):
        """Close database connections"""
        self.neo4j.close()

    def geoparse_document(
        self,
        xml_path: str,
        source_location: Optional[Dict] = None,
        disambiguate_all_clusters: bool = False
    ) -> GeoparseResult:
        """
        Geoparse a single XML document

        Args:
            xml_path: Path to XML file with NER locations
            source_location: Optional geographic source (e.g., newspaper location)
            disambiguate_all_clusters: If True, disambiguate all detected clusters

        Returns:
            GeoparseResult with all disambiguation results
        """
        self.logger.info(f"=== Geoparsing document: {xml_path} ===")

        # Step 1: Parse XML
        mentions = self.parser.parse_file(xml_path)
        self.logger.info(f"Parsed {len(mentions)} unique location mentions")

        if not mentions:
            return GeoparseResult(
                document_id=os.path.basename(xml_path),
                total_mentions=0,
                filtered_mentions=0,
                processed_mentions=0,
                multi_referent_detected=0,
                results=[]
            )

        # Step 2: Filter ungroundable toponyms (if enabled)
        filtered_count = 0
        filter_stats = None

        if self.filter_enabled:
            groundable, filtered = self.filter.filter_mentions(mentions)
            filter_stats = self.filter.get_filter_statistics(filtered)
            filtered_count = len(filtered)

            self.logger.info(f"Filtered {filtered_count} ungroundable toponyms")
            self.logger.info(f"Proceeding with {len(groundable)} groundable mentions")

            mentions = groundable

        # Step 3: Disambiguate each mention
        results = []
        multi_referent_count = 0

        for i, mention in enumerate(mentions, 1):
            self.logger.info(f"\n--- Processing {i}/{len(mentions)}: '{mention.name}' ---")

            try:
                if disambiguate_all_clusters:
                    # Disambiguate all detected clusters (for multi-referent cases)
                    cluster_results = self.disambiguator.disambiguate_all_clusters(
                        mention,
                        source_location=source_location
                    )

                    if len(cluster_results) > 1:
                        multi_referent_count += 1

                    for result in cluster_results:
                        results.append(self._serialize_result(result))

                else:
                    # Disambiguate largest cluster only
                    result = self.disambiguator.disambiguate(
                        mention,
                        source_location=source_location
                    )

                    if result.has_multiple_referents:
                        multi_referent_count += 1

                    results.append(self._serialize_result(result))

            except Exception as e:
                self.logger.error(f"Error processing '{mention.name}': {e}")
                # Add error result
                results.append({
                    'toponym': mention.name,
                    'selected_candidate': None,
                    'confidence': 'error',
                    'reasoning': f"Processing error: {str(e)}",
                    'error': True
                })

        # Step 4: Return complete results
        return GeoparseResult(
            document_id=os.path.basename(xml_path),
            total_mentions=len(mentions) + filtered_count,
            filtered_mentions=filtered_count,
            processed_mentions=len(mentions),
            multi_referent_detected=multi_referent_count,
            results=results,
            filter_statistics=filter_stats
        )

    def geoparse_batch(
        self,
        xml_paths: List[str],
        source_location: Optional[Dict] = None,
        output_path: Optional[str] = None
    ) -> List[GeoparseResult]:
        """
        Geoparse multiple documents

        Args:
            xml_paths: List of XML file paths
            source_location: Optional geographic source
            output_path: If provided, save results to JSON

        Returns:
            List of GeoparseResult objects
        """
        self.logger.info(f"=== Batch geoparsing {len(xml_paths)} documents ===")

        results = []
        for i, xml_path in enumerate(xml_paths, 1):
            self.logger.info(f"\n{'='*80}")
            self.logger.info(f"Document {i}/{len(xml_paths)}")
            self.logger.info(f"{'='*80}")

            result = self.geoparse_document(xml_path, source_location)
            results.append(result)

        # Save to file if requested
        if output_path:
            with open(output_path, 'w') as f:
                json.dump([asdict(r) for r in results], f, indent=2)
            self.logger.info(f"\nResults saved to: {output_path}")

        return results

    def _serialize_result(self, result: DisambiguationResult) -> Dict:
        """Convert DisambiguationResult to serializable dict"""
        return {
            'toponym': result.toponym,
            'selected_candidate': result.selected_candidate,
            'confidence': result.confidence,
            'reasoning': result.reasoning,
            'clusters_detected': result.clusters_detected,
            'has_multiple_referents': result.has_multiple_referents,
            'all_candidates': result.all_candidates,
            'contexts_used': result.contexts_used,
            'nearby_locations': result.nearby_locations,
            'source_location': result.source_location
        }

    def get_statistics(self) -> Dict:
        """Get knowledge graph statistics"""
        return self.neo4j.get_statistics()

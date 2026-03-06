"""Indexing service for storing document chunks in vector store and database."""

import logging
import uuid
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clause import Clause, ClauseType
from app.models.contract import Contract, ContractStatus
from app.services.chunker import Chunk, ChunkedDocument, DocumentChunker, get_chunker
from app.services.parser import DocumentParser, ParsedDocument, get_parser
from app.services.vector_store import ChunkMetadata, VectorStore, get_vector_store

# Import agents for metadata and risk extraction
from app.agents.metadata_extraction import extract_metadata_with_fallback, update_contract_metadata
from app.agents.risk_detection import assess_risk, update_contract_risk
from app.services.custom_field_extraction import extract_custom_fields
from app.services.knowledge_graph_extractor import get_knowledge_graph_extractor
from app.services.progress_tracker import get_progress_tracker, ProcessingStage
from app.models.knowledge_graph import KGEntity
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


class IndexingError(Exception):
    """Exception raised for indexing errors."""

    pass


class IndexingService:
    """Service for indexing documents into vector store and database."""

    def __init__(
        self,
        db: AsyncSession,
        parser: DocumentParser | None = None,
        chunker: DocumentChunker | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        """Initialize indexing service.

        Args:
            db: Database session.
            parser: Document parser (optional, uses singleton if not provided).
            chunker: Document chunker (optional, uses singleton if not provided).
            vector_store: Vector store (optional, uses singleton if not provided).
        """
        self.db = db
        self.parser = parser or get_parser()
        self.chunker = chunker or get_chunker()
        self.vector_store = vector_store or get_vector_store()

    async def index_contract(
        self,
        contract: Contract,
        user_id: str | None = None,
        user_role: str | None = None,
    ) -> tuple[bool, str | None]:
        """Index a contract: parse, chunk, and store vectors.

        Args:
            contract: Contract model to index.
            user_id: User ID for RBAC metadata.
            user_role: User role for RBAC metadata.

        Returns:
            Tuple of (success, error_message).
        """
        contract_id = str(contract.id)
        tracker = get_progress_tracker()

        try:
            # Start progress tracking
            tracker.start_tracking(contract_id)

            # Update status to processing
            contract.status = ContractStatus.PROCESSING
            await self.db.flush()

            # Parse document
            tracker.update_progress(contract_id, ProcessingStage.PARSING, f"Parsing {contract.filename}")
            logger.info(f"Parsing contract {contract.id}: {contract.filename}")
            parsed = self.parser.parse_file(contract.file_path)

            if not parsed.success:
                tracker.update_progress(contract_id, ProcessingStage.FAILED, error=f"Parse error: {parsed.error}")
                return await self._mark_failed(contract, f"Parse error: {parsed.error}")

            # Update contract with parsed metadata
            await self._update_contract_metadata(contract, parsed)

            # Chunk document
            tracker.update_progress(contract_id, ProcessingStage.CHUNKING, "Splitting document into sections")
            logger.info(f"Chunking contract {contract.id}")
            chunked = self.chunker.chunk_document(parsed)

            if not chunked.chunks:
                tracker.update_progress(contract_id, ProcessingStage.FAILED, error="No content extracted")
                return await self._mark_failed(contract, "No content extracted from document")

            # Clean up any existing vectors and clauses (for re-processing)
            await self._cleanup_existing(contract)

            # Store chunks in vector store and database
            tracker.update_progress(
                contract_id, ProcessingStage.CLASSIFYING,
                f"Classifying {len(chunked.chunks)} sections"
            )
            logger.info(f"Indexing {len(chunked.chunks)} chunks for contract {contract.id}")
            await self._store_chunks(contract, chunked, user_id, user_role)

            # Extract metadata using AI agent with regex fallback
            tracker.update_progress(contract_id, ProcessingStage.METADATA, "Extracting contract metadata")
            logger.info(f"Extracting metadata for contract {contract.id}")
            full_text = parsed.full_text or ""
            try:
                metadata = await extract_metadata_with_fallback(
                    contract_text=full_text,
                    contract_id=str(contract.id),
                    user_id=user_id,
                    user_role=user_role,
                )
                await update_contract_metadata(self.db, contract, metadata)
                logger.info(f"Metadata extracted for contract {contract.id} (confidence: {metadata.overall_confidence:.2f})")
                tracker.update_progress(
                    contract_id, ProcessingStage.METADATA,
                    f"Metadata extracted (confidence: {metadata.overall_confidence:.0%})",
                    details={"counterparty": metadata.counterparty.value if metadata.counterparty else None}
                )
            except Exception as e:
                logger.warning(f"Metadata extraction failed for {contract.id}: {e}")

            # Extract custom fields if tenant has them defined
            if contract.tenant_id:
                try:
                    tenant = await self.db.get(Tenant, contract.tenant_id)
                    if tenant and tenant.custom_field_definitions:
                        tracker.update_progress(contract_id, ProcessingStage.CUSTOM_FIELDS, "Extracting custom fields")
                        logger.info(f"Extracting custom fields for contract {contract.id}")
                        custom_fields = await extract_custom_fields(
                            tenant=tenant,
                            contract_text=full_text,
                            contract_id=str(contract.id),
                            entity_type="contract",
                        )
                        if custom_fields:
                            contract.custom_fields = custom_fields
                            logger.info(
                                f"Custom fields extracted for contract {contract.id}: {list(custom_fields.keys())}"
                            )
                except Exception as e:
                    logger.warning(f"Custom field extraction failed for {contract.id}: {e}")

            # Assess risk using AI agent
            tracker.update_progress(contract_id, ProcessingStage.RISK, "Assessing contract risks")
            logger.info(f"Assessing risk for contract {contract.id}")
            try:
                risk_result = await assess_risk(
                    contract_text=full_text,
                    contract_id=str(contract.id),
                    user_id=user_id,
                )
                await update_contract_risk(self.db, contract, risk_result)
                logger.info(f"Risk assessed for contract {contract.id}: {risk_result.risk_level}")
                tracker.update_progress(
                    contract_id, ProcessingStage.RISK,
                    f"Risk level: {risk_result.risk_level}",
                    details={"risk_level": risk_result.risk_level, "risk_score": risk_result.risk_score}
                )
            except Exception as e:
                logger.warning(f"Risk assessment failed for {contract.id}: {e}")

            # Extract knowledge graph (entities and relationships)
            tracker.update_progress(contract_id, ProcessingStage.KNOWLEDGE_GRAPH, "Building knowledge graph")
            logger.info(f"Extracting knowledge graph for contract {contract.id}")
            try:
                kg_extractor = await get_knowledge_graph_extractor(self.db)
                entity_count, rel_count = await kg_extractor.extract_and_store(
                    contract_id=str(contract.id),
                    tenant_id=str(contract.tenant_id),
                    contract_text=full_text,
                    force_reextract=True,  # Always fresh extract during indexing
                )
                logger.info(
                    f"Knowledge graph extracted for contract {contract.id}: "
                    f"{entity_count} entities, {rel_count} relationships"
                )
                tracker.update_progress(
                    contract_id, ProcessingStage.KNOWLEDGE_GRAPH,
                    f"Extracted {entity_count} entities, {rel_count} relationships",
                    details={"entities": entity_count, "relationships": rel_count}
                )
            except Exception as e:
                logger.warning(f"Knowledge graph extraction failed for {contract.id}: {e}")

            # Mark as completed
            contract.status = ContractStatus.COMPLETED
            await self.db.flush()

            # Update progress to completed
            tracker.update_progress(
                contract_id, ProcessingStage.COMPLETED,
                "Processing complete",
                details={"status": "completed"}
            )

            logger.info(f"Successfully indexed contract {contract.id}")
            return True, None

        except Exception as e:
            logger.exception(f"Error indexing contract {contract.id}")
            tracker.update_progress(contract_id, ProcessingStage.FAILED, error=str(e))
            return await self._mark_failed(contract, str(e))

    async def reindex_contract(
        self,
        contract: Contract,
        user_id: str | None = None,
        user_role: str | None = None,
    ) -> tuple[bool, str | None]:
        """Re-index an existing contract.

        Args:
            contract: Contract model to re-index.
            user_id: User ID for RBAC metadata.
            user_role: User role for RBAC metadata.

        Returns:
            Tuple of (success, error_message).
        """
        # Clean up first
        await self._cleanup_existing(contract)

        # Re-index
        return await self.index_contract(contract, user_id, user_role)

    async def delete_contract_index(self, contract: Contract) -> bool:
        """Delete all indexed data for a contract.

        Args:
            contract: Contract to delete index for.

        Returns:
            True if successful.
        """
        try:
            await self._cleanup_existing(contract)
            return True
        except Exception as e:
            logger.exception(f"Error deleting index for contract {contract.id}")
            return False

    async def _mark_failed(
        self, contract: Contract, error: str
    ) -> tuple[bool, str]:
        """Mark a contract as failed.

        Args:
            contract: Contract to mark.
            error: Error message.

        Returns:
            Tuple of (False, error_message).
        """
        contract.status = ContractStatus.FAILED
        contract.processing_error = error[:500]  # Truncate if needed
        await self.db.flush()
        return False, error

    async def _update_contract_metadata(
        self, contract: Contract, parsed: ParsedDocument
    ) -> None:
        """Update contract with parsed document metadata.

        Args:
            contract: Contract to update.
            parsed: Parsed document with metadata.
        """
        if parsed.metadata.title and not contract.filename:
            contract.filename = parsed.metadata.title

        # Store raw text size for reference
        # Additional metadata extraction will be done by the metadata agent

    async def _cleanup_existing(self, contract: Contract) -> None:
        """Clean up existing vectors, clauses, and knowledge graph for a contract.

        Args:
            contract: Contract to clean up.
        """
        contract_id = str(contract.id)

        # Delete from vector store
        try:
            self.vector_store.delete_by_contract_id(contract_id)
        except Exception as e:
            logger.warning(f"Error cleaning up vectors for {contract_id}: {e}")

        # Delete clauses from database
        await self.db.execute(
            delete(Clause).where(Clause.contract_id == contract.id)
        )

        # Delete knowledge graph entities (relationships cascade delete)
        await self.db.execute(
            delete(KGEntity).where(KGEntity.contract_id == contract.id)
        )

    async def _store_chunks(
        self,
        contract: Contract,
        chunked: ChunkedDocument,
        user_id: str | None,
        user_role: str | None,
    ) -> None:
        """Store chunks in vector store and database with semantic classification.

        Args:
            contract: Contract being indexed.
            chunked: Chunked document.
            user_id: User ID for RBAC.
            user_role: User role for RBAC.
        """
        from app.services.section_classifier import smart_classify_batch

        contract_id = str(contract.id)

        # Semantic classification of all chunks (replaces regex-based detection)
        logger.info(f"Classifying {len(chunked.chunks)} chunks semantically for contract {contract.id}")
        chunk_texts = [chunk.text for chunk in chunked.chunks]
        classifications = await smart_classify_batch(chunk_texts, batch_size=10)

        # Prepare data for batch insertion
        documents: list[str] = []
        metadatas: list[ChunkMetadata] = []
        ids: list[str] = []
        clauses: list[Clause] = []

        for chunk, classification in zip(chunked.chunks, classifications):
            chunk_id = f"{contract_id}_{chunk.chunk_index}"

            # Prepare vector store metadata with semantic classification
            metadata = ChunkMetadata(
                contract_id=contract_id,
                tenant_id=str(contract.tenant_id) if contract.tenant_id else None,
                filename=contract.filename,
                section_number=chunk.section_number,
                section_title=classification.section_title,
                page_number=chunk.page_start,
                uploaded_by=user_id,
                allowed_roles=user_role,
                # Semantic classification (replaces regex)
                section_type=classification.section_type,
                semantic_tags=",".join(classification.semantic_tags) if classification.semantic_tags else None,
            )

            documents.append(chunk.text)
            metadatas.append(metadata)
            ids.append(chunk_id)

            # Map AI section classification to clause type
            section_to_clause_type = {
                "sla": ClauseType.SERVICE_LEVEL,
                "governance": ClauseType.GOVERNANCE,
                "liability": ClauseType.LIMITATION_OF_LIABILITY,
                "payment": ClauseType.PAYMENT_TERMS,
                "confidentiality": ClauseType.CONFIDENTIALITY,
                "termination": ClauseType.TERMINATION,
                "ip": ClauseType.INTELLECTUAL_PROPERTY,
                "compliance": ClauseType.DATA_PROTECTION,
                "scope": ClauseType.SCOPE,
                "preamble": ClauseType.PREAMBLE,
                "definitions": ClauseType.DEFINITIONS,
                "exhibits": ClauseType.EXHIBIT,
                "terms": ClauseType.PROCEDURAL,
            }
            clause_type = section_to_clause_type.get(
                classification.section_type,
                ClauseType.OTHER
            )

            # Create clause record with AI-determined type
            clause = Clause(
                contract_id=contract.id,
                clause_type=clause_type,
                text=chunk.text,  # Store full chunk text without truncation
                section_number=chunk.section_number,
                page_number=chunk.page_start,
                confidence_score=classification.confidence,
            )
            clauses.append(clause)

        logger.info(f"Storing {len(documents)} chunks with semantic metadata")

        # Store in vector store (batched)
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i : i + batch_size]
            batch_metas = metadatas[i : i + batch_size]
            batch_ids = ids[i : i + batch_size]

            self.vector_store.add_documents(
                texts=batch_docs,
                metadatas=batch_metas,
                ids=batch_ids,
            )

        # Store clauses in database
        self.db.add_all(clauses)
        await self.db.flush()


class IngestionPipeline:
    """Orchestrates the full document ingestion pipeline."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize pipeline with database session.

        Args:
            db: Database session.
        """
        self.db = db
        self.indexer = IndexingService(db)

    async def process_contract(
        self,
        contract_id: str,
        user_id: str | None = None,
        user_role: str | None = None,
    ) -> tuple[bool, str | None]:
        """Process a contract through the full ingestion pipeline.

        Args:
            contract_id: ID of the contract to process.
            user_id: User ID for RBAC.
            user_role: User role for RBAC.

        Returns:
            Tuple of (success, error_message).
        """
        from sqlalchemy import select

        # Get contract
        result = await self.db.execute(
            select(Contract).where(Contract.id == uuid.UUID(contract_id))
        )
        contract = result.scalar_one_or_none()

        if not contract:
            return False, f"Contract not found: {contract_id}"

        # Run indexing
        return await self.indexer.index_contract(contract, user_id, user_role)

    async def process_batch(
        self,
        contract_ids: list[str],
        user_id: str | None = None,
        user_role: str | None = None,
    ) -> dict[str, tuple[bool, str | None]]:
        """Process multiple contracts.

        Args:
            contract_ids: List of contract IDs to process.
            user_id: User ID for RBAC.
            user_role: User role for RBAC.

        Returns:
            Dictionary mapping contract_id to (success, error) tuple.
        """
        results = {}

        for contract_id in contract_ids:
            success, error = await self.process_contract(contract_id, user_id, user_role)
            results[contract_id] = (success, error)

        return results

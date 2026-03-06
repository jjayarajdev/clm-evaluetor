import uuid
from typing import Any

import chromadb
from chromadb.config import Settings
from pydantic import BaseModel

from app.config import settings


class AccessLevel(str):
    """Access levels for RBAC."""

    PUBLIC = "public"  # All authenticated users
    LEGAL = "legal"  # Legal and Admin only
    PROCUREMENT = "procurement"  # Procurement and Admin only
    ADMIN = "admin"  # Admin only
    RESTRICTED = "restricted"  # Specific users only


class SectionType(str):
    """Semantic section types for contract chunks."""

    PREAMBLE = "preamble"  # Opening, recitals, whereas clauses
    DEFINITIONS = "definitions"  # Defined terms
    PARTIES = "parties"  # Party identification
    SCOPE = "scope"  # Scope of work/services
    TERMS = "terms"  # Term and duration
    PAYMENT = "payment"  # Payment terms, pricing, fees
    CONFIDENTIALITY = "confidentiality"  # NDA provisions
    LIABILITY = "liability"  # Liability, indemnification
    TERMINATION = "termination"  # Termination, renewal
    IP = "ip"  # Intellectual property
    COMPLIANCE = "compliance"  # Regulatory compliance
    GOVERNANCE = "governance"  # Governance, reporting
    SLA = "sla"  # Service levels, KPIs
    EXHIBITS = "exhibits"  # Exhibits, schedules, appendices
    SIGNATURES = "signatures"  # Signature blocks
    GENERAL = "general"  # General provisions, miscellaneous


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk stored in ChromaDB."""

    contract_id: str
    tenant_id: str | None = None  # Tenant ID for multi-tenant isolation
    filename: str | None = None  # Original filename for display
    clause_type: str | None = None
    section_number: str | None = None
    section_title: str | None = None  # Section heading text
    page_number: int | None = None
    char_start: int | None = None
    char_end: int | None = None

    # Semantic classification (replaces regex-based detection)
    section_type: str | None = None  # Semantic type: preamble, definitions, payment, etc.
    semantic_tags: str | None = None  # Comma-separated: "liability,indemnification,risk"

    # RBAC fields
    uploaded_by: str | None = None  # User ID who uploaded
    access_level: str = AccessLevel.PUBLIC  # Default access level
    department: str | None = None  # Owning department
    allowed_roles: str | None = None  # Comma-separated roles (e.g., "admin,legal")


class QueryResult(BaseModel):
    """Result from a similarity query."""

    id: str
    text: str
    metadata: dict[str, Any]
    distance: float


class VectorStore:
    """ChromaDB vector store service for contract chunks.

    IMPORTANT: Uses HTTP client only - no local fallback to prevent data
    inconsistency between two separate databases. If ChromaDB service is
    unavailable, operations will fail fast rather than silently write to
    a different database.
    """

    COLLECTION_NAME = "contract_chunks"

    def __init__(self) -> None:
        """Initialize ChromaDB client."""
        self._client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None
        self._last_heartbeat_failed: bool = False

    def _create_http_client(self) -> chromadb.HttpClient:
        """Create a new HTTP client connection to ChromaDB."""
        return chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=Settings(
                anonymized_telemetry=False,
            ),
        )

    def _ensure_connection(self) -> None:
        """Verify HTTP client is healthy, reconnect if needed.

        This prevents stale connections from causing silent failures.
        """
        if self._client is not None:
            try:
                self._client.heartbeat()
                self._last_heartbeat_failed = False
            except Exception:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("ChromaDB heartbeat failed, reconnecting...")
                self._client = None
                self._collection = None
                self._last_heartbeat_failed = True

    @property
    def client(self) -> chromadb.ClientAPI:
        """Get or create ChromaDB HTTP client.

        Uses HTTP client only - no local fallback. This ensures all data
        goes to a single authoritative ChromaDB instance and prevents
        data loss from writes going to different databases.

        Raises:
            ConnectionError: If ChromaDB service is unavailable.
        """
        # Check if existing connection is still valid
        self._ensure_connection()

        if self._client is None:
            import logging
            logger = logging.getLogger(__name__)

            try:
                http_client = self._create_http_client()
                # Test connection
                http_client.heartbeat()
                self._client = http_client
                logger.info(f"Connected to ChromaDB at {settings.chroma_host}:{settings.chroma_port}")
            except Exception as e:
                logger.error(
                    f"Failed to connect to ChromaDB at {settings.chroma_host}:{settings.chroma_port}: {e}"
                )
                raise ConnectionError(
                    f"ChromaDB service unavailable at {settings.chroma_host}:{settings.chroma_port}. "
                    "Ensure the ChromaDB container is running and healthy."
                ) from e
        return self._client

    @property
    def collection(self) -> chromadb.Collection:
        """Get or create the contract chunks collection."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={
                    "description": "Contract document chunks for RAG",
                    "hnsw:space": "cosine",
                },
            )
        return self._collection

    def reset_connection(self) -> None:
        """Force reconnection to ChromaDB on next access.

        Use this when you suspect the connection is stale or after
        ChromaDB service restarts.
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Resetting ChromaDB connection")
        self._client = None
        self._collection = None

    def health_check(self) -> bool:
        """Check if ChromaDB is reachable.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            # First ensure existing connection is valid
            self._ensure_connection()
            self.client.heartbeat()
            return True
        except Exception:
            return False

    def add_documents(
        self,
        texts: list[str],
        metadatas: list[ChunkMetadata],
        ids: list[str] | None = None,
    ) -> list[str]:
        """Add documents to the vector store.

        Args:
            texts: List of document texts to embed and store.
            metadatas: List of metadata for each document.
            ids: Optional list of IDs. Generated if not provided.

        Returns:
            List of document IDs.
        """
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]

        # Convert Pydantic models to dicts, filtering None values
        metadata_dicts = [
            {k: v for k, v in m.model_dump().items() if v is not None}
            for m in metadatas
        ]

        # Add to collection (ChromaDB handles embedding)
        self.collection.add(
            documents=texts,
            metadatas=metadata_dicts,
            ids=ids,
        )

        return ids

    def _build_rbac_filter(
        self,
        user_id: str | None = None,
        user_role: str | None = None,
    ) -> list[dict[str, Any]]:
        """Build RBAC filter conditions based on user role.

        Args:
            user_id: The current user's ID.
            user_role: The current user's role (admin, legal, procurement).

        Returns:
            List of filter conditions for RBAC.
        """
        if not user_role:
            # No role means no access (except public)
            return [{"access_level": AccessLevel.PUBLIC}]

        role_lower = user_role.lower()

        # Admin can access everything
        if role_lower == "admin":
            return []  # No RBAC filter needed

        # Build OR conditions for what this role can access
        access_conditions = [
            {"access_level": AccessLevel.PUBLIC},  # Everyone can access public
        ]

        # Role-specific access
        if role_lower == "legal":
            access_conditions.append({"access_level": AccessLevel.LEGAL})
            access_conditions.append({"allowed_roles": {"$contains": "legal"}})
        elif role_lower == "procurement":
            access_conditions.append({"access_level": AccessLevel.PROCUREMENT})
            access_conditions.append({"allowed_roles": {"$contains": "procurement"}})

        # User can always access their own uploads
        if user_id:
            access_conditions.append({"uploaded_by": user_id})

        return access_conditions

    def query_similar(
        self,
        query_text: str,
        top_k: int = 10,
        contract_id: str | None = None,
        clause_type: str | None = None,
        section_types: list[str] | None = None,
        semantic_tags: list[str] | None = None,
        user_id: str | None = None,
        user_role: str | None = None,
        tenant_id: str | None = None,
    ) -> list[QueryResult]:
        """Query for similar documents with semantic and RBAC filtering.

        Args:
            query_text: Text to search for.
            top_k: Number of results to return.
            contract_id: Optional filter by contract ID.
            clause_type: Optional filter by clause type.
            section_types: Optional list of section types (e.g., ["payment", "terms"]).
            semantic_tags: Optional list of semantic tags to match.
            user_id: Current user's ID for RBAC.
            user_role: Current user's role for RBAC (admin, legal, procurement).
            tenant_id: Tenant ID for isolation.

        Returns:
            List of QueryResult with matching documents the user can access.
        """
        # Build where filter
        conditions = []

        # Tenant filter
        if tenant_id:
            conditions.append({"tenant_id": tenant_id})

        # Content filters
        if contract_id:
            conditions.append({"contract_id": contract_id})
        if clause_type:
            conditions.append({"clause_type": clause_type})

        # Semantic section type filter (replaces regex-based detection)
        if section_types:
            if len(section_types) == 1:
                conditions.append({"section_type": section_types[0]})
            else:
                conditions.append({"section_type": {"$in": section_types}})

        # Semantic tags filter
        if semantic_tags:
            tag_conditions = [{"semantic_tags": {"$contains": tag}} for tag in semantic_tags]
            if len(tag_conditions) == 1:
                conditions.append(tag_conditions[0])
            else:
                conditions.append({"$or": tag_conditions})

        # RBAC filters
        rbac_conditions = self._build_rbac_filter(user_id, user_role)
        if rbac_conditions:
            if len(rbac_conditions) == 1:
                conditions.append(rbac_conditions[0])
            else:
                conditions.append({"$or": rbac_conditions})

        # Combine all conditions
        where_filter: dict[str, Any] | None = None
        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$and": conditions}

        # Query collection
        results = self.collection.query(
            query_texts=[query_text],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        # Parse results
        query_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                query_results.append(
                    QueryResult(
                        id=doc_id,
                        text=results["documents"][0][i] if results["documents"] else "",
                        metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                        distance=results["distances"][0][i] if results["distances"] else 0.0,
                    )
                )

        return query_results

    def delete_by_contract_id(self, contract_id: str) -> int:
        """Delete all chunks for a contract.

        Args:
            contract_id: The contract ID to delete chunks for.

        Returns:
            Number of chunks deleted.

        Raises:
            Exception: If deletion fails after retrieval.
        """
        import logging
        logger = logging.getLogger(__name__)

        # Ensure we have fresh collection reference
        collection = self.collection

        logger.info(f"Attempting to delete chunks for contract_id={contract_id}")

        # Get IDs to delete
        try:
            results = collection.get(
                where={"contract_id": contract_id},
                include=[],
            )
        except Exception as e:
            logger.error(f"Failed to query chunks for contract_id={contract_id}: {e}")
            raise

        if not results["ids"]:
            logger.info(f"No chunks found for contract_id={contract_id}")
            return 0

        ids_to_delete = results["ids"]
        count = len(ids_to_delete)
        logger.info(f"Found {count} chunks to delete for contract_id={contract_id}")

        # Delete by IDs
        try:
            collection.delete(ids=ids_to_delete)
            logger.info(f"Deleted {count} chunks for contract_id={contract_id}")
        except Exception as e:
            logger.error(f"Failed to delete chunks for contract_id={contract_id}: {e}")
            raise

        # Verify deletion
        verify_results = collection.get(
            where={"contract_id": contract_id},
            include=[],
        )
        if verify_results["ids"]:
            remaining = len(verify_results["ids"])
            logger.warning(f"Deletion incomplete: {remaining} chunks still exist for contract_id={contract_id}")
        else:
            logger.info(f"Verified: all chunks deleted for contract_id={contract_id}")

        return count

    def delete_by_ids(self, ids: list[str]) -> None:
        """Delete documents by their IDs.

        Args:
            ids: List of document IDs to delete.
        """
        if ids:
            self.collection.delete(ids=ids)

    def get_collection_stats(self) -> dict[str, Any]:
        """Get statistics about the collection.

        Returns:
            Dictionary with collection stats.
        """
        return {
            "name": self.COLLECTION_NAME,
            "count": self.collection.count(),
        }

    def cleanup_orphaned_documents(self, valid_contract_ids: set[str]) -> int:
        """Remove documents belonging to contracts not in the valid set.

        This is useful for cleaning up orphaned vectors when contract
        deletions fail to clean up ChromaDB properly.

        Args:
            valid_contract_ids: Set of contract IDs that should exist.

        Returns:
            Number of orphaned documents deleted.
        """
        import logging
        logger = logging.getLogger(__name__)

        # Get all documents from the collection
        all_results = self.collection.get(include=["metadatas"])

        if not all_results["ids"]:
            logger.info("No documents in collection to clean up")
            return 0

        # Find orphaned document IDs
        orphaned_ids = []
        for doc_id, metadata in zip(all_results["ids"], all_results["metadatas"] or []):
            contract_id = metadata.get("contract_id") if metadata else None
            if contract_id and contract_id not in valid_contract_ids:
                orphaned_ids.append(doc_id)

        if not orphaned_ids:
            logger.info("No orphaned documents found")
            return 0

        # Delete orphaned documents in batches
        batch_size = 100
        total_deleted = 0
        for i in range(0, len(orphaned_ids), batch_size):
            batch = orphaned_ids[i:i + batch_size]
            self.collection.delete(ids=batch)
            total_deleted += len(batch)
            logger.info(f"Deleted batch of {len(batch)} orphaned documents")

        logger.info(f"Cleaned up {total_deleted} orphaned documents")
        return total_deleted

    def get_all_contract_ids(self) -> set[str]:
        """Get all unique contract IDs in the vector store.

        Returns:
            Set of contract IDs.
        """
        all_results = self.collection.get(include=["metadatas"])

        contract_ids = set()
        if all_results["metadatas"]:
            for metadata in all_results["metadatas"]:
                if metadata and "contract_id" in metadata:
                    contract_ids.add(metadata["contract_id"])

        return contract_ids

    def check_access(
        self,
        contract_id: str,
        user_id: str | None = None,
        user_role: str | None = None,
    ) -> bool:
        """Check if a user has access to a contract's chunks.

        Args:
            contract_id: The contract ID to check access for.
            user_id: Current user's ID.
            user_role: Current user's role.

        Returns:
            True if user has access, False otherwise.
        """
        # Admin has access to everything
        if user_role and user_role.lower() == "admin":
            return True

        # Get one chunk from the contract to check access
        results = self.collection.get(
            where={"contract_id": contract_id},
            limit=1,
            include=["metadatas"],
        )

        if not results["ids"]:
            return False  # No chunks found

        metadata = results["metadatas"][0] if results["metadatas"] else {}
        access_level = metadata.get("access_level", AccessLevel.PUBLIC)
        uploaded_by = metadata.get("uploaded_by")
        allowed_roles = metadata.get("allowed_roles", "")

        # Check if user uploaded this document
        if user_id and uploaded_by == user_id:
            return True

        # Check access level
        if access_level == AccessLevel.PUBLIC:
            return True

        if not user_role:
            return False

        role_lower = user_role.lower()

        # Check role-based access
        if access_level == AccessLevel.LEGAL and role_lower == "legal":
            return True
        if access_level == AccessLevel.PROCUREMENT and role_lower == "procurement":
            return True

        # Check allowed_roles list
        if allowed_roles and role_lower in allowed_roles.split(","):
            return True

        return False

    def get_accessible_contracts(
        self,
        user_id: str | None = None,
        user_role: str | None = None,
        limit: int = 100,
    ) -> list[str]:
        """Get list of contract IDs the user can access.

        Args:
            user_id: Current user's ID.
            user_role: Current user's role.
            limit: Maximum number of contracts to return.

        Returns:
            List of accessible contract IDs.
        """
        # Build RBAC filter
        rbac_conditions = self._build_rbac_filter(user_id, user_role)

        where_filter: dict[str, Any] | None = None
        if rbac_conditions:
            if len(rbac_conditions) == 1:
                where_filter = rbac_conditions[0]
            else:
                where_filter = {"$or": rbac_conditions}

        # Get all chunks matching RBAC
        results = self.collection.get(
            where=where_filter,
            include=["metadatas"],
        )

        # Extract unique contract IDs
        contract_ids = set()
        if results["metadatas"]:
            for metadata in results["metadatas"]:
                if "contract_id" in metadata:
                    contract_ids.add(metadata["contract_id"])
                    if len(contract_ids) >= limit:
                        break

        return list(contract_ids)[:limit]

    def query_by_section_type(
        self,
        contract_id: str,
        section_types: list[str],
        top_k: int = 20,
    ) -> list[QueryResult]:
        """Query chunks by semantic section type.

        This replaces regex-based section searching with semantic queries.

        Args:
            contract_id: Contract to search within.
            section_types: Section types to retrieve (e.g., ["terms", "payment"]).
            top_k: Maximum results.

        Returns:
            List of QueryResult matching the section types.
        """
        # Build filter
        conditions = [{"contract_id": contract_id}]

        if len(section_types) == 1:
            conditions.append({"section_type": section_types[0]})
        else:
            conditions.append({"section_type": {"$in": section_types}})

        where_filter = {"$and": conditions}

        # Get matching chunks
        results = self.collection.get(
            where=where_filter,
            include=["documents", "metadatas"],
            limit=top_k,
        )

        query_results = []
        if results["ids"]:
            for i, doc_id in enumerate(results["ids"]):
                query_results.append(
                    QueryResult(
                        id=doc_id,
                        text=results["documents"][i] if results["documents"] else "",
                        metadata=results["metadatas"][i] if results["metadatas"] else {},
                        distance=0.0,  # Not a similarity query
                    )
                )

        return query_results

    def get_contract_sections_summary(self, contract_id: str) -> dict[str, int]:
        """Get count of chunks by section type for a contract.

        Args:
            contract_id: Contract ID.

        Returns:
            Dict mapping section_type to chunk count.
        """
        results = self.collection.get(
            where={"contract_id": contract_id},
            include=["metadatas"],
        )

        section_counts: dict[str, int] = {}
        if results["metadatas"]:
            for metadata in results["metadatas"]:
                section_type = metadata.get("section_type", "general")
                section_counts[section_type] = section_counts.get(section_type, 0) + 1

        return section_counts


# Singleton instance
vector_store = VectorStore()


def get_vector_store() -> VectorStore:
    """Get the vector store instance.

    Usage in FastAPI:
        @app.get("/search")
        async def search(vs: VectorStore = Depends(get_vector_store)):
            ...
    """
    return vector_store

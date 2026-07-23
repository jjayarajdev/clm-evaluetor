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
from app.services.few_shot_service import get_few_shot_context
from app.services.progress_tracker import (
    HealthRecorder,
    ProcessingStage,
    get_progress_tracker,
    new_health_recorder,
)
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


def _merge_prompt_addenda(hints: dict[str, str], tenant) -> dict[str, str]:
    """Append tenant-level prompt addenda (#27) onto the industry hints.

    Storage: ``tenant.config_overrides["prompt_addenda"]`` is a dict mapping
    agent-type keys (``metadata`` / ``clauses`` / ``obligations`` / ``slas``
    / ``risks``) to free-text instructions. Each addendum is appended to the
    corresponding entry in ``hints`` so every contract processed under this
    tenant sees the extra guidance, regardless of industry profile.
    """
    if not tenant or not tenant.config_overrides:
        return hints
    addenda = tenant.config_overrides.get("prompt_addenda") or {}
    if not isinstance(addenda, dict) or not addenda:
        return hints
    merged = dict(hints)
    for agent_key in ("metadata", "clauses", "obligations", "slas", "risks"):
        addendum = addenda.get(agent_key)
        if not addendum or not isinstance(addendum, str):
            continue
        addendum = addendum.strip()
        if not addendum:
            continue
        existing = merged.get(agent_key, "") or ""
        merged[agent_key] = (existing + "\n\n" + addendum).strip() if existing else addendum
    return merged


async def _load_extraction_hints(
    db: AsyncSession, tenant_id, contract_profile_id=None
) -> dict[str, str]:
    """Load industry-specific extraction hints.

    Resolution: contract profile → tenant profile, merged with tenant overrides
    AND per-tenant prompt addenda (#27).
    Returns dict like {"metadata": "...", "clauses": "...", "risks": "...", ...}
    or empty dict if nothing is configured.
    """
    if not tenant_id:
        return {}
    try:
        from sqlalchemy import select
        from app.models.industry_profile import IndustryProfile

        tenant = await db.get(Tenant, tenant_id)
        if not tenant:
            return {}

        # Contract-level profile takes priority
        profile_id = contract_profile_id or (
            tenant.industry_profile_id if tenant else None
        )

        hints: dict[str, str] = {}
        if profile_id:
            profile = await db.get(IndustryProfile, profile_id)
            if profile:
                # Merge with tenant overrides so custom hints are included
                merged = profile.get_merged_config(tenant.config_overrides)
                hints = merged.get("extraction_hints", {}) or {}

        # Tenant prompt addenda apply regardless of whether a profile is set
        return _merge_prompt_addenda(hints, tenant)
    except Exception as e:
        logger.debug(f"Extraction hints loading skipped: {e}")
    return {}


# Maps Industry enum values to keywords found in profile names/slugs, used
# to disambiguate when a contract type (e.g. "msa") exists in many profiles.
_INDUSTRY_PROFILE_KEYWORDS = {
    "technology": ["it ", "it_", "it-", "tech", "software", "digital"],
    "telecommunications": ["telecom", "it ", "tech"],
    "pharmaceutical": ["pharma", "life science"],
    "healthcare": ["health", "medi"],
    "manufacturing": ["manufactur"],
    "chemical": ["chemical"],
    "financial_services": ["financ", "bank", "insur"],
    "energy": ["energy", "utilit"],
    "aerospace_defense": ["aerospace", "defense"],
    "food_beverage": ["food", "beverage"],
    "automotive": ["automotive"],
    "retail": ["retail"],
    "construction": ["construction", "real estate", "vastgoed"],
}


async def _match_profile_for_contract_type(
    db: AsyncSession,
    contract_type: str | None,
    tenant_id=None,
    detected_industry: str | None = None,
):
    """Find the industry profile whose contract_types match the given type.

    Generic types (msa, sow, nda) exist in many profiles, so a bare
    first-match is wrong. Candidates are collected by match tier (exact code
    > code substring > exact label > description substring), then
    disambiguated: tenant's default profile wins, else a unique
    detected-industry keyword match, else a unique candidate. Ambiguity
    returns None — no assignment beats a wrong one.
    """
    from sqlalchemy import select
    from app.models.industry_profile import IndustryProfile

    if not contract_type:
        return None

    try:
        result = await db.execute(select(IndustryProfile))
        all_profiles = result.scalars().all()
    except Exception as e:
        logger.debug(f"Profile matching skipped: {e}")
        return None

    ct_lower = contract_type.strip().lower()
    tiers: list[list] = [[], [], [], []]
    for profile in all_profiles:
        if not profile.contract_types:
            continue
        codes = {(ct.get("code") or "").lower() for ct in profile.contract_types}
        labels = {(ct.get("label") or "").lower() for ct in profile.contract_types}
        descs = {(ct.get("description") or "").lower() for ct in profile.contract_types}

        if ct_lower in codes:
            tiers[0].append(profile)
        elif any(c and (ct_lower in c or c in ct_lower) for c in codes):
            tiers[1].append(profile)
        elif ct_lower in labels:
            tiers[2].append(profile)
        elif any(d and ct_lower in d for d in descs):
            tiers[3].append(profile)

    candidates = next((t for t in tiers if t), [])
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    # Tie-break 1: the tenant's default profile is the most likely context
    if tenant_id:
        tenant = await db.get(Tenant, tenant_id)
        if tenant and tenant.industry_profile_id:
            for profile in candidates:
                if profile.id == tenant.industry_profile_id:
                    return profile

    # Tie-break 2: unique match against the detected industry
    if detected_industry:
        keywords = _INDUSTRY_PROFILE_KEYWORDS.get(str(detected_industry).lower(), [])
        if keywords:
            hits = [
                p for p in candidates
                if any(kw in f"{p.name} {p.slug or ''}".lower() for kw in keywords)
            ]
            if len(hits) == 1:
                return hits[0]

    logger.info(
        f"Contract type '{contract_type}' is ambiguous across "
        f"{len(candidates)} profiles — not auto-assigning"
    )
    return None


async def _resolve_hints_for_contract(
    db: AsyncSession,
    tenant_id,
    contract_type: str | None,
    contract_profile_id=None,
) -> dict[str, str]:
    """Resolve the best extraction hints based on contract profile or detected type.

    Resolution order:
    1. Contract-level profile (if set) — always wins
    2. Best-matching profile by contract_type across all profiles
    3. Tenant's default profile

    All results are merged with tenant overrides so custom hints apply.
    """
    from sqlalchemy import select
    from app.models.industry_profile import IndustryProfile

    if not tenant_id:
        return {}

    # 1. Contract-level profile takes priority
    if contract_profile_id:
        return await _load_extraction_hints(db, tenant_id, contract_profile_id)

    # 2. Try to match contract_type against all profiles
    if not contract_type:
        return await _load_extraction_hints(db, tenant_id)

    best_profile = await _match_profile_for_contract_type(
        db, contract_type, tenant_id=tenant_id
    )
    if best_profile is None:
        return await _load_extraction_hints(db, tenant_id)

    tenant = await db.get(Tenant, tenant_id)
    tenant_profile_id = tenant.industry_profile_id if tenant else None

    if best_profile and best_profile.extraction_hints:
        if best_profile.id != tenant_profile_id:
            logger.info(
                f"Contract type '{contract_type}' matched profile "
                f"'{best_profile.name}' (tenant default: "
                f"{tenant_profile_id})"
            )
        # Merge with tenant overrides
        if tenant and tenant.config_overrides:
            merged = best_profile.get_merged_config(tenant.config_overrides)
            hints = merged.get("extraction_hints", {}) or {}
        else:
            hints = best_profile.extraction_hints or {}
        # Always apply tenant prompt addenda (#27) regardless of the profile path
        return _merge_prompt_addenda(hints, tenant)

    # 3. Fall back to tenant's assigned profile
    return await _load_extraction_hints(db, tenant_id)


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
        recorder = new_health_recorder()

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

            # Store extracted text immediately so it's available for
            # AI reference extraction, auto-link detection, and re-analysis
            # without re-parsing the document or wasting tokens.
            if parsed.full_text:
                contract.extracted_text = parsed.full_text
                await self.db.flush()

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

            # Build excluded parties list from tenant/client names + party aliases
            # so the AI doesn't set the uploader's own org as the counterparty
            excluded_parties: list[str] = []
            if contract.tenant_id:
                try:
                    tenant = await self.db.get(Tenant, contract.tenant_id)
                    if tenant and tenant.name:
                        excluded_parties.append(tenant.name)
                    # Load party aliases from tenant config_overrides
                    if tenant and tenant.config_overrides:
                        aliases = tenant.config_overrides.get("party_aliases", [])
                        if isinstance(aliases, list):
                            for alias in aliases:
                                if alias and alias not in excluded_parties:
                                    excluded_parties.append(alias)
                except Exception:
                    pass
            if contract.client_id:
                try:
                    from app.models.client import Client
                    client = await self.db.get(Client, contract.client_id)
                    if client and client.name and client.name not in excluded_parties:
                        excluded_parties.append(client.name)
                except Exception:
                    pass

            # Load industry-specific extraction hints (contract profile → tenant profile)
            extraction_hints = await _load_extraction_hints(
                self.db, contract.tenant_id, contract.industry_profile_id
            )

            # Build few-shot context from golden set
            meta_few_shot = ""
            if contract.tenant_id:
                try:
                    meta_few_shot = await get_few_shot_context(
                        self.db, contract.tenant_id, "metadata"
                    )
                    if meta_few_shot:
                        logger.info(f"Using golden-set few-shot examples for metadata extraction")
                except Exception as e:
                    logger.debug(f"Few-shot context skipped: {e}")

            # Load per-field confidence thresholds from tenant config.
            # Shape: tenant.config_overrides["confidence_thresholds"] = {
            #   "default": 0.7,
            #   "fields": {"counterparty": 0.85, "contract_value": 0.9, ...}
            # }
            field_thresholds: dict[str, float] | None = None
            default_threshold = 0.7
            if contract.tenant_id:
                try:
                    tenant_for_thresholds = await self.db.get(Tenant, contract.tenant_id)
                    overrides = (tenant_for_thresholds.config_overrides or {}) if tenant_for_thresholds else {}
                    ct_cfg = overrides.get("confidence_thresholds") or {}
                    if isinstance(ct_cfg.get("default"), (int, float)):
                        default_threshold = float(ct_cfg["default"])
                    fields_cfg = ct_cfg.get("fields") or {}
                    if isinstance(fields_cfg, dict) and fields_cfg:
                        field_thresholds = {k: float(v) for k, v in fields_cfg.items()
                                           if isinstance(v, (int, float))}
                except Exception:
                    pass

            try:
                metadata = await extract_metadata_with_fallback(
                    contract_text=full_text,
                    contract_id=str(contract.id),
                    user_id=user_id,
                    user_role=user_role,
                    excluded_parties=excluded_parties if excluded_parties else None,
                    few_shot_context=meta_few_shot,
                    tenant_id=str(contract.tenant_id) if contract.tenant_id else None,
                    industry_hint=extraction_hints.get("metadata", ""),
                )
                _, dropped_fields = await update_contract_metadata(
                    self.db, contract, metadata,
                    confidence_threshold=default_threshold,
                    excluded_parties=excluded_parties if excluded_parties else None,
                    field_thresholds=field_thresholds,
                )
                if dropped_fields:
                    logger.info(
                        f"Metadata thresholds dropped {len(dropped_fields)} field(s) for "
                        f"{contract.id}: {[d['field'] for d in dropped_fields]}"
                    )
                logger.info(f"Metadata extracted for contract {contract.id} (confidence: {metadata.overall_confidence:.2f})")
                tracker.update_progress(
                    contract_id, ProcessingStage.METADATA,
                    f"Metadata extracted (confidence: {metadata.overall_confidence:.0%})",
                    details={"counterparty": metadata.counterparty.value if metadata.counterparty else None}
                )
                meta_details: dict = {"confidence": round(metadata.overall_confidence, 2)}
                if dropped_fields:
                    meta_details["dropped_fields"] = dropped_fields
                recorder.success(ProcessingStage.METADATA, details=meta_details)
            except Exception as e:
                logger.warning(f"Metadata extraction failed for {contract.id}: {e}")
                recorder.failed(ProcessingStage.METADATA, error=str(e))

            # Signal-based industry detection (no LLM cost) — persisted as a
            # supporting signal and used to disambiguate profile matching.
            try:
                from app.services.industry_detector import IndustryDetector

                detection = await IndustryDetector(self.db).detect_industry(contract)
                if detection and detection.industry:
                    contract.detected_industry = detection.industry
                    contract.industry_confidence = detection.confidence
            except Exception as e:
                logger.debug(f"Industry detection skipped for {contract.id}: {e}")

            # Re-resolve extraction hints based on detected contract type.
            # The initial hints came from the tenant's default profile, but now
            # that we know the contract type we can pick the best-fit profile.
            if contract.contract_type:
                # Persist the matched profile on the contract itself so every
                # contract carries its own profile (never overwrite a manual
                # assignment). Deep analysis and later re-runs then use it via
                # resolution priority 1; the tenant profile is fallback only.
                if contract.industry_profile_id is None:
                    matched = await _match_profile_for_contract_type(
                        self.db,
                        contract.contract_type,
                        tenant_id=contract.tenant_id,
                        detected_industry=(
                            contract.detected_industry.value
                            if contract.detected_industry
                            else None
                        ),
                    )
                    if matched:
                        contract.industry_profile_id = matched.id
                        logger.info(
                            f"Auto-assigned profile '{matched.name}' to contract "
                            f"{contract.id} (type: {contract.contract_type})"
                        )

                resolved_hints = await _resolve_hints_for_contract(
                    self.db,
                    contract.tenant_id,
                    contract.contract_type,
                    contract_profile_id=contract.industry_profile_id,
                )
                if resolved_hints:
                    extraction_hints = resolved_hints

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
                        recorder.success(
                            ProcessingStage.CUSTOM_FIELDS,
                            details={"field_count": len(custom_fields) if custom_fields else 0},
                        )
                    else:
                        recorder.skipped(
                            ProcessingStage.CUSTOM_FIELDS,
                            reason="no custom field definitions on tenant",
                        )
                except Exception as e:
                    logger.warning(f"Custom field extraction failed for {contract.id}: {e}")
                    recorder.failed(ProcessingStage.CUSTOM_FIELDS, error=str(e))

            # Flush metadata changes before optional stages so they survive failures
            await self.db.flush()

            # Assess risk using AI agent
            tracker.update_progress(contract_id, ProcessingStage.RISK, "Assessing contract risks")
            logger.info(f"Assessing risk for contract {contract.id}")
            try:
                risk_result = await assess_risk(
                    contract_text=full_text,
                    contract_id=str(contract.id),
                    user_id=user_id,
                    industry_hint=extraction_hints.get("risks", ""),
                )
                await update_contract_risk(self.db, contract, risk_result)
                logger.info(f"Risk assessed for contract {contract.id}: {risk_result.risk_level}")
                tracker.update_progress(
                    contract_id, ProcessingStage.RISK,
                    f"Risk level: {risk_result.risk_level}",
                    details={"risk_level": risk_result.risk_level}
                )
                recorder.success(
                    ProcessingStage.RISK,
                    details={"risk_level": risk_result.risk_level},
                )
            except Exception as e:
                logger.warning(f"Risk assessment failed for {contract.id}: {e}")
                recorder.failed(ProcessingStage.RISK, error=str(e))

            # NOTE: Knowledge graph extraction is deferred to deep_analysis to avoid
            # FK violation errors that can poison the session and rollback metadata changes.
            # The KG extraction runs via _run_deep_analysis in the contracts router.
            tracker.update_progress(
                contract_id, ProcessingStage.KNOWLEDGE_GRAPH,
                "Deferred to deep analysis",
            )

            # Extract contract references (parent/child relationships) using AI
            try:
                from app.agents.contract_reference_extraction import (
                    extract_contract_references,
                    store_contract_references,
                )
                ref_result = await extract_contract_references(
                    contract_text=full_text,
                    filename=contract.filename,
                    contract_id=str(contract.id),
                    user_id=user_id,
                )
                await store_contract_references(self.db, contract, ref_result)
                ref_count = len(ref_result.parent_references) + len(ref_result.child_references)
                if ref_result.parent_references or ref_result.child_references:
                    logger.info(
                        f"Extracted references for {contract.id}: "
                        f"{len(ref_result.parent_references)} parent, "
                        f"{len(ref_result.child_references)} child"
                    )
                recorder.success("contract_references", details={"count": ref_count})
            except Exception as e:
                logger.warning(f"Contract reference extraction failed for {contract.id}: {e}")
                recorder.failed("contract_references", error=str(e))

            # Mark as completed
            contract.status = ContractStatus.COMPLETED
            await self.db.flush()

            # Invalidate dashboard caches for this tenant
            try:
                from app.services.metric_snapshot_service import invalidate_dashboard_cache
                await invalidate_dashboard_cache(self.db, contract.tenant_id)
            except Exception as e:
                logger.warning(f"Dashboard cache invalidation failed: {e}")

            # Run hierarchy detection to suggest related contracts
            try:
                from app.services.hierarchy_detection import detect_hierarchy

                # Gather tenant's completed contracts for pairwise analysis
                tenant_contracts = await self.db.execute(
                    select(Contract.id).where(
                        Contract.tenant_id == contract.tenant_id,
                        Contract.status == ContractStatus.COMPLETED,
                    ).order_by(Contract.created_at.desc()).limit(50)
                )
                contract_ids_for_hierarchy = list(tenant_contracts.scalars().all())

                if len(contract_ids_for_hierarchy) >= 2:
                    num_suggestions = await detect_hierarchy(
                        db=self.db,
                        contract_ids=contract_ids_for_hierarchy,
                        tenant_id=contract.tenant_id,
                        batch_id=f"indexer_{contract.id}",
                    )
                    if num_suggestions:
                        await self.db.flush()
                        logger.info(f"Hierarchy detection created {num_suggestions} suggestions for {contract.id}")
                    recorder.success("hierarchy_detection", details={"suggestions": num_suggestions or 0})
                else:
                    recorder.skipped(
                        "hierarchy_detection",
                        reason="fewer than 2 completed contracts to compare",
                    )
            except Exception as e:
                logger.warning(f"Hierarchy detection failed for {contract.id}: {e}")
                recorder.failed("hierarchy_detection", error=str(e))

            # Persist per-stage outcomes so silent failures are visible to tenants.
            # Deep analysis will augment this dict with its own stages later.
            contract.extraction_health = recorder.to_dict()
            await self.db.flush()

            # Update progress — indexer phase done, deep analysis will continue
            tracker.update_progress(
                contract_id, ProcessingStage.KNOWLEDGE_GRAPH,
                "Indexing complete — starting deep analysis",
                details={"indexer_complete": True}
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

        # KG cleanup is handled by the KG extractor itself (force_reextract=True)

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

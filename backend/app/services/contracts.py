"""Contract service for CRUD operations and search."""

import uuid as uuid_module
from datetime import date
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.clause import Clause
from app.models.contract import Contract, ContractStatus, RiskLevel
from app.models.obligation import Obligation
from app.services.vector_store import get_vector_store

logger = get_logger(__name__)


class ContractService:
    """Service for contract CRUD operations."""

    def __init__(
        self,
        db: AsyncSession,
        tenant_id: uuid_module.UUID | None = None,
        business_unit_id: uuid_module.UUID | None = None,
        user_role: str | None = None,
        bu_child_ids: list | None = None,
    ) -> None:
        """Initialize with database session and optional filters.

        Args:
            db: Database session.
            tenant_id: Tenant ID to filter by. If None, no tenant filtering is applied
                      (used by super-admin or system operations).
            business_unit_id: Business unit ID to filter by. Only applies for certain roles.
            user_role: User's role for BU-aware filtering.
            bu_child_ids: List of child BU IDs for BU_HEAD role hierarchical access.
        """
        self.db = db
        self.tenant_id = tenant_id
        self.business_unit_id = business_unit_id
        self.user_role = user_role
        self.bu_child_ids = bu_child_ids
        self.vector_store = get_vector_store()

    def _apply_tenant_filter(self, query):
        """Apply tenant filter to a query if tenant_id is set."""
        if self.tenant_id is not None:
            return query.where(Contract.tenant_id == self.tenant_id)
        return query

    def _apply_bu_filter(self, query):
        """Apply business unit filter based on user role.

        Role hierarchy:
        - SUPER_ADMIN: No BU filter (sees all)
        - ADMIN: No BU filter within tenant (sees all in tenant)
        - BU_HEAD: Sees all contracts in their BU and child BUs
        - LEGAL/PROCUREMENT/VIEWER: Sees contracts in their BU only, or all if no BU assigned
        """
        from sqlalchemy import or_
        from app.models.user import Role

        # Super admin and tenant admin see everything
        if self.user_role in [Role.SUPER_ADMIN.value, Role.ADMIN.value, "super_admin", "admin"]:
            return query

        # If user has no BU assigned, they can see all (legacy behavior)
        if self.business_unit_id is None:
            return query

        # BU_HEAD sees their BU and child BUs
        if self.user_role in [Role.BU_HEAD.value, "bu_head"]:
            all_bu_ids = [self.business_unit_id] + list(self.bu_child_ids or [])
            return query.where(
                or_(
                    Contract.business_unit_id.in_(all_bu_ids),
                    Contract.business_unit_id.is_(None),
                )
            )

        # Other roles see only their BU or unassigned
        return query.where(
            or_(
                Contract.business_unit_id == self.business_unit_id,
                Contract.business_unit_id.is_(None),
            )
        )

    async def get_contract(
        self,
        contract_id: str,
        include_clauses: bool = True,
        include_obligations: bool = True,
    ) -> Contract | None:
        """Get a contract by ID with optional related data.

        Args:
            contract_id: Contract ID.
            include_clauses: Whether to load clauses.
            include_obligations: Whether to load obligations.

        Returns:
            Contract or None if not found (or not accessible by tenant).
        """
        query = select(Contract).where(Contract.id == uuid_module.UUID(contract_id))

        # Apply tenant filter
        query = self._apply_tenant_filter(query)

        # Apply BU filter
        query = self._apply_bu_filter(query)

        if include_clauses:
            query = query.options(selectinload(Contract.clauses))
        if include_obligations:
            query = query.options(selectinload(Contract.obligations))
        # Always load SLAs for sla_count in response
        query = query.options(selectinload(Contract.slas))

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_contracts(
        self,
        page: int = 1,
        page_size: int = 20,
        contract_type: str | None = None,
        counterparty: str | None = None,
        risk_level: RiskLevel | None = None,
        status: ContractStatus | None = None,
        expiration_before: date | None = None,
        expiration_after: date | None = None,
        search: str | None = None,
        client_id: str | None = None,
        sort_by: str = "created_at",
        sort_desc: bool = True,
    ) -> tuple[list[Contract], int]:
        """List contracts with filters and pagination.

        Args:
            page: Page number (1-indexed).
            page_size: Number of items per page.
            contract_type: Filter by contract type.
            counterparty: Filter by counterparty (partial match).
            risk_level: Filter by risk level.
            status: Filter by status.
            expiration_before: Filter by expiration date (before).
            expiration_after: Filter by expiration date (after).
            search: Search in filename and counterparty.
            client_id: Filter by client ID.
            sort_by: Field to sort by.
            sort_desc: Sort descending if True.

        Returns:
            Tuple of (contracts, total_count).
        """
        # Base query with tenant and BU filters
        query = select(Contract)
        query = self._apply_tenant_filter(query)
        query = self._apply_bu_filter(query)

        # Apply filters
        if contract_type:
            query = query.where(Contract.contract_type == contract_type)
        if counterparty:
            query = query.where(Contract.counterparty.ilike(f"%{counterparty}%"))
        if risk_level:
            query = query.where(Contract.risk_level == risk_level)
        if status:
            query = query.where(Contract.status == status)
        if expiration_before:
            query = query.where(Contract.expiration_date <= expiration_before)
        if expiration_after:
            query = query.where(Contract.expiration_date >= expiration_after)
        if search:
            search_filter = (
                Contract.filename.ilike(f"%{search}%") |
                Contract.counterparty.ilike(f"%{search}%")
            )
            query = query.where(search_filter)
        if client_id:
            query = query.where(Contract.client_id == uuid_module.UUID(client_id))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        sort_column = getattr(Contract, sort_by, Contract.created_at)
        if sort_desc:
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self.db.execute(query)
        contracts = list(result.scalars().all())

        return contracts, total

    async def search_contracts(
        self,
        query_text: str,
        user_id: str | None = None,
        user_role: str | None = None,
        n_results: int = 20,
    ) -> list[dict[str, Any]]:
        """Search contracts using vector similarity.

        Args:
            query_text: Search query.
            user_id: User ID for RBAC.
            user_role: User role for RBAC.
            n_results: Maximum results to return.

        Returns:
            List of search results with contract info.
        """
        # Search vector store
        results = self.vector_store.query_similar(
            query_text=query_text,
            n_results=n_results,
            user_id=user_id,
            user_role=user_role,
        )

        # Group by contract and get details
        contract_scores: dict[str, float] = {}
        for result in results:
            if result.contract_id not in contract_scores:
                contract_scores[result.contract_id] = result.distance
            else:
                # Keep best score (lowest distance)
                contract_scores[result.contract_id] = min(
                    contract_scores[result.contract_id],
                    result.distance,
                )

        # Get contract details
        search_results = []
        for contract_id, score in sorted(contract_scores.items(), key=lambda x: x[1]):
            contract = await self.get_contract(
                contract_id, include_clauses=False, include_obligations=False
            )
            if contract:
                search_results.append({
                    "contract": contract,
                    "relevance_score": 1 - score,  # Convert distance to similarity
                })

        return search_results

    async def delete_contract(self, contract_id: str) -> bool:
        """Delete a contract and all associated data.

        Cleans up:
        - Vector store (ChromaDB)
        - All related database records (clauses, obligations, SLAs, etc.)
        - Physical file from disk

        Args:
            contract_id: Contract ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        from pathlib import Path
        from app.models.sla import ContractSLA
        from app.models.definition import ContractDefinition
        from app.models.exhibit import ContractExhibit
        from app.models.preamble import ContractPreamble
        from app.models.process_step import ContractProcessStep
        from app.models.key_date import ContractKeyDate
        from app.models.party import ContractParty
        from app.models.financial import ContractFinancial

        contract = await self.get_contract(
            contract_id, include_clauses=False, include_obligations=False
        )
        if not contract:
            return False

        contract_uuid = contract.id
        file_path = contract.file_path
        filename = contract.filename

        logger.info(
            "Deleting contract and all associated data",
            contract_id=contract_id,
            filename=filename,
        )

        # 1. Delete from vector store (ChromaDB)
        try:
            deleted_chunks = self.vector_store.delete_by_contract_id(contract_id)
            logger.info(
                "Deleted chunks from vector store",
                contract_id=contract_id,
                chunks_deleted=deleted_chunks,
            )
        except Exception as e:
            # Log full exception details for debugging
            logger.error(
                "Vector store cleanup failed - this may leave orphaned data",
                contract_id=contract_id,
                error=str(e),
                exc_info=True,
            )
            # Continue with database deletion even if vector store fails
            # The orphaned vectors can be cleaned up later

        # 2. Delete all related database records
        related_tables = [
            (Clause, "clauses"),
            (Obligation, "obligations"),
            (ContractSLA, "SLAs"),
            (ContractDefinition, "definitions"),
            (ContractExhibit, "exhibits"),
            (ContractPreamble, "preambles"),
            (ContractProcessStep, "process steps"),
            (ContractKeyDate, "key dates"),
            (ContractParty, "parties"),
            (ContractFinancial, "financial terms"),
        ]

        deleted_records = {}
        for model, name in related_tables:
            try:
                result = await self.db.execute(
                    delete(model).where(model.contract_id == contract_uuid)
                )
                if result.rowcount:
                    deleted_records[name] = result.rowcount
            except Exception as e:
                logger.warning(
                    f"Failed to delete {name}",
                    contract_id=contract_id,
                    table=name,
                    error=str(e),
                )

        if deleted_records:
            logger.info(
                "Deleted related database records",
                contract_id=contract_id,
                records=deleted_records,
            )

        # 3. Delete the contract record
        await self.db.delete(contract)
        await self.db.flush()

        # 4. Delete physical file and folder from disk
        if file_path:
            try:
                path = Path(file_path)
                if path.exists():
                    path.unlink()
                    logger.info(
                        "Deleted physical file",
                        contract_id=contract_id,
                        file=path.name,
                    )

                    # Delete parent folder if empty
                    parent = path.parent
                    if parent.exists() and not any(parent.iterdir()):
                        parent.rmdir()
                        logger.info(
                            "Deleted empty folder",
                            contract_id=contract_id,
                            folder=parent.name,
                        )
            except Exception as e:
                logger.warning(
                    "File cleanup failed",
                    contract_id=contract_id,
                    error=str(e),
                )

        logger.info(
            "Contract deleted successfully",
            contract_id=contract_id,
            filename=filename,
        )
        return True

    async def get_contract_stats(self) -> dict[str, Any]:
        """Get aggregate statistics about contracts.

        Returns:
            Dictionary with various statistics.
        """
        stats = {}

        # Build base filters based on tenant
        base_filter = []
        if self.tenant_id is not None:
            base_filter.append(Contract.tenant_id == self.tenant_id)

        # Count by type
        type_query = select(Contract.contract_type, func.count(Contract.id)).group_by(Contract.contract_type)
        for f in base_filter:
            type_query = type_query.where(f)
        type_result = await self.db.execute(type_query)
        stats["by_type"] = {
            (t.value if t else "unknown"): c
            for t, c in type_result.all()
        }

        # Count by status
        status_query = select(Contract.status, func.count(Contract.id)).group_by(Contract.status)
        for f in base_filter:
            status_query = status_query.where(f)
        status_result = await self.db.execute(status_query)
        stats["by_status"] = {
            s.value: c for s, c in status_result.all()
        }

        # Count by risk level
        risk_query = (
            select(Contract.risk_level, func.count(Contract.id))
            .where(Contract.risk_level.isnot(None))
            .group_by(Contract.risk_level)
        )
        for f in base_filter:
            risk_query = risk_query.where(f)
        risk_result = await self.db.execute(risk_query)
        stats["by_risk"] = {
            r.value: c for r, c in risk_result.all()
        }

        # Total counts
        total_query = select(func.count(Contract.id))
        for f in base_filter:
            total_query = total_query.where(f)
        total_result = await self.db.execute(total_query)
        stats["total"] = total_result.scalar() or 0

        return stats

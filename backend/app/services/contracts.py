"""Contract service for CRUD operations and search."""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.clause import Clause
from app.models.contract import Contract, ContractStatus, ContractType, RiskLevel
from app.models.obligation import Obligation
from app.services.vector_store import get_vector_store


class ContractService:
    """Service for contract CRUD operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session."""
        self.db = db
        self.vector_store = get_vector_store()

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
            Contract or None if not found.
        """
        query = select(Contract).where(Contract.id == uuid.UUID(contract_id))

        if include_clauses:
            query = query.options(selectinload(Contract.clauses))
        if include_obligations:
            query = query.options(selectinload(Contract.obligations))

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_contracts(
        self,
        page: int = 1,
        page_size: int = 20,
        contract_type: ContractType | None = None,
        counterparty: str | None = None,
        risk_level: RiskLevel | None = None,
        status: ContractStatus | None = None,
        expiration_before: date | None = None,
        expiration_after: date | None = None,
        search: str | None = None,
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
            sort_by: Field to sort by.
            sort_desc: Sort descending if True.

        Returns:
            Tuple of (contracts, total_count).
        """
        # Base query
        query = select(Contract)

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

        Args:
            contract_id: Contract ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        contract = await self.get_contract(
            contract_id, include_clauses=False, include_obligations=False
        )
        if not contract:
            return False

        # Delete from vector store
        try:
            self.vector_store.delete_by_contract_id(contract_id)
        except Exception:
            pass  # Best effort

        # Delete related records
        await self.db.execute(
            delete(Clause).where(Clause.contract_id == contract.id)
        )
        await self.db.execute(
            delete(Obligation).where(Obligation.contract_id == contract.id)
        )

        # Delete contract
        await self.db.delete(contract)
        await self.db.flush()

        return True

    async def get_contract_stats(self) -> dict[str, Any]:
        """Get aggregate statistics about contracts.

        Returns:
            Dictionary with various statistics.
        """
        stats = {}

        # Count by type
        type_result = await self.db.execute(
            select(Contract.contract_type, func.count(Contract.id))
            .group_by(Contract.contract_type)
        )
        stats["by_type"] = {
            (t.value if t else "unknown"): c
            for t, c in type_result.all()
        }

        # Count by status
        status_result = await self.db.execute(
            select(Contract.status, func.count(Contract.id))
            .group_by(Contract.status)
        )
        stats["by_status"] = {
            s.value: c for s, c in status_result.all()
        }

        # Count by risk level
        risk_result = await self.db.execute(
            select(Contract.risk_level, func.count(Contract.id))
            .where(Contract.risk_level.isnot(None))
            .group_by(Contract.risk_level)
        )
        stats["by_risk"] = {
            r.value: c for r, c in risk_result.all()
        }

        # Total counts
        total_result = await self.db.execute(
            select(func.count(Contract.id))
        )
        stats["total"] = total_result.scalar() or 0

        return stats

"""Shared tenant isolation utilities.

Provides a generic apply_tenant_filter function that works with any
SQLAlchemy model that has a tenant_id column, plus specialized variants
for models that require joins to reach the tenant scope.

Also provides apply_bu_filter for business-unit-level access control.
"""

import uuid
from typing import Any

from sqlalchemy import Select, or_


def apply_tenant_filter(
    query: Select,
    tenant_id: uuid.UUID | None,
    model: Any,
) -> Select:
    """Apply tenant isolation filter to a query.

    For models with a direct tenant_id column (Contract, Organization,
    BusinessRelationship, Client, ServicePortfolio, etc.).

    Super admins pass tenant_id=None and see all tenants.

    Args:
        query: SQLAlchemy select statement.
        tenant_id: Tenant UUID or None for super admin.
        model: SQLAlchemy model class with a tenant_id column.

    Returns:
        Filtered query.
    """
    if tenant_id is not None:
        return query.where(model.tenant_id == tenant_id)
    return query


def apply_tenant_filter_via_join(
    query: Select,
    tenant_id: uuid.UUID | None,
    source_model: Any,
    join_model: Any,
    join_condition: Any,
    tenant_model: Any | None = None,
) -> Select:
    """Apply tenant filter through a join chain.

    For models that don't have a direct tenant_id column and must
    join through related models (e.g., Obligation -> Contract,
    SLAAlert -> Contract, KPI -> BusinessRelationship -> Organization).

    Args:
        query: SQLAlchemy select statement.
        tenant_id: Tenant UUID or None for super admin.
        source_model: The model being queried (e.g., Obligation).
        join_model: The model to join to (e.g., Contract).
        join_condition: The join ON clause.
        tenant_model: Model with tenant_id column (defaults to join_model).

    Returns:
        Filtered query with join applied.
    """
    if tenant_id is not None:
        target = tenant_model or join_model
        return query.join(join_model, join_condition).where(
            target.tenant_id == tenant_id
        )
    return query


def apply_bu_filter(
    query: Select,
    business_unit_id: uuid.UUID | None,
    user_role: str | None,
    model: Any = None,
) -> Select:
    """Apply business unit filter to a query.

    Admin and super_admin roles see all contracts regardless of BU.
    Other roles see only contracts in their BU or unassigned contracts.
    Users without a BU assigned see all contracts (legacy behavior).

    Args:
        query: SQLAlchemy select statement.
        business_unit_id: User's business unit UUID, or None if unassigned.
        user_role: User's role value string (e.g., 'admin', 'legal').
        model: SQLAlchemy model class with a business_unit_id column.
               Defaults to Contract if not specified.

    Returns:
        Filtered query.
    """
    # Admin and super_admin see everything
    if not business_unit_id or user_role in ("admin", "super_admin"):
        return query

    if model is None:
        from app.models.contract import Contract
        model = Contract

    return query.where(
        or_(
            model.business_unit_id == business_unit_id,
            model.business_unit_id.is_(None),
        )
    )

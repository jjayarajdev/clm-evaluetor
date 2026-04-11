"""Shared pagination utilities.

Provides a standard paginated response format and helper function
for consistent pagination across all list endpoints.
"""

import math
from typing import Any, TypeVar, Generic

from fastapi import Query
from pydantic import BaseModel


class PaginationParams:
    """Standard pagination parameters for list endpoints.

    Usage in router:
        async def list_items(
            pagination: PaginationParams = Depends(),
        ):
            ...
            query = pagination.apply(query)
            total = await get_total(...)
            return pagination.response(items, total)
    """

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    def apply(self, query):
        """Apply offset/limit to a SQLAlchemy query."""
        return query.offset(self.offset).limit(self.page_size)

    def response(self, items: list, total: int) -> dict[str, Any]:
        """Build a standard paginated response dict."""
        return {
            "items": items,
            "total": total,
            "page": self.page,
            "page_size": self.page_size,
            "pages": math.ceil(total / self.page_size) if self.page_size > 0 else 0,
        }


class PaginatedResponse(BaseModel):
    """Standard paginated response schema.

    Use as a base for typed paginated responses:
        class ContractListResponse(PaginatedResponse):
            items: list[ContractSummary]
    """
    items: list[Any] = []
    total: int
    page: int
    page_size: int
    pages: int

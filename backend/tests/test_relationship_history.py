"""Tests for Relationship Performance Status History functionality."""

import pytest
import uuid
from datetime import datetime
from decimal import Decimal

from app.models.relationship_history import (
    RelationshipStatusHistory,
    PerformanceStatus,
)
from app.schemas.relationship_history import (
    RelationshipHistoryCreate,
    RelationshipHistoryResponse,
    PerformanceTrendPoint,
)


class TestPerformanceStatus:
    """Tests for PerformanceStatus enum."""

    def test_all_statuses(self):
        """Test all expected performance statuses exist."""
        expected = ["excellent", "good", "acceptable", "concerning", "poor", "critical"]
        actual = [s.value for s in PerformanceStatus]
        for status in expected:
            assert status in actual
        assert len(actual) == len(expected)


class TestRelationshipStatusHistory:
    """Tests for RelationshipStatusHistory model."""

    def test_create_history(self):
        """Test RelationshipStatusHistory model creation with all fields."""
        rel_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        history = RelationshipStatusHistory(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            relationship_id=rel_id,
            status="good",
            previous_status="acceptable",
            overall_score=Decimal("75.50"),
            period="2024-Q2",
            recorded_by=user_id,
            notes="Improved after corrective action plan",
            trigger="kpi_evaluation_cycle",
        )
        assert history.relationship_id == rel_id
        assert history.tenant_id == tenant_id
        assert history.status == "good"
        assert history.previous_status == "acceptable"
        assert history.overall_score == Decimal("75.50")
        assert history.period == "2024-Q2"
        assert history.recorded_by == user_id
        assert history.notes == "Improved after corrective action plan"
        assert history.trigger == "kpi_evaluation_cycle"

    def test_history_repr(self):
        """Test RelationshipStatusHistory string representation."""
        rel_id = uuid.uuid4()
        history = RelationshipStatusHistory(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            relationship_id=rel_id,
            status="critical",
            period="2024-Q4",
        )
        result = repr(history)
        assert "critical" in result
        assert "2024-Q4" in result

    def test_status_transition(self):
        """Test creating a history entry with status and previous_status."""
        history = RelationshipStatusHistory(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            relationship_id=uuid.uuid4(),
            status="poor",
            previous_status="concerning",
            period="2024-Q3",
        )
        assert history.status == "poor"
        assert history.previous_status == "concerning"


class TestRelationshipHistorySchemas:
    """Tests for Relationship History Pydantic schemas."""

    def test_create_schema(self):
        """Test RelationshipHistoryCreate schema validation."""
        data = RelationshipHistoryCreate(
            status=PerformanceStatus.GOOD,
            previous_status=PerformanceStatus.ACCEPTABLE,
            overall_score=Decimal("82.00"),
            period="2024-Q1",
            notes="Quarterly review completed",
            trigger="manual",
        )
        assert data.status == PerformanceStatus.GOOD
        assert data.previous_status == PerformanceStatus.ACCEPTABLE
        assert data.overall_score == Decimal("82.00")
        assert data.period == "2024-Q1"
        assert data.notes == "Quarterly review completed"
        assert data.trigger == "manual"

    def test_response_schema(self):
        """Test RelationshipHistoryResponse model_validate."""
        history_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        rel_id = uuid.uuid4()
        now = datetime.utcnow()
        data = RelationshipHistoryResponse.model_validate({
            "id": history_id,
            "tenant_id": tenant_id,
            "relationship_id": rel_id,
            "status": PerformanceStatus.EXCELLENT,
            "previous_status": PerformanceStatus.GOOD,
            "overall_score": Decimal("92.50"),
            "period": "2024-Q4",
            "recorded_date": now,
            "recorded_by": None,
            "notes": "Outstanding performance",
            "trigger": "kpi_evaluation_cycle",
            "created_at": now,
            "recorded_by_name": None,
        })
        assert data.id == history_id
        assert data.status == PerformanceStatus.EXCELLENT
        assert data.previous_status == PerformanceStatus.GOOD
        assert data.overall_score == Decimal("92.50")

    def test_performance_trend_point(self):
        """Test PerformanceTrendPoint schema validation."""
        point = PerformanceTrendPoint(
            period="2024-Q1",
            score=Decimal("85.00"),
            status=PerformanceStatus.GOOD,
        )
        assert point.period == "2024-Q1"
        assert point.score == Decimal("85.00")
        assert point.status == PerformanceStatus.GOOD

    def test_performance_trend_point_no_score(self):
        """Test PerformanceTrendPoint without score (optional)."""
        point = PerformanceTrendPoint(
            period="2024-Q2",
            status=PerformanceStatus.ACCEPTABLE,
        )
        assert point.score is None
        assert point.status == PerformanceStatus.ACCEPTABLE

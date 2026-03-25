"""Tests for KPI Approval Workflow functionality."""

import pytest
import uuid
from datetime import datetime
from decimal import Decimal

from app.models.kpi import (
    PerceptionScore,
    ScoreApprovalStatus,
)
from app.schemas.kpi import (
    PerceptionScoreResponse,
    ScoreApprovalAction,
)


class TestScoreApprovalStatus:
    """Tests for ScoreApprovalStatus enum."""

    def test_all_statuses(self):
        """Test all expected approval statuses exist."""
        expected = ["draft", "pending_approval", "approved", "rejected"]
        actual = [s.value for s in ScoreApprovalStatus]
        for status in expected:
            assert status in actual
        assert len(actual) == len(expected)


class TestPerceptionScoreApproval:
    """Tests for PerceptionScore model approval fields."""

    def test_score_with_approval_fields(self):
        """Test creating a PerceptionScore with approval-related fields."""
        approver_id = uuid.uuid4()
        approved_at = datetime.utcnow()
        score = PerceptionScore(
            id=uuid.uuid4(),
            kpi_id=uuid.uuid4(),
            scorer_org_id=uuid.uuid4(),
            scored_by_user_id=uuid.uuid4(),
            score=Decimal("7.5"),
            period="2024-Q1",
            comments="Good performance overall",
            is_internal=True,
            approval_status="approved",
            approved_by=approver_id,
            approved_at=approved_at,
            approval_comments="Verified and approved",
        )
        assert score.approval_status == "approved"
        assert score.approved_by == approver_id
        assert score.approved_at == approved_at
        assert score.approval_comments == "Verified and approved"

    def test_default_approval_status(self):
        """Test PerceptionScore default approval_status is 'pending_approval'."""
        approval_col = PerceptionScore.__table__.columns["approval_status"]
        assert approval_col.default.arg == "pending_approval"


class TestPerceptionScoreResponseSchema:
    """Tests for PerceptionScoreResponse schema approval fields."""

    def test_response_includes_approval_fields(self):
        """Test that approval fields are present in the response schema."""
        score_id = uuid.uuid4()
        kpi_id = uuid.uuid4()
        org_id = uuid.uuid4()
        approver_id = uuid.uuid4()
        now = datetime.utcnow()
        data = PerceptionScoreResponse.model_validate({
            "id": score_id,
            "kpi_id": kpi_id,
            "scorer_org_id": org_id,
            "scored_by_user_id": None,
            "score": Decimal("8.0"),
            "period": "2024-Q2",
            "comments": "Excellent delivery",
            "is_internal": True,
            "scored_at": now,
            "approval_status": ScoreApprovalStatus.APPROVED,
            "approved_by": approver_id,
            "approved_at": now,
            "approval_comments": "Approved after review",
        })
        assert data.approval_status == ScoreApprovalStatus.APPROVED
        assert data.approved_by == approver_id
        assert data.approved_at == now
        assert data.approval_comments == "Approved after review"

    def test_response_approval_fields_optional(self):
        """Test that approval fields are optional in the response schema."""
        score_id = uuid.uuid4()
        now = datetime.utcnow()
        data = PerceptionScoreResponse.model_validate({
            "id": score_id,
            "kpi_id": uuid.uuid4(),
            "scorer_org_id": uuid.uuid4(),
            "score": Decimal("6.0"),
            "period": "2024-Q3",
            "is_internal": False,
            "scored_at": now,
        })
        assert data.approval_status is None
        assert data.approved_by is None
        assert data.approved_at is None
        assert data.approval_comments is None


class TestScoreApprovalActionSchema:
    """Tests for ScoreApprovalAction schema."""

    def test_approve_action(self):
        """Test ScoreApprovalAction with comments."""
        action = ScoreApprovalAction(
            comments="Reviewed and approved for Q1 reporting",
        )
        assert action.comments == "Reviewed and approved for Q1 reporting"

    def test_approve_action_no_comments(self):
        """Test ScoreApprovalAction without comments (optional)."""
        action = ScoreApprovalAction()
        assert action.comments is None

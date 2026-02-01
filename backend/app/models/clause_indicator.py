"""Contract clause indicators model - boolean flags for clause presence."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Boolean, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.contract import Contract


class ContractClauseIndicator(Base, UUIDMixin, TimestampMixin):
    """Boolean indicators for presence/absence of standard contract clauses.

    This enables quick filtering and risk assessment without full-text search.
    Each boolean indicates whether the clause is present (True), absent (False),
    or unknown (None).
    """

    __tablename__ = "contract_clause_indicators"

    # Foreign key to contract (one-to-one relationship)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One-to-one
        index=True,
    )

    # ===== CONFIDENTIALITY & IP =====
    has_confidentiality: Mapped[bool | None] = mapped_column(Boolean)
    confidentiality_term_years: Mapped[int | None] = mapped_column()
    has_mutual_confidentiality: Mapped[bool | None] = mapped_column(Boolean)
    has_ip_ownership: Mapped[bool | None] = mapped_column(Boolean)
    ip_ownership_party: Mapped[str | None] = mapped_column(String(100))  # provider/client/joint
    has_ip_license: Mapped[bool | None] = mapped_column(Boolean)
    has_work_for_hire: Mapped[bool | None] = mapped_column(Boolean)

    # ===== LIABILITY & INDEMNIFICATION =====
    has_limitation_of_liability: Mapped[bool | None] = mapped_column(Boolean)
    has_liability_cap: Mapped[bool | None] = mapped_column(Boolean)
    has_indemnification: Mapped[bool | None] = mapped_column(Boolean)
    has_mutual_indemnification: Mapped[bool | None] = mapped_column(Boolean)
    has_warranty_disclaimer: Mapped[bool | None] = mapped_column(Boolean)
    has_as_is_disclaimer: Mapped[bool | None] = mapped_column(Boolean)

    # ===== TERMINATION & RENEWAL =====
    has_termination_for_cause: Mapped[bool | None] = mapped_column(Boolean)
    has_termination_for_convenience: Mapped[bool | None] = mapped_column(Boolean)
    has_termination_notice_period: Mapped[bool | None] = mapped_column(Boolean)
    has_auto_renewal: Mapped[bool | None] = mapped_column(Boolean)
    has_renewal_notice_requirement: Mapped[bool | None] = mapped_column(Boolean)

    # ===== FORCE MAJEURE & DISPUTES =====
    has_force_majeure: Mapped[bool | None] = mapped_column(Boolean)
    has_governing_law: Mapped[bool | None] = mapped_column(Boolean)
    has_dispute_resolution: Mapped[bool | None] = mapped_column(Boolean)
    has_arbitration: Mapped[bool | None] = mapped_column(Boolean)
    has_mediation: Mapped[bool | None] = mapped_column(Boolean)
    has_exclusive_jurisdiction: Mapped[bool | None] = mapped_column(Boolean)

    # ===== COMPLIANCE & REGULATORY =====
    has_data_protection: Mapped[bool | None] = mapped_column(Boolean)
    has_gdpr_compliance: Mapped[bool | None] = mapped_column(Boolean)
    has_ccpa_compliance: Mapped[bool | None] = mapped_column(Boolean)
    has_hipaa_compliance: Mapped[bool | None] = mapped_column(Boolean)
    has_pci_compliance: Mapped[bool | None] = mapped_column(Boolean)
    has_soc2_compliance: Mapped[bool | None] = mapped_column(Boolean)
    has_anticorruption: Mapped[bool | None] = mapped_column(Boolean)
    has_fcpa_compliance: Mapped[bool | None] = mapped_column(Boolean)
    has_sanctions_compliance: Mapped[bool | None] = mapped_column(Boolean)
    has_export_control: Mapped[bool | None] = mapped_column(Boolean)

    # ===== BUSINESS RESTRICTIONS =====
    has_non_compete: Mapped[bool | None] = mapped_column(Boolean)
    non_compete_duration_months: Mapped[int | None] = mapped_column()
    has_non_solicit: Mapped[bool | None] = mapped_column(Boolean)
    non_solicit_duration_months: Mapped[int | None] = mapped_column()
    has_exclusivity: Mapped[bool | None] = mapped_column(Boolean)
    has_most_favored_nation: Mapped[bool | None] = mapped_column(Boolean)

    # ===== OPERATIONAL =====
    has_insurance_requirement: Mapped[bool | None] = mapped_column(Boolean)
    has_audit_rights: Mapped[bool | None] = mapped_column(Boolean)
    has_service_levels: Mapped[bool | None] = mapped_column(Boolean)
    has_sla_credits: Mapped[bool | None] = mapped_column(Boolean)
    has_change_control: Mapped[bool | None] = mapped_column(Boolean)
    has_assignment_restriction: Mapped[bool | None] = mapped_column(Boolean)
    has_subcontracting_restriction: Mapped[bool | None] = mapped_column(Boolean)

    # ===== PAYMENT =====
    has_payment_terms: Mapped[bool | None] = mapped_column(Boolean)
    has_late_payment_interest: Mapped[bool | None] = mapped_column(Boolean)
    has_price_escalation: Mapped[bool | None] = mapped_column(Boolean)
    has_taxes_clause: Mapped[bool | None] = mapped_column(Boolean)

    # ===== SURVIVAL =====
    has_survival_clause: Mapped[bool | None] = mapped_column(Boolean)
    survival_sections: Mapped[str | None] = mapped_column(Text)  # List of surviving sections

    # ===== NOTES =====
    extraction_notes: Mapped[str | None] = mapped_column(Text)  # Any notes from extraction

    # Relationship
    contract: Mapped["Contract"] = relationship(back_populates="clause_indicators")

    def __repr__(self) -> str:
        return f"<ContractClauseIndicator contract_id={self.contract_id}>"

    def to_summary_dict(self) -> dict:
        """Return a summary of present clauses."""
        present = []
        absent = []
        unknown = []

        for col in self.__table__.columns:
            if col.name.startswith("has_"):
                value = getattr(self, col.name)
                clause_name = col.name.replace("has_", "").replace("_", " ").title()
                if value is True:
                    present.append(clause_name)
                elif value is False:
                    absent.append(clause_name)
                else:
                    unknown.append(clause_name)

        return {
            "present": present,
            "absent": absent,
            "unknown": unknown,
            "coverage_percentage": (
                len(present) / (len(present) + len(absent) + len(unknown)) * 100
                if (present or absent or unknown) else 0
            ),
        }

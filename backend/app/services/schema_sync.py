"""Service to sync schema-extracted data to relational DB structure.

This service handles the "hybrid" approach:
1. Full schema extraction stored in JSONB (schema_data)
2. Important fields synced to columns for efficient querying
3. Child tables populated for parties, key dates, etc.
4. Canonical tables populated for financials, liabilities, clause indicators
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.party import ContractParty, PartyRole
from app.models.key_date import ContractKeyDate, DateEventType
from app.models.financial import (
    ContractFinancial,
    ContractLiability,
    FeeType,
    PaymentTerms,
    PenaltyType,
    LiabilityCapType,
)
from app.models.clause_indicator import ContractClauseIndicator
from app.models.obligation import (
    Obligation,
    ObligationType,
    ObligationOwner,
    ObligationCategory,
    ObligationFrequency,
    ObligationStatus,
    RAGStatus,
    DeadlineType,
)

logger = logging.getLogger(__name__)


def parse_date(value: Any) -> date | None:
    """Parse a date from various formats."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def parse_decimal(value: Any) -> Decimal | None:
    """Parse a decimal value."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return None


def parse_int(value: Any) -> int | None:
    """Parse an integer value."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def safe_lower(value: Any, default: str = "") -> str:
    """Safely convert value to lowercase string."""
    if value is None:
        return default.lower()
    return str(value).lower()


def safe_currency(value: Any, default: str = "USD") -> str:
    """Extract and validate currency code (3 chars max)."""
    if value is None:
        return default[:3]
    currency = str(value).upper().strip()
    # Extract first 3 chars (standard currency code)
    return currency[:3] if currency else default[:3]


class SchemaSyncService:
    """Syncs schema-extracted data to relational structure."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_contract(self, contract: Contract) -> None:
        """Sync all schema data for a contract.

        Args:
            contract: Contract with schema_data to sync.
        """
        if not contract.schema_data:
            logger.warning(f"No schema_data to sync for contract {contract.id}")
            return

        schema_data = contract.schema_data
        logger.info(f"Syncing schema data for contract {contract.id}")

        # Sync promoted columns
        self._sync_promoted_columns(contract, schema_data)

        # Sync parties
        await self._sync_parties(contract, schema_data)

        # Sync key dates
        await self._sync_key_dates(contract, schema_data)

        # Sync canonical tables (Phase 2)
        await self._sync_financials(contract, schema_data)
        await self._sync_liabilities(contract, schema_data)
        await self._sync_clause_indicators(contract, schema_data)
        await self._sync_obligations(contract, schema_data)

        await self.db.flush()
        logger.info(f"Schema sync completed for contract {contract.id}")

    def _sync_promoted_columns(self, contract: Contract, data: dict) -> None:
        """Sync important fields to dedicated columns."""

        # Contract metadata
        metadata = data.get("contract_metadata", {})

        if not contract.effective_date:
            contract.effective_date = parse_date(metadata.get("effective_date"))

        if not contract.expiration_date:
            contract.expiration_date = parse_date(metadata.get("expiration_date"))

        contract.governing_law = metadata.get("governing_law") or contract.governing_law

        initial_term = metadata.get("initial_term_years")
        if initial_term:
            contract.initial_term_months = parse_int(initial_term) * 12 if parse_int(initial_term) else None

        contract.notice_period_days = (
            parse_int(metadata.get("termination_notice_days"))
            or contract.notice_period_days
        )

        # Counterparty from parties list — the counterparty is the vendor/supplier,
        # NOT the client/customer (the client is typically the document owner)
        parties = metadata.get("parties", [])
        for party in parties:
            role = safe_lower(party.get("role"), "")
            party_name = party.get("legal_name") or party.get("name")
            if role in ("vendor", "supplier", "service_provider", "contractor",
                        "provider", "disclosing_party", "licensor"):
                if not contract.counterparty and party_name:
                    contract.counterparty = party_name
                    logger.info(f"Set counterparty from schema (role={role}): {party_name}")
                break

        # Term and renewal
        term_data = data.get("termination_and_disputes", {}).get("term", {})
        if term_data:
            contract.auto_renewal = term_data.get("auto_renewal", contract.auto_renewal)

        termination_rights = data.get("termination_and_disputes", {}).get("termination_rights", [])
        for right in termination_rights:
            # Handle both dict and string formats
            if isinstance(right, dict):
                if right.get("reason") == "for_convenience":
                    contract.termination_for_convenience = True
                    break
            elif isinstance(right, str):
                if "convenience" in right.lower():
                    contract.termination_for_convenience = True
                    break

        # Risk and compliance
        risk_compliance = data.get("risk_and_compliance", {})

        liability_cap = risk_compliance.get("liability_cap", {})
        if liability_cap:
            contract.liability_cap_type = liability_cap.get("cap_type")
            contract.liability_cap_amount = parse_decimal(liability_cap.get("cap_amount"))

        confidentiality = risk_compliance.get("confidentiality", {})
        if confidentiality:
            survival = confidentiality.get("survival_period")
            if survival and isinstance(survival, str):
                # Try to parse "X years" format
                try:
                    years = int(survival.split()[0])
                    contract.confidentiality_term_years = years
                except (ValueError, IndexError):
                    pass

        # Dispute resolution
        dispute = data.get("termination_and_disputes", {}).get("dispute_resolution", {})
        if dispute:
            contract.dispute_resolution_method = dispute.get("method")
            if not contract.jurisdiction:
                contract.jurisdiction = dispute.get("jurisdiction")

        # Financials
        financials = data.get("financials", {})
        fee_model = financials.get("fee_model", {})
        if fee_model:
            if not contract.currency:
                contract.currency = safe_currency(fee_model.get("currency"))

        logger.debug(f"Synced promoted columns for {contract.id}")

    async def _sync_parties(self, contract: Contract, data: dict) -> None:
        """Sync parties to the contract_parties table."""

        # Clear existing parties
        await self.db.execute(
            delete(ContractParty).where(ContractParty.contract_id == contract.id)
        )

        metadata = data.get("contract_metadata", {})
        parties_data = metadata.get("parties", [])

        if not parties_data:
            return

        role_map = {
            "provider": PartyRole.PROVIDER,
            "client": PartyRole.CLIENT,
            "vendor": PartyRole.VENDOR,
            "customer": PartyRole.CUSTOMER,
            "licensor": PartyRole.LICENSOR,
            "licensee": PartyRole.LICENSEE,
            "employer": PartyRole.EMPLOYER,
            "employee": PartyRole.EMPLOYEE,
            "disclosing_party": PartyRole.DISCLOSING_PARTY,
            "receiving_party": PartyRole.RECEIVING_PARTY,
        }

        for i, party_data in enumerate(parties_data):
            role_str = safe_lower(party_data.get("role"), "other").replace(" ", "_")
            role = role_map.get(role_str, PartyRole.OTHER)

            legal_name = party_data.get("legal_name") or party_data.get("name")
            if not legal_name:
                continue

            party = ContractParty(
                contract_id=contract.id,
                role=role,
                legal_name=legal_name,
                short_name=party_data.get("short_name"),
                entity_type=party_data.get("entity_type"),
                jurisdiction=party_data.get("jurisdiction"),
                registered_address=party_data.get("registered_address"),
                is_primary=(i == 0),  # First party is typically "our" side
            )
            self.db.add(party)

        logger.debug(f"Synced {len(parties_data)} parties for {contract.id}")

    async def _sync_key_dates(self, contract: Contract, data: dict) -> None:
        """Sync key dates to the contract_key_dates table."""

        # Clear existing key dates (except manually added ones)
        await self.db.execute(
            delete(ContractKeyDate).where(ContractKeyDate.contract_id == contract.id)
        )

        key_dates_added = 0

        # Contract effective date
        metadata = data.get("contract_metadata", {})
        effective_date = parse_date(metadata.get("effective_date"))
        if effective_date:
            self.db.add(ContractKeyDate(
                contract_id=contract.id,
                event_type=DateEventType.CONTRACT_START,
                event_name="Contract Effective Date",
                event_date=effective_date,
            ))
            key_dates_added += 1

        # Contract expiration
        expiration_date = parse_date(metadata.get("expiration_date"))
        if not expiration_date and contract.expiration_date:
            expiration_date = contract.expiration_date

        if expiration_date:
            notice_days = contract.notice_period_days or 30
            notice_deadline = expiration_date - timedelta(days=notice_days)

            self.db.add(ContractKeyDate(
                contract_id=contract.id,
                event_type=DateEventType.CONTRACT_EXPIRATION,
                event_name="Contract Expiration",
                event_date=expiration_date,
                notice_required_by=notice_deadline,
                action_required="Review contract and decide on renewal or termination",
                alert_days_before=notice_days + 14,  # Alert 2 weeks before notice deadline
            ))
            key_dates_added += 1

            # Renewal notice deadline
            self.db.add(ContractKeyDate(
                contract_id=contract.id,
                event_type=DateEventType.RENEWAL_NOTICE_DEADLINE,
                event_name="Renewal Notice Deadline",
                event_date=notice_deadline,
                action_required=f"Provide {notice_days}-day notice if not renewing",
                alert_days_before=14,
            ))
            key_dates_added += 1

        # Key dates from schema
        key_dates_data = data.get("key_dates", {}).get("dates", [])
        for date_entry in key_dates_data:
            event_date = parse_date(date_entry.get("date"))
            if not event_date:
                continue

            event_type = self._map_event_type(date_entry.get("event", ""))

            self.db.add(ContractKeyDate(
                contract_id=contract.id,
                event_type=event_type,
                event_name=date_entry.get("event", "Key Date"),
                event_date=event_date,
                notice_required_by=parse_date(date_entry.get("notice_required_by")),
                action_required=date_entry.get("action_required"),
            ))
            key_dates_added += 1

        # Obligations with fixed deadlines
        obligations = data.get("obligations", {})
        for obl_type in ["provider_obligations", "client_obligations", "mutual_obligations"]:
            for obl in obligations.get(obl_type, []):
                # Skip string obligations
                if not isinstance(obl, dict):
                    continue
                deadline = parse_date(obl.get("deadline_value"))
                if deadline and obl.get("deadline_type") == "fixed_date":
                    self.db.add(ContractKeyDate(
                        contract_id=contract.id,
                        event_type=DateEventType.OBLIGATION_DEADLINE,
                        event_name=f"Obligation: {obl.get('description', '')[:100]}",
                        description=obl.get("description"),
                        event_date=deadline,
                        responsible_party=obl.get("obligated_party"),
                        section_reference=obl.get("section_reference"),
                    ))
                    key_dates_added += 1

        logger.debug(f"Synced {key_dates_added} key dates for {contract.id}")

    def _map_event_type(self, event_str: str) -> DateEventType:
        """Map event string to DateEventType enum."""
        event_lower = event_str.lower()

        if "expir" in event_lower:
            return DateEventType.CONTRACT_EXPIRATION
        if "renew" in event_lower:
            if "notice" in event_lower:
                return DateEventType.RENEWAL_NOTICE_DEADLINE
            return DateEventType.RENEWAL_DATE
        if "terminat" in event_lower:
            return DateEventType.TERMINATION_NOTICE_DEADLINE
        if "payment" in event_lower or "pay" in event_lower:
            return DateEventType.PAYMENT_DUE
        if "deliver" in event_lower:
            return DateEventType.DELIVERY_DUE
        if "milestone" in event_lower:
            return DateEventType.MILESTONE
        if "review" in event_lower:
            return DateEventType.REVIEW_DATE

        return DateEventType.CUSTOM

    # ===== PHASE 2: CANONICAL TABLE SYNC METHODS =====

    async def _sync_financials(self, contract: Contract, data: dict) -> None:
        """Sync financial terms to the contract_financials table."""

        # Clear existing financials
        await self.db.execute(
            delete(ContractFinancial).where(ContractFinancial.contract_id == contract.id)
        )

        financials_data = data.get("financials", {})
        fee_model = financials_data.get("fee_model", {})
        payment_terms_data = financials_data.get("payment_terms", {})
        penalties_data = financials_data.get("penalties", [])

        financials_added = 0

        # Map string fee types to enum
        fee_type_map = {
            "base_fee": FeeType.BASE_FEE,
            "per_unit": FeeType.PER_UNIT,
            "per_hour": FeeType.PER_HOUR,
            "per_day": FeeType.PER_DAY,
            "percentage": FeeType.PERCENTAGE,
            "milestone": FeeType.MILESTONE,
            "recurring_monthly": FeeType.RECURRING_MONTHLY,
            "recurring_annual": FeeType.RECURRING_ANNUAL,
            "one_time": FeeType.ONE_TIME,
            "retainer": FeeType.RETAINER,
            "success_fee": FeeType.SUCCESS_FEE,
            "licensing_fee": FeeType.LICENSING_FEE,
            "license_fee": FeeType.LICENSING_FEE,
            "maintenance_fee": FeeType.MAINTENANCE_FEE,
            "support_fee": FeeType.SUPPORT_FEE,
            "time_and_materials": FeeType.PER_HOUR,
            "fixed_price": FeeType.ONE_TIME,
            "other": FeeType.OTHER,
        }

        payment_terms_map = {
            "upon_receipt": PaymentTerms.UPON_RECEIPT,
            "due_on_receipt": PaymentTerms.UPON_RECEIPT,
            "net_15": PaymentTerms.NET_15,
            "net_30": PaymentTerms.NET_30,
            "net_45": PaymentTerms.NET_45,
            "net_60": PaymentTerms.NET_60,
            "net_90": PaymentTerms.NET_90,
            "advance": PaymentTerms.ADVANCE,
            "milestone_based": PaymentTerms.MILESTONE_BASED,
            "upon_completion": PaymentTerms.UPON_COMPLETION,
            "custom": PaymentTerms.CUSTOM,
        }

        penalty_type_map = {
            "late_payment": PenaltyType.LATE_PAYMENT,
            "late_delivery": PenaltyType.LATE_DELIVERY,
            "non_compliance": PenaltyType.NON_COMPLIANCE,
            "non_performance": PenaltyType.NON_COMPLIANCE,
            "breach": PenaltyType.BREACH,
            "early_termination": PenaltyType.EARLY_TERMINATION,
            "sla_violation": PenaltyType.SLA_VIOLATION,
            "sla_breach": PenaltyType.SLA_VIOLATION,
            "quality_failure": PenaltyType.QUALITY_FAILURE,
            "other": PenaltyType.OTHER,
        }

        # Extract main fee
        if fee_model:
            fee_type_str = safe_lower(fee_model.get("fee_type"), "other").replace(" ", "_")
            fee_type = fee_type_map.get(fee_type_str, FeeType.OTHER)

            payment_str = safe_lower(payment_terms_data.get("payment_terms"), "").replace(" ", "_")
            payment_terms = payment_terms_map.get(payment_str)

            financial = ContractFinancial(
                contract_id=contract.id,
                fee_type=fee_type,
                fee_description=fee_model.get("description"),
                fee_amount=parse_decimal(fee_model.get("base_amount")),
                currency=safe_currency(fee_model.get("currency")),
                invoicing_frequency=fee_model.get("billing_frequency"),
                payment_terms=payment_terms,
                payment_terms_days=parse_int(payment_terms_data.get("payment_due_days")),
                is_penalty=False,
                section_reference=fee_model.get("section_reference"),
            )
            self.db.add(financial)
            financials_added += 1

        # Extract rate information if present
        rate_info = fee_model.get("rates", []) if fee_model else []
        for rate in rate_info:
            financial = ContractFinancial(
                contract_id=contract.id,
                fee_type=FeeType.PER_HOUR,
                fee_description=rate.get("role") or rate.get("description"),
                fee_amount=parse_decimal(rate.get("rate")),
                currency=safe_currency(fee_model.get("currency") if fee_model else None),
                invoicing_frequency=rate.get("frequency", "hourly"),
                is_penalty=False,
            )
            self.db.add(financial)
            financials_added += 1

        # Extract penalties
        for penalty in penalties_data:
            penalty_type_str = safe_lower(penalty.get("type"), "other").replace(" ", "_")
            penalty_type = penalty_type_map.get(penalty_type_str, PenaltyType.OTHER)

            financial = ContractFinancial(
                contract_id=contract.id,
                fee_type=FeeType.OTHER,
                fee_description=penalty.get("description"),
                penalty_amount=parse_decimal(penalty.get("amount")),
                penalty_percentage=parse_decimal(penalty.get("percentage")),
                currency=safe_currency(penalty.get("currency")),
                is_penalty=True,
                penalty_type=penalty_type,
                penalty_trigger=penalty.get("trigger"),
                section_reference=penalty.get("section_reference"),
            )
            self.db.add(financial)
            financials_added += 1

        logger.debug(f"Synced {financials_added} financial terms for {contract.id}")

    async def _sync_liabilities(self, contract: Contract, data: dict) -> None:
        """Sync liability terms to the contract_liabilities table."""

        # Clear existing liabilities
        await self.db.execute(
            delete(ContractLiability).where(ContractLiability.contract_id == contract.id)
        )

        risk_data = data.get("risk_and_compliance", {})
        liability_cap = risk_data.get("liability_cap", {})
        indemnification = risk_data.get("indemnification", {})
        insurance = risk_data.get("insurance_requirements", {})

        liabilities_added = 0

        cap_type_map = {
            "unlimited": LiabilityCapType.UNLIMITED,
            "fixed_amount": LiabilityCapType.FIXED_AMOUNT,
            "fees_paid": LiabilityCapType.FEES_PAID,
            "annual_fees": LiabilityCapType.ANNUAL_FEES,
            "multiple_of_fees": LiabilityCapType.MULTIPLE_OF_FEES,
            "percentage_of_value": LiabilityCapType.PERCENTAGE_OF_VALUE,
            "insurance_limit": LiabilityCapType.INSURANCE_LIMIT,
            "custom": LiabilityCapType.CUSTOM,
        }

        # Liability cap
        if liability_cap:
            cap_type_str = safe_lower(liability_cap.get("cap_type"), "custom").replace(" ", "_")
            cap_type = cap_type_map.get(cap_type_str, LiabilityCapType.CUSTOM)

            # Check for exclusions
            exclusions = liability_cap.get("exclusions", [])

            liability = ContractLiability(
                contract_id=contract.id,
                liability_cap_type=cap_type,
                liability_cap_amount=parse_decimal(liability_cap.get("cap_amount")),
                liability_cap_currency=safe_currency(liability_cap.get("currency")),
                liability_cap_multiplier=parse_decimal(liability_cap.get("multiplier")),
                liability_cap_description=liability_cap.get("description"),
                mutual_indemnification=liability_cap.get("is_mutual", False),
                excludes_indirect_damages="indirect" in str(exclusions).lower(),
                excludes_consequential_damages="consequential" in str(exclusions).lower(),
                excludes_lost_profits="lost profit" in str(exclusions).lower(),
                exclusions_description=", ".join(exclusions) if exclusions else None,
                section_reference=liability_cap.get("section_reference"),
            )
            self.db.add(liability)
            liabilities_added += 1

        # Indemnification clauses
        if indemnification:
            provider_indemnifies = indemnification.get("provider_indemnifies", [])
            client_indemnifies = indemnification.get("client_indemnifies", [])

            for item in provider_indemnifies:
                if isinstance(item, str):
                    liability = ContractLiability(
                        contract_id=contract.id,
                        liability_cap_type=LiabilityCapType.CUSTOM,
                        indemnifying_party="Provider",
                        indemnification_scope=item,
                    )
                    self.db.add(liability)
                    liabilities_added += 1

            for item in client_indemnifies:
                if isinstance(item, str):
                    liability = ContractLiability(
                        contract_id=contract.id,
                        liability_cap_type=LiabilityCapType.CUSTOM,
                        indemnifying_party="Client",
                        indemnification_scope=item,
                    )
                    self.db.add(liability)
                    liabilities_added += 1

        # Insurance requirements
        if insurance:
            # Handle both dict and list formats
            if isinstance(insurance, dict):
                min_coverage = insurance.get("minimum_coverage", {})
                if isinstance(min_coverage, dict):
                    for coverage_type, amount in min_coverage.items():
                        liability = ContractLiability(
                            contract_id=contract.id,
                            liability_cap_type=LiabilityCapType.INSURANCE_LIMIT,
                            liability_cap_amount=parse_decimal(amount),
                            liability_cap_description=coverage_type,
                            insurance_required=True,
                            insurance_types=coverage_type,
                            insurance_minimum_amount=parse_decimal(amount),
                        )
                        self.db.add(liability)
                        liabilities_added += 1
            elif isinstance(insurance, list):
                for ins_item in insurance:
                    if isinstance(ins_item, dict):
                        liability = ContractLiability(
                            contract_id=contract.id,
                            liability_cap_type=LiabilityCapType.INSURANCE_LIMIT,
                            liability_cap_amount=parse_decimal(ins_item.get("amount")),
                            liability_cap_description=ins_item.get("type") or ins_item.get("description"),
                            insurance_required=True,
                            insurance_types=ins_item.get("type"),
                            insurance_minimum_amount=parse_decimal(ins_item.get("amount")),
                        )
                        self.db.add(liability)
                        liabilities_added += 1

        logger.debug(f"Synced {liabilities_added} liability terms for {contract.id}")

    async def _sync_clause_indicators(self, contract: Contract, data: dict) -> None:
        """Sync clause presence indicators to contract_clause_indicators table."""

        # Delete existing indicator record
        await self.db.execute(
            delete(ContractClauseIndicator).where(
                ContractClauseIndicator.contract_id == contract.id
            )
        )

        # Extract data from various schema sections
        risk_data = data.get("risk_and_compliance", {})
        term_data = data.get("termination_and_disputes", {})
        obligations = data.get("obligations", {})
        metadata = data.get("contract_metadata", {})
        ip_data = data.get("intellectual_property", {})
        services_data = data.get("services_and_deliverables", {})

        # Helper to check if data exists and is meaningful
        def has_data(obj: Any) -> bool:
            if obj is None:
                return False
            if isinstance(obj, dict):
                return bool(obj)
            if isinstance(obj, list):
                return len(obj) > 0
            if isinstance(obj, str):
                return bool(obj.strip())
            return bool(obj)

        # Create indicator record - use only columns that exist in the model
        indicators = ContractClauseIndicator(
            contract_id=contract.id,
            # Confidentiality & IP
            has_confidentiality=has_data(risk_data.get("confidentiality")),
            has_mutual_confidentiality=risk_data.get("confidentiality", {}).get("is_mutual", False),
            has_ip_ownership=has_data(ip_data.get("ip_ownership")),
            has_ip_license=has_data(ip_data.get("license_grant")),
            has_work_for_hire=has_data(ip_data.get("work_for_hire")),
            # Liability & Indemnification
            has_limitation_of_liability=has_data(risk_data.get("liability_cap")),
            has_liability_cap=has_data(risk_data.get("liability_cap", {}).get("cap_amount")),
            has_indemnification=has_data(risk_data.get("indemnification")),
            has_mutual_indemnification=risk_data.get("indemnification", {}).get("is_mutual", False),
            has_warranty_disclaimer=has_data(risk_data.get("disclaimer_of_warranties")),
            # Termination & Renewal
            has_termination_for_cause=self._check_termination_for_cause(term_data),
            has_termination_for_convenience=self._check_termination_for_convenience(term_data),
            has_termination_notice_period=has_data(term_data.get("termination_rights")),
            has_auto_renewal=term_data.get("term", {}).get("auto_renewal", False),
            has_renewal_notice_requirement=has_data(term_data.get("term", {}).get("notice_days")),
            # Force Majeure & Disputes
            has_force_majeure=has_data(risk_data.get("force_majeure")),
            has_governing_law=has_data(metadata.get("governing_law")),
            has_dispute_resolution=has_data(term_data.get("dispute_resolution")),
            has_arbitration=self._check_for_arbitration(term_data),
            has_exclusive_jurisdiction=has_data(term_data.get("dispute_resolution", {}).get("jurisdiction")),
            # Compliance & Regulatory
            has_data_protection=has_data(risk_data.get("data_protection")),
            has_gdpr_compliance=has_data(risk_data.get("gdpr_compliance")),
            has_anticorruption=has_data(risk_data.get("anti_corruption")),
            has_sanctions_compliance=has_data(risk_data.get("sanctions")),
            has_export_control=has_data(risk_data.get("export_control")),
            # Business restrictions
            has_non_compete=has_data(risk_data.get("non_compete")),
            has_non_solicit=has_data(risk_data.get("non_solicitation")),
            has_exclusivity=has_data(metadata.get("exclusivity")),
            has_most_favored_nation=has_data(risk_data.get("most_favored_nation")),
            # Operational
            has_insurance_requirement=has_data(risk_data.get("insurance_requirements")),
            has_audit_rights=has_data(risk_data.get("audit_rights")),
            has_service_levels=has_data(services_data.get("service_levels")),
            has_change_control=has_data(services_data.get("change_control")),
            has_assignment_restriction=has_data(term_data.get("assignment")),
            has_subcontracting_restriction=has_data(services_data.get("subcontracting")),
            # Payment
            has_payment_terms=has_data(data.get("financials", {}).get("payment_terms")),
            has_late_payment_interest=self._check_for_late_payment_penalty(data),
            has_price_escalation=has_data(data.get("financials", {}).get("price_adjustment")),
            # Survival
            has_survival_clause=has_data(term_data.get("survival_clause")),
        )

        self.db.add(indicators)
        logger.debug(f"Synced clause indicators for {contract.id}")

    def _check_termination_for_convenience(self, term_data: dict) -> bool:
        """Check if contract has termination for convenience."""
        termination_rights = term_data.get("termination_rights", [])
        for right in termination_rights:
            if isinstance(right, dict):
                if right.get("reason") == "for_convenience":
                    return True
            elif isinstance(right, str):
                if "convenience" in right.lower():
                    return True
        return False

    def _check_termination_for_cause(self, term_data: dict) -> bool:
        """Check if contract has termination for cause."""
        termination_rights = term_data.get("termination_rights", [])
        for right in termination_rights:
            if isinstance(right, dict):
                reason = safe_lower(right.get("reason"), "")
                if "cause" in reason or "breach" in reason or "default" in reason:
                    return True
            elif isinstance(right, str):
                right_lower = right.lower()
                if "cause" in right_lower or "breach" in right_lower or "default" in right_lower:
                    return True
        return False

    def _check_for_arbitration(self, term_data: dict) -> bool:
        """Check if dispute resolution involves arbitration."""
        dispute = term_data.get("dispute_resolution", {})
        method = safe_lower(dispute.get("method"), "")
        return "arbitration" in method

    def _check_for_late_payment_penalty(self, data: dict) -> bool:
        """Check if there's a late payment penalty."""
        penalties = data.get("financials", {}).get("penalties", [])
        for penalty in penalties:
            if "late" in safe_lower(penalty.get("type"), ""):
                return True
            if "late" in safe_lower(penalty.get("description"), ""):
                return True
        return False

    async def _sync_obligations(self, contract: Contract, data: dict) -> None:
        """Sync enhanced obligation fields from schema data.

        Note: If obligations already exist (from AI extraction), we skip recreation
        to avoid deleting obligations that were extracted by the obligation_tracking agent.
        """
        from sqlalchemy import select, func

        # Check if obligations already exist for this contract
        existing_count = await self.db.scalar(
            select(func.count()).select_from(Obligation).where(
                Obligation.contract_id == contract.id
            )
        )

        if existing_count and existing_count > 0:
            logger.debug(f"Skipping obligation sync - {existing_count} obligations already exist for {contract.id}")
            return

        # Get existing obligations for this contract
        obligations_data = data.get("obligations", {})

        owner_map = {
            "provider": ObligationOwner.PROVIDER,
            "client": ObligationOwner.CLIENT,
            "customer": ObligationOwner.CLIENT,
            "mutual": ObligationOwner.MUTUAL,
            "third_party": ObligationOwner.THIRD_PARTY,
        }

        category_map = {
            "service_provision": ObligationCategory.SERVICE_PROVISION,
            "service_levels": ObligationCategory.SERVICE_LEVELS,
            "delivery": ObligationCategory.DELIVERY,
            "performance": ObligationCategory.PERFORMANCE,
            "payment": ObligationCategory.PAYMENT,
            "invoicing": ObligationCategory.INVOICING,
            "data_protection": ObligationCategory.DATA_PROTECTION,
            "data_handling": ObligationCategory.DATA_HANDLING,
            "reporting": ObligationCategory.REPORTING,
            "compliance": ObligationCategory.REGULATORY_COMPLIANCE,
            "regulatory_compliance": ObligationCategory.REGULATORY_COMPLIANCE,
            "audit": ObligationCategory.AUDIT,
            "confidentiality": ObligationCategory.CONFIDENTIALITY,
            "notification": ObligationCategory.NOTIFICATION,
            "insurance": ObligationCategory.INSURANCE,
            "documentation": ObligationCategory.DOCUMENTATION,
            "training": ObligationCategory.TRAINING,
            "support": ObligationCategory.SUPPORT,
            "maintenance": ObligationCategory.MAINTENANCE,
            "testing": ObligationCategory.TESTING,
            "transition": ObligationCategory.TRANSITION,
        }

        frequency_map = {
            "one_time": ObligationFrequency.ONE_TIME,
            "daily": ObligationFrequency.DAILY,
            "weekly": ObligationFrequency.WEEKLY,
            "monthly": ObligationFrequency.MONTHLY,
            "quarterly": ObligationFrequency.QUARTERLY,
            "annual": ObligationFrequency.ANNUAL,
            "yearly": ObligationFrequency.ANNUAL,
            "ongoing": ObligationFrequency.ONGOING,
            "triggered": ObligationFrequency.TRIGGERED,
            "as_needed": ObligationFrequency.AS_NEEDED,
        }

        # Delete existing obligations and recreate with enhanced fields
        await self.db.execute(
            delete(Obligation).where(Obligation.contract_id == contract.id)
        )

        obligations_added = 0

        # Process each obligation category
        obligation_sources = [
            ("provider_obligations", ObligationOwner.PROVIDER),
            ("client_obligations", ObligationOwner.CLIENT),
            ("mutual_obligations", ObligationOwner.MUTUAL),
        ]

        for source_key, default_owner in obligation_sources:
            for obl in obligations_data.get(source_key, []):
                # Handle string obligations (just descriptions)
                if isinstance(obl, str):
                    obl = {"description": obl}

                description = obl.get("description", "")
                if not description:
                    continue

                # Map category
                category_str = safe_lower(obl.get("category"), "other").replace(" ", "_")
                category = category_map.get(category_str, ObligationCategory.OTHER)

                # Map frequency
                frequency_str = safe_lower(obl.get("frequency"), "").replace(" ", "_")
                frequency = frequency_map.get(frequency_str, ObligationFrequency.ONE_TIME)

                # Determine obligation type
                obl_type_str = safe_lower(obl.get("type"), "other")
                type_map = {
                    "payment": ObligationType.PAYMENT,
                    "delivery": ObligationType.DELIVERY,
                    "reporting": ObligationType.REPORTING,
                    "compliance": ObligationType.COMPLIANCE,
                    "notification": ObligationType.NOTIFICATION,
                    "performance": ObligationType.PERFORMANCE,
                }
                obl_type = type_map.get(obl_type_str, ObligationType.OTHER)

                # Determine deadline type
                deadline_type_str = safe_lower(obl.get("deadline_type"), "")
                deadline_type_map = {
                    "fixed_date": DeadlineType.FIXED_DATE,
                    "recurring": DeadlineType.RECURRING,
                    "relative": DeadlineType.RELATIVE,
                    "ongoing": DeadlineType.ONGOING,
                }
                deadline_type = deadline_type_map.get(deadline_type_str, DeadlineType.RELATIVE)

                # Determine owner and map to legacy obligated_party field
                owner_str = safe_lower(obl.get("owner"), "")
                owner_enum = owner_map.get(owner_str, default_owner)

                # Map owner_type enum to legacy obligated_party string for dashboard compatibility
                obligated_party_map = {
                    ObligationOwner.PROVIDER: "Provider",
                    ObligationOwner.CLIENT: "Client",
                    ObligationOwner.MUTUAL: "Mutual",
                    ObligationOwner.THIRD_PARTY: "Third Party",
                    ObligationOwner.UNSPECIFIED: "Unknown",
                }
                obligated_party = obl.get("obligated_party") or obligated_party_map.get(owner_enum, "Unknown")

                # Create obligation
                obligation = Obligation(
                    contract_id=contract.id,
                    description=description,
                    obligation_type=obl_type,
                    owner_type=owner_enum,
                    category=category,
                    frequency=frequency,
                    frequency_custom=obl.get("frequency_custom"),
                    deadline_type=deadline_type,
                    deadline=parse_date(obl.get("deadline_value")),
                    recurrence_pattern=obl.get("recurrence_pattern"),
                    relative_deadline_text=obl.get("relative_deadline_text"),
                    obligated_party=obligated_party,
                    beneficiary_party=obl.get("beneficiary_party"),
                    status=ObligationStatus.PENDING,
                    rag_status=RAGStatus.NOT_ASSESSED,
                    is_critical=obl.get("is_critical", False),
                    priority=parse_int(obl.get("priority")) or 3,
                    section_reference=obl.get("section_reference"),
                    consequence_of_breach=obl.get("consequence_of_breach"),
                    trigger_condition=obl.get("trigger_condition"),
                    source_text=obl.get("source_text"),
                )
                self.db.add(obligation)
                obligations_added += 1

        logger.debug(f"Synced {obligations_added} obligations for {contract.id}")


async def sync_schema_to_db(db: AsyncSession, contract: Contract) -> None:
    """Convenience function to sync schema data.

    Args:
        db: Database session.
        contract: Contract with schema_data.
    """
    service = SchemaSyncService(db)
    await service.sync_contract(contract)

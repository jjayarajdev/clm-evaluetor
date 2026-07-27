"""Post-signing dashboard service.

Aggregates data from obligations, SLAs, renewals, vendors, and milestones
into widget responses for the post-signing dashboard.
"""

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import apply_bu_filter, apply_tenant_filter
from app.models import (
    Contract, ContractStatus, Obligation, ObligationStatus, RAGStatus,
    ContractSLA, SLAPerformance,
)
from app.schemas.postsigning import (
    ObligationWidget,
    SLAWidget,
    RenewalWidget,
    VendorWidget,
    MilestoneWidget,
    ComplianceWidget,
    PostSigningDashboard,
)


class PostSigningService:
    """Aggregation service for post-signing dashboard widgets."""

    def __init__(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID | None = None,
        business_unit_id: uuid.UUID | None = None,
        user_role: str | None = None,
    ) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.business_unit_id = business_unit_id
        self.user_role = user_role

    def _apply_filters(self, query, model=Contract):
        """Apply tenant + BU filters to a query."""
        query = apply_tenant_filter(query, self.tenant_id, model)
        query = apply_bu_filter(query, self.business_unit_id, self.user_role)
        return query

    async def _fetch_contracts(self):
        """Fetch all completed contracts for tenant/BU."""
        query = select(Contract).where(Contract.status == ContractStatus.COMPLETED)
        query = self._apply_filters(query)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _fetch_obligations(self):
        """Fetch all obligations linked to completed contracts."""
        query = (
            select(Obligation)
            .join(Contract, Obligation.contract_id == Contract.id)
            .where(Contract.status == ContractStatus.COMPLETED)
        )
        query = self._apply_filters(query)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _fetch_slas(self):
        """Fetch all SLAs linked to completed contracts."""
        query = (
            select(ContractSLA)
            .join(Contract, ContractSLA.contract_id == Contract.id)
            .where(Contract.status == ContractStatus.COMPLETED)
        )
        query = self._apply_filters(query)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    def _is_overdue(o, today) -> bool:
        """Check if an obligation is overdue (computed, not stored)."""
        return (
            o.deadline is not None
            and o.deadline < today
            and o.status not in (ObligationStatus.COMPLETED, ObligationStatus.WAIVED)
        )

    @staticmethod
    def _effective_status(o, today) -> str:
        """Return the effective display status for an obligation."""
        if o.status == ObligationStatus.COMPLETED:
            return "completed"
        if o.status == ObligationStatus.WAIVED:
            return "waived"
        if o.status == ObligationStatus.IN_PROGRESS:
            return "in_progress"
        # Compute overdue dynamically for pending obligations
        if o.deadline and o.deadline < today:
            return "overdue"
        return o.status.value if o.status else "pending"

    def _build_obligation_widget(self, obligations, today):
        """Build the obligation widget from obligation data."""
        obl_total = len(obligations)
        obl_completed = sum(1 for o in obligations if o.status == ObligationStatus.COMPLETED)
        obl_in_progress = sum(1 for o in obligations if o.status == ObligationStatus.IN_PROGRESS)
        # Compute overdue dynamically: deadline passed AND not completed/waived
        obl_overdue = sum(1 for o in obligations if self._is_overdue(o, today))

        obl_at_risk = sum(
            1 for o in obligations
            if not self._is_overdue(o, today)
            and o.status not in (ObligationStatus.COMPLETED, ObligationStatus.WAIVED)
            and o.deadline
            and 0 <= (o.deadline - today).days <= 7
        )

        # RAG includes overdue as red
        obl_green = sum(1 for o in obligations if o.rag_status == RAGStatus.GREEN and not self._is_overdue(o, today))
        obl_amber = sum(1 for o in obligations if o.rag_status == RAGStatus.AMBER and not self._is_overdue(o, today))
        obl_red = sum(1 for o in obligations if o.rag_status == RAGStatus.RED or self._is_overdue(o, today))

        waived = sum(1 for o in obligations if o.status == ObligationStatus.WAIVED)
        pending_future = sum(
            1 for o in obligations
            if o.status in (ObligationStatus.PENDING, ObligationStatus.IN_PROGRESS)
            and o.deadline and o.deadline > today
        )
        # Assessable = total minus waived minus future pending (not yet due).
        # Honest: None ("not tracked") when there's no completion signal at all —
        # a bare 0% on untracked obligations reads as failure, not "unmaintained".
        assessable = obl_total - waived - pending_future
        obl_compliance = (
            round((obl_completed + obl_in_progress) / assessable * 100, 2)
            if assessable > 0 and (obl_completed + obl_in_progress) > 0
            else None
        )

        # Urgent obligations: overdue + due within 3 days
        urgent_obls = [
            o for o in obligations
            if self._is_overdue(o, today)
            or (
                o.status not in (ObligationStatus.COMPLETED, ObligationStatus.WAIVED)
                and o.deadline and 0 <= (o.deadline - today).days <= 3
            )
        ]
        urgent_obls.sort(key=lambda o: o.deadline or date.max)

        urgent_items = [
            {
                "id": str(o.id),
                "title": o.description[:100] if o.description else "No description",
                "due_date": o.deadline.isoformat() if o.deadline else None,
                "status": self._effective_status(o, today),
                "rag": "red" if self._is_overdue(o, today) else (o.rag_status.value if o.rag_status else None),
            }
            for o in urgent_obls[:5]
        ]

        widget = ObligationWidget(
            total=obl_total,
            completed=obl_completed,
            in_progress=obl_in_progress,
            overdue=obl_overdue,
            at_risk=obl_at_risk,
            compliance_rate=obl_compliance,
            green=obl_green,
            amber=obl_amber,
            red=obl_red,
            urgent_items=urgent_items,
        )
        return widget, obl_compliance, obl_overdue, urgent_obls

    @staticmethod
    def _format_sla_value(value: float | None, unit_value: str) -> str | None:
        """Format an SLA value with its unit for display."""
        if value is None:
            return None
        unit_labels = {
            "percentage": "%",
            "hours": "hrs",
            "minutes": "min",
            "days": "days",
            "business_days": "b.days",
            "count": "",
            "score": "pts",
        }
        suffix = unit_labels.get(unit_value, "")
        # For percentages, show 1 decimal; for time/count, show whole or 1 decimal
        if unit_value == "percentage":
            return f"{value:.1f}{suffix}"
        elif value == int(value):
            return f"{int(value)} {suffix}".strip()
        else:
            return f"{value:.1f} {suffix}".strip()

    async def _build_sla_widget(self, slas, contracts, today):
        """Build the SLA widget from SLA data."""
        sla_total = len(slas)
        sla_active = sum(1 for s in slas if s.is_active)
        sla_breached = sum(1 for s in slas if s.consecutive_breaches > 0)
        sla_compliant = sla_active - sla_breached

        critical_breaches = sum(
            1 for s in slas
            if s.consecutive_breaches > 0
            and s.severity and s.severity.value == "critical"
        )

        compliance_rates = [float(s.current_compliance_rate) for s in slas if s.current_compliance_rate is not None]
        # Honest: None ("not measured") when there's no actual performance data —
        # not a fake 100% that reads as perfect when nothing has been measured.
        sla_compliance = round(sum(compliance_rates) / len(compliance_rates), 2) if compliance_rates else None

        # MTD penalties
        mtd_start = date(today.year, today.month, 1)
        penalty_query = (
            select(func.sum(SLAPerformance.penalty_amount))
            .join(ContractSLA, SLAPerformance.sla_id == ContractSLA.id)
            .join(Contract, ContractSLA.contract_id == Contract.id)
            .where(
                and_(
                    SLAPerformance.penalty_applied == True,
                    SLAPerformance.measured_at >= datetime.combine(mtd_start, datetime.min.time()),
                )
            )
        )
        if self.tenant_id is not None:
            penalty_query = penalty_query.where(Contract.tenant_id == self.tenant_id)
        penalty_query = apply_bu_filter(penalty_query, self.business_unit_id, self.user_role)
        penalty_result = await self.db.execute(penalty_query)
        total_penalties_mtd = float(penalty_result.scalar() or 0)

        # Recent breaches with performance details
        # Only include SLAs that have a target value set
        breached_slas = [
            s for s in slas
            if s.consecutive_breaches > 0 and s.target_value
        ]
        breached_slas.sort(key=lambda s: s.consecutive_breaches, reverse=True)

        recent_breaches = []
        for s in breached_slas[:10]:
            contract = next((c for c in contracts if c.id == s.contract_id), None)
            unit_val = s.metric_unit.value if s.metric_unit else "percentage"

            perf_query = (
                select(SLAPerformance)
                .where(SLAPerformance.sla_id == s.id)
                .order_by(SLAPerformance.measured_at.desc())
                .limit(1)
            )
            perf_result = await self.db.execute(perf_query)
            latest_perf = perf_result.scalar_one_or_none()

            target_raw = float(s.target_value) if s.target_value else None
            actual_raw = float(latest_perf.actual_value) if latest_perf and latest_perf.actual_value else None

            recent_breaches.append({
                "sla_id": str(s.id),
                "sla_name": s.sla_name,
                "contract_id": str(s.contract_id),
                "contract": contract.filename if contract else "Unknown",
                "breaches": s.consecutive_breaches,
                "severity": s.severity.value if s.severity else "medium",
                "metric_type": s.metric_type.value if s.metric_type else "custom",
                "metric_unit": unit_val,
                "target_value": target_raw,
                "actual_value": actual_raw,
                "target_display": self._format_sla_value(target_raw, unit_val),
                "actual_display": self._format_sla_value(actual_raw, unit_val),
                "deviation": float(latest_perf.deviation_percentage) if latest_perf and latest_perf.deviation_percentage else None,
                "measured_at": latest_perf.measured_at.isoformat() if latest_perf and latest_perf.measured_at else None,
                "penalty_amount": float(latest_perf.penalty_amount) if latest_perf and latest_perf.penalty_amount else None,
            })

        widget = SLAWidget(
            total_slas=sla_total,
            active_slas=sla_active,
            compliant=sla_compliant,
            breached=sla_breached,
            compliance_rate=sla_compliance,
            critical_breaches=critical_breaches,
            total_penalties_mtd=total_penalties_mtd,
            recent_breaches=recent_breaches,
        )
        return widget, sla_compliance, sla_breached, recent_breaches

    def _build_renewal_widget(self, contracts, today):
        """Build the renewal widget from contract data."""
        expiring_30, expiring_60, expiring_90, past_notice = [], [], [], []
        expired_count = 0
        no_date_count = 0

        for c in contracts:
            if not c.expiration_date:
                no_date_count += 1
                continue
            days_until = (c.expiration_date - today).days
            if days_until < 0:
                expired_count += 1
                continue
            if days_until <= 30:
                expiring_30.append(c)
            if days_until <= 60:
                expiring_60.append(c)
            if days_until <= 90:
                expiring_90.append(c)
            if c.notice_period_days:
                notice_deadline = c.expiration_date - timedelta(days=c.notice_period_days)
                if notice_deadline < today and days_until > 0:
                    past_notice.append(c)

        value_at_risk = sum(float(c.contract_value) for c in expiring_90 if c.contract_value)

        upcoming = sorted(expiring_90, key=lambda c: c.expiration_date or date.max)[:5]
        upcoming_renewals = [
            {
                "contract_id": str(c.id),
                "filename": c.filename,
                "counterparty": c.counterparty,
                "expiration_date": c.expiration_date.isoformat() if c.expiration_date else None,
                "value": float(c.contract_value) if c.contract_value else None,
                "auto_renewal": c.auto_renewal,
            }
            for c in upcoming
        ]

        widget = RenewalWidget(
            expiring_30_days=len(expiring_30),
            expiring_60_days=len(expiring_60),
            expiring_90_days=len(expiring_90),
            past_notice_deadline=len(past_notice),
            total_value_at_risk=value_at_risk,
            expired_count=expired_count,
            no_date_count=no_date_count,
            total_contracts=len(contracts),
            upcoming_renewals=upcoming_renewals,
        )
        return widget, past_notice

    def _build_vendor_widget(self, contracts, obligations, slas, today=None):
        """Build the vendor widget from contract/obligation/SLA data."""
        if today is None:
            today = date.today()

        # Group counterparties into distinct entities the same way the Vendors
        # page does (organization_id, else canonical name key) — otherwise the
        # same vendor fragments across name variants (e.g. "ING", "ING Bank N.V.",
        # "ING Group") and the count/scores are inflated and inconsistent.
        from collections import defaultdict
        from app.services.org_resolver import canonical_org_key
        from app.agents.metadata_extraction import clean_counterparty

        groups: dict = defaultdict(list)
        for c in contracts:
            if not c.counterparty:
                continue
            if c.organization_id is not None:
                key = ("org", str(c.organization_id))
            else:
                cleaned = clean_counterparty(c.counterparty) or c.counterparty
                key = ("cp", canonical_org_key(cleaned) or cleaned.lower())
            groups[key].append(c)

        vendor_scores = []
        for _key, cp_contracts in groups.items():
            cp = clean_counterparty(cp_contracts[0].counterparty) or cp_contracts[0].counterparty
            cp_contract_ids = [c.id for c in cp_contracts]

            # Obligation compliance — same definition the Vendors page uses
            # (vendor_service.calculate_obligation_compliance): rate over the
            # *assessable* obligations (completed + in_progress + overdue by
            # stored status), and None (unrated) until something is actually
            # tracked. Keeps the dashboard widget and the Vendors page in agreement
            # instead of one deriving overdue from deadlines and the other not.
            cp_obls = [o for o in obligations if o.contract_id in cp_contract_ids]
            cp_completed = sum(1 for o in cp_obls if o.status == ObligationStatus.COMPLETED)
            cp_in_progress = sum(1 for o in cp_obls if o.status == ObligationStatus.IN_PROGRESS)
            cp_overdue = sum(1 for o in cp_obls if o.status == ObligationStatus.OVERDUE)
            assessable = cp_completed + cp_in_progress + cp_overdue
            obl_rate = ((cp_completed + cp_in_progress) / assessable * 100) if assessable > 0 else None

            cp_slas = [s for s in slas if s.contract_id in cp_contract_ids]
            cp_sla_rates = [float(s.current_compliance_rate) for s in cp_slas if s.current_compliance_rate is not None]
            sla_rate = sum(cp_sla_rates) / len(cp_sla_rates) if cp_sla_rates else None

            # Score from real signals only; None (unrated) when neither exists.
            comps = [r for r in (obl_rate, sla_rate) if r is not None]
            score = round(sum(comps) / len(comps), 2) if comps else None
            vendor_scores.append({
                "name": cp,
                "score": score,
                "contracts": len(cp_contracts),
            })

        rated = [v for v in vendor_scores if v["score"] is not None]
        rated.sort(key=lambda v: v["score"], reverse=True)
        at_risk_vendors = sum(1 for v in rated if v["score"] < 60)
        avg_score = round(sum(v["score"] for v in rated) / len(rated), 2) if rated else None

        return VendorWidget(
            total_vendors=len(groups),
            at_risk_vendors=at_risk_vendors,
            avg_performance_score=avg_score,
            top_performers=rated[:3],
            bottom_performers=rated[-3:][::-1] if len(rated) >= 3 else rated[::-1],
        )

    def _build_milestone_widget(self, obligations, today):
        """Build the milestone widget from obligation data."""
        milestones = [o for o in obligations if o.deadline]
        ms_total = len(milestones)
        ms_completed = sum(1 for o in milestones if o.status == ObligationStatus.COMPLETED)
        ms_overdue = sum(1 for o in milestones if self._is_overdue(o, today))
        ms_at_risk = sum(
            1 for o in milestones
            if not self._is_overdue(o, today)
            and o.status not in (ObligationStatus.COMPLETED, ObligationStatus.WAIVED)
            and o.deadline and 0 <= (o.deadline - today).days <= 7
        )
        # Honest: None when there are no milestones (not a fake 100% complete).
        ms_completion_rate = round(ms_completed / ms_total * 100, 2) if ms_total > 0 else None

        week_end = today + timedelta(days=7)
        due_this_week_obls = [
            o for o in milestones
            if o.deadline and today <= o.deadline <= week_end
            and o.status != ObligationStatus.COMPLETED
        ]
        due_this_week_obls.sort(key=lambda o: o.deadline or date.max)

        due_this_week = [
            {
                "id": str(o.id),
                "title": o.description[:100] if o.description else "No description",
                "due_date": o.deadline.isoformat() if o.deadline else None,
                "status": self._effective_status(o, today),
            }
            for o in due_this_week_obls[:5]
        ]

        return MilestoneWidget(
            total_milestones=ms_total,
            completed=ms_completed,
            at_risk=ms_at_risk,
            overdue=ms_overdue,
            completion_rate=ms_completion_rate,  # already rounded; None when no milestones
            due_this_week=due_this_week,
        )

    async def _load_scoring_config(self) -> dict:
        """Resolve At-Risk/Compliance scoring rules: default -> tenant -> BU."""
        from app.models.tenant import Tenant
        from app.models.business_unit import BusinessUnit
        from app.services.scoring_config import resolve_scoring_config

        sources: list[dict] = []
        if self.tenant_id:
            t = await self.db.get(Tenant, self.tenant_id)
            if t and t.config_overrides:
                sources.append(t.config_overrides)
        if self.business_unit_id:
            bu = await self.db.get(BusinessUnit, self.business_unit_id)
            if bu and bu.config_overrides:
                sources.append(bu.config_overrides)
        return resolve_scoring_config(*sources)

    async def get_dashboard(self) -> PostSigningDashboard:
        """Build the complete post-signing dashboard."""
        today = date.today()
        now = datetime.utcnow()

        self.scoring = await self._load_scoring_config()

        contracts = await self._fetch_contracts()
        obligations = await self._fetch_obligations()
        slas = await self._fetch_slas()

        total_contracts = len(contracts)
        # Never sum across currencies. Group by currency, headline the dominant
        # (largest) subtotal, and expose the full breakdown + coverage (how many
        # contracts actually have a recorded value) so the figure is honest.
        value_by_currency: dict[str, float] = {}
        valued_contracts = 0
        for c in contracts:
            if c.contract_value:
                cur = (c.currency or "USD").upper()
                value_by_currency[cur] = value_by_currency.get(cur, 0.0) + float(c.contract_value)
                valued_contracts += 1
        if value_by_currency:
            total_value_currency, total_value = max(value_by_currency.items(), key=lambda kv: kv[1])
            total_value = round(total_value, 2)
        else:
            total_value_currency, total_value = "USD", 0.0
        total_value_by_currency = {k: round(v, 2) for k, v in value_by_currency.items()}

        # Build widgets
        obl_widget, obl_compliance, obl_overdue, urgent_obls = self._build_obligation_widget(obligations, today)
        sla_widget, sla_compliance, sla_breached, recent_breaches = await self._build_sla_widget(slas, contracts, today)
        renewal_widget, past_notice = self._build_renewal_widget(contracts, today)
        vendor_widget = self._build_vendor_widget(contracts, obligations, slas, today)
        milestone_widget = self._build_milestone_widget(obligations, today)

        # Compliance widget — weighted blend of the measured components only.
        # Weights are tenant/BU-configurable (default obligations 0.6 / SLA 0.4).
        comp_cfg = self.scoring["compliance"]
        _measured = [
            (v, w) for v, w in (
                (obl_compliance, comp_cfg["obligation_weight"]),
                (sla_compliance, comp_cfg["sla_weight"]),
            ) if v is not None
        ]
        overall_compliance = (
            round(sum(v * w for v, w in _measured) / sum(w for _, w in _measured), 2)
            if _measured and sum(w for _, w in _measured) > 0 else None
        )

        # Contracts at risk — tenant/BU-configurable definition + thresholds.
        ar = self.scoring["at_risk"]
        definition = ar["definition"]
        count_th = ar["overdue_count_threshold"]
        ratio_th = ar["overdue_ratio_threshold"]
        risk_levels = {str(x).lower() for x in ar["risk_levels"]}
        contracts_at_risk = 0
        for c in contracts:
            at_risk = False
            if definition in ("obligations", "both"):
                c_obls = [o for o in obligations if o.contract_id == c.id]
                c_overdue = sum(1 for o in c_obls if self._is_overdue(o, today))
                if c_overdue >= count_th or (len(c_obls) > 0 and c_overdue / len(c_obls) > ratio_th):
                    at_risk = True
            if not at_risk and definition in ("risk_level", "both") and c.risk_level is not None:
                lvl = c.risk_level.value if hasattr(c.risk_level, "value") else str(c.risk_level)
                if lvl.lower() in risk_levels:
                    at_risk = True
            if at_risk:
                contracts_at_risk += 1

        high_priority = obl_overdue + sla_breached + len(past_notice)

        compliance_widget = ComplianceWidget(
            overall_compliance_rate=overall_compliance,
            obligation_compliance_rate=obl_compliance,
            sla_compliance_rate=sla_compliance,
            trend=None,
            change_from_last_month=None,
            contracts_at_risk=contracts_at_risk,
            high_priority_actions=high_priority,
        )

        # Priority actions
        priority_actions = []
        for o in urgent_obls[:3]:
            is_od = self._is_overdue(o, today)
            priority_actions.append({
                "type": "obligation",
                "severity": "high" if is_od else "medium",
                "title": f"{'Overdue' if is_od else 'Upcoming'}: {o.description[:50] if o.description else 'Obligation'}",
                "action": "Review and complete obligation",
                "due_date": o.deadline.isoformat() if o.deadline else None,
                "obligation_id": str(o.id),
                "contract_id": str(o.contract_id),
            })
        for breach in recent_breaches[:2]:
            if breach["severity"] == "critical":
                priority_actions.append({
                    "type": "sla",
                    "severity": "critical",
                    "title": f"SLA Breach: {breach['sla_name']}",
                    "action": "Escalate and remediate immediately",
                    "contract": breach["contract"],
                    "sla_id": breach["sla_id"],
                    "contract_id": breach["contract_id"],
                })
        for c in past_notice[:2]:
            priority_actions.append({
                "type": "renewal",
                "severity": "high",
                "title": f"Renewal: {c.filename}",
                "action": "Make renewal decision - past notice deadline",
                "expiration": c.expiration_date.isoformat() if c.expiration_date else None,
                "contract_id": str(c.id),
            })

        contracts_needing_attention = contracts_at_risk + len(past_notice)

        return PostSigningDashboard(
            generated_at=now,
            as_of_date=today,
            obligations=obl_widget,
            slas=sla_widget,
            renewals=renewal_widget,
            vendors=vendor_widget,
            milestones=milestone_widget,
            compliance=compliance_widget,
            total_contracts=total_contracts,
            total_value=total_value,
            total_value_currency=total_value_currency,
            total_value_by_currency=total_value_by_currency,
            valued_contracts=valued_contracts,
            contracts_needing_attention=contracts_needing_attention,
            priority_actions=priority_actions[:10],
        )

    async def get_obligation_details(self, status_filter=None, rag_filter=None):
        """Get detailed obligation list with optional filters."""
        today = date.today()
        query = (
            select(Obligation, Contract)
            .join(Contract, Obligation.contract_id == Contract.id)
            .where(Contract.status == ContractStatus.COMPLETED)
        )
        query = self._apply_filters(query)

        if status_filter:
            if status_filter == "overdue":
                query = query.where(
                    Obligation.deadline < today,
                    Obligation.status.notin_([ObligationStatus.COMPLETED, ObligationStatus.WAIVED]),
                )
            else:
                query = query.where(Obligation.status == ObligationStatus(status_filter))
        if rag_filter:
            if rag_filter == "red":
                # Also include overdue obligations in RED filter
                from sqlalchemy import or_
                query = query.where(
                    or_(
                        Obligation.rag_status == RAGStatus.RED,
                        (Obligation.deadline < today) & Obligation.status.notin_([ObligationStatus.COMPLETED, ObligationStatus.WAIVED]),
                    )
                )
            else:
                query = query.where(Obligation.rag_status == RAGStatus(rag_filter))

        query = query.order_by(Obligation.deadline)
        result = await self.db.execute(query)
        rows = result.all()

        today_val = today
        return [
            {
                "id": str(o.id),
                "contract_id": str(c.id),
                "contract_filename": c.filename,
                "counterparty": c.counterparty,
                "title": o.description[:100] if o.description else "No description",
                "description": o.description,
                "category": o.category.value if o.category else None,
                "owner": o.obligated_party,
                "due_date": o.deadline.isoformat() if o.deadline else None,
                "status": "overdue" if (o.deadline and o.deadline < today_val and o.status not in (ObligationStatus.COMPLETED, ObligationStatus.WAIVED)) else (o.status.value if o.status else "pending"),
                "rag_status": o.rag_status.value if o.rag_status else None,
                "has_evidence": bool(o.compliance_evidence),
                "assigned_user_id": str(o.assigned_user_id) if o.assigned_user_id else None,
            }
            for o, c in rows
        ]

    async def get_sla_details(self, breached_only=False):
        """Get detailed SLA list with optional filters."""
        query = (
            select(ContractSLA, Contract)
            .join(Contract, ContractSLA.contract_id == Contract.id)
            .where(
                and_(
                    Contract.status == ContractStatus.COMPLETED,
                    ContractSLA.is_active == True,
                )
            )
        )
        query = self._apply_filters(query)

        if breached_only:
            query = query.where(ContractSLA.consecutive_breaches > 0)

        query = query.order_by(ContractSLA.consecutive_breaches.desc())
        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "id": str(s.id),
                "contract_id": str(c.id),
                "contract_filename": c.filename,
                "counterparty": c.counterparty,
                "sla_name": s.sla_name,
                "metric_type": s.metric_type.value if s.metric_type else None,
                "target_value": float(s.target_value) if s.target_value else None,
                "compliance_rate": float(s.current_compliance_rate) if s.current_compliance_rate else None,
                "consecutive_breaches": s.consecutive_breaches,
                "severity": s.severity.value if s.severity else "medium",
                "has_penalty": s.has_penalty,
            }
            for s, c in rows
        ]

    async def get_milestone_details(self):
        """Get all obligations that have deadlines (i.e., milestones)."""
        today = date.today()
        query = (
            select(Obligation, Contract)
            .join(Contract, Obligation.contract_id == Contract.id)
            .where(
                and_(
                    Contract.status == ContractStatus.COMPLETED,
                    Obligation.deadline.isnot(None),
                )
            )
        )
        query = self._apply_filters(query)
        query = query.order_by(Obligation.deadline)
        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "id": str(o.id),
                "contract_id": str(c.id),
                "contract_filename": c.filename,
                "counterparty": c.counterparty,
                "title": o.description[:100] if o.description else "No description",
                "due_date": o.deadline.isoformat() if o.deadline else None,
                "status": self._effective_status(o, today),
                "category": o.category.value if o.category else None,
                "owner": o.obligated_party,
            }
            for o, c in rows
        ]

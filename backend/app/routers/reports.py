"""Compliance Reporting API endpoints.

Thin HTTP handlers delegating to reporting_service for data access.
"""

import csv
import io
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, CurrentTenantId
from app.database import get_db
from app.models import ObligationStatus
from app.schemas.report import (
    ObligationReportItem,
    SLAReportItem,
    ComplianceReportSummary,
    ComplianceReportResponse,
    TrendDataPoint,
    ComplianceTrendResponse,
    ExportRequest,
)
from app.services.reporting_service import (
    get_obligations_in_period,
    get_sla_aggregates_in_period,
    determine_trend,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/compliance", response_model=ComplianceReportResponse)
async def get_compliance_report(
    start_date: date = Query(..., description="Report start date"),
    end_date: date = Query(..., description="Report end date"),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate compliance report for a date range.

    Includes obligations and SLA performance data with summary statistics.
    """
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be after start_date"
        )

    # Get obligations
    bu_id = current_user.business_unit_id if current_user else None
    bu_role = current_user.role.value if current_user and current_user.role else None
    obl_rows = await get_obligations_in_period(db, start_date, end_date, tenant_id, bu_id, bu_role)

    obligation_items = []
    obligations_completed = 0
    obligations_overdue = 0
    obligations_on_time = 0

    by_contract: dict[str, dict] = {}
    by_category: dict[str, dict] = {}

    for obligation, contract in obl_rows:
        was_on_time = None
        if obligation.last_compliance_date and obligation.deadline:
            was_on_time = obligation.last_compliance_date <= obligation.deadline
            if was_on_time:
                obligations_on_time += 1

        if obligation.status == ObligationStatus.COMPLETED:
            obligations_completed += 1
        elif obligation.status == ObligationStatus.OVERDUE:
            obligations_overdue += 1

        item = ObligationReportItem(
            obligation_id=str(obligation.id),
            contract_id=str(contract.id),
            contract_filename=contract.filename,
            counterparty=contract.counterparty,
            title=obligation.description[:100] if obligation.description else "No description",
            category=obligation.category.value if obligation.category else None,
            owner=obligation.obligated_party,
            due_date=obligation.deadline,
            completed_date=obligation.last_compliance_date,
            status=obligation.status.value if obligation.status else "pending",
            rag_status=obligation.rag_status.value if obligation.rag_status else None,
            was_on_time=was_on_time,
        )
        obligation_items.append(item)

        # Track by contract
        cid = str(contract.id)
        if cid not in by_contract:
            by_contract[cid] = {
                "filename": contract.filename,
                "obligation_total": 0,
                "obligation_completed": 0,
                "sla_total": 0,
                "sla_compliant": 0,
            }
        by_contract[cid]["obligation_total"] += 1
        if obligation.status == ObligationStatus.COMPLETED:
            by_contract[cid]["obligation_completed"] += 1

        # Track by category
        cat = obligation.category.value if obligation.category else "uncategorized"
        if cat not in by_category:
            by_category[cat] = {"total": 0, "completed": 0, "compliance_rate": 0}
        by_category[cat]["total"] += 1
        if obligation.status == ObligationStatus.COMPLETED:
            by_category[cat]["completed"] += 1

    # Calculate category compliance rates
    for cat in by_category:
        total = by_category[cat]["total"]
        completed = by_category[cat]["completed"]
        by_category[cat]["compliance_rate"] = (completed / total * 100) if total > 0 else 0

    # Get SLA aggregates (SQL-level aggregation — no N+1)
    sla_aggregates = await get_sla_aggregates_in_period(db, start_date, end_date, tenant_id, bu_id, bu_role)

    sla_items = []
    slas_compliant = 0
    slas_breached = 0
    total_penalties = 0.0

    for agg in sla_aggregates:
        compliance_rate = (agg["compliant_count"] / agg["total_count"] * 100) if agg["total_count"] > 0 else 0
        is_compliant = compliance_rate >= 80  # SLA meets target if >= 80% of measurements pass

        if is_compliant:
            slas_compliant += 1
        else:
            slas_breached += 1

        total_penalties += agg["total_penalties"]

        item = SLAReportItem(
            sla_id=agg["sla_id"],
            contract_id=agg["contract_id"],
            contract_filename=agg["contract_filename"],
            counterparty=agg["counterparty"],
            sla_name=agg["sla_name"],
            metric_type=agg["metric_type"],
            target_value=agg["target_value"],
            actual_value=agg["current_compliance_rate"],
            compliance_rate=compliance_rate,
            is_compliant=is_compliant,
            breaches_in_period=agg["breach_count"],
            penalties_in_period=agg["total_penalties"],
        )
        sla_items.append(item)

        # Track unique SLAs per contract
        cid = agg["contract_id"]
        if cid not in by_contract:
            by_contract[cid] = {
                "filename": agg["contract_filename"],
                "obligation_total": 0,
                "obligation_completed": 0,
                "sla_total": 0,
                "sla_compliant": 0,
            }
        by_contract[cid]["sla_total"] += 1
        if is_compliant:
            by_contract[cid]["sla_compliant"] += 1

    # Calculate compliance rates
    total_obligations = len(obligation_items)
    obligation_compliance_rate = (obligations_completed / total_obligations * 100) if total_obligations > 0 else 100.0

    total_slas = len(sla_aggregates)
    sla_compliance_rate = (slas_compliant / total_slas * 100) if total_slas > 0 else 100.0

    overall_compliance_rate = (obligation_compliance_rate * 0.6 + sla_compliance_rate * 0.4)

    # Count unique contracts and high-risk
    contracts_reviewed = len(by_contract)
    high_risk = sum(1 for cid, data in by_contract.items()
                    if (data["obligation_total"] > 0 and
                        data["obligation_completed"] / data["obligation_total"] < 0.5))

    summary = ComplianceReportSummary(
        report_period_start=start_date,
        report_period_end=end_date,
        generated_at=datetime.utcnow(),
        total_obligations=total_obligations,
        obligations_completed=obligations_completed,
        obligations_overdue=obligations_overdue,
        obligations_on_time=obligations_on_time,
        obligation_compliance_rate=round(obligation_compliance_rate, 2),
        total_slas=total_slas,
        slas_compliant=slas_compliant,
        slas_breached=slas_breached,
        sla_compliance_rate=round(sla_compliance_rate, 2),
        total_penalties=total_penalties,
        overall_compliance_rate=round(overall_compliance_rate, 2),
        contracts_reviewed=contracts_reviewed,
        high_risk_contracts=high_risk,
    )

    # Calculate contract compliance rates
    for cid in by_contract:
        data = by_contract[cid]
        obl_rate = (data["obligation_completed"] / data["obligation_total"] * 100) if data["obligation_total"] > 0 else 0
        sla_rate = (data["sla_compliant"] / data["sla_total"] * 100) if data["sla_total"] > 0 else 0
        data["obligation_rate"] = obl_rate
        data["sla_rate"] = sla_rate

    return ComplianceReportResponse(
        summary=summary,
        obligations=obligation_items,
        slas=sla_items,
        by_contract=by_contract,
        by_category=by_category,
    )


@router.get("/compliance/trend", response_model=ComplianceTrendResponse)
async def get_compliance_trend(
    period: str = Query("weekly", pattern="^(weekly|monthly)$"),
    lookback: int = Query(4, ge=1, le=12, description="Number of periods to look back"),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get compliance trend over time.

    Shows how compliance rates have changed over the specified periods.
    """
    today = date.today()
    data_points = []

    obligation_rates = []
    sla_rates = []
    overall_rates = []

    for i in range(lookback - 1, -1, -1):
        if period == "weekly":
            end = today - timedelta(weeks=i)
            start = end - timedelta(days=6)
            label = f"Week {lookback - i}"
        else:  # monthly
            # Go back i months
            month = today.month - i
            year = today.year
            while month <= 0:
                month += 12
                year -= 1
            start = date(year, month, 1)
            if month == 12:
                end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end = date(year, month + 1, 1) - timedelta(days=1)
            label = start.strftime("%b %Y")

        # Get report for this period
        report = await get_compliance_report(start, end, current_user, tenant_id, db)

        point = TrendDataPoint(
            period_start=start,
            period_end=end,
            period_label=label,
            obligation_compliance_rate=report.summary.obligation_compliance_rate,
            sla_compliance_rate=report.summary.sla_compliance_rate,
            overall_compliance_rate=report.summary.overall_compliance_rate,
            obligations_completed=report.summary.obligations_completed,
            obligations_overdue=report.summary.obligations_overdue,
            sla_breaches=report.summary.slas_breached,
            penalties=report.summary.total_penalties,
        )
        data_points.append(point)

        obligation_rates.append(report.summary.obligation_compliance_rate)
        sla_rates.append(report.summary.sla_compliance_rate)
        overall_rates.append(report.summary.overall_compliance_rate)

    # Determine trends
    obligation_trend = determine_trend(obligation_rates)
    sla_trend = determine_trend(sla_rates)
    overall_trend = determine_trend(overall_rates)

    # Calculate change percentages
    obligation_change = obligation_rates[-1] - obligation_rates[0] if len(obligation_rates) >= 2 else 0
    sla_change = sla_rates[-1] - sla_rates[0] if len(sla_rates) >= 2 else 0
    overall_change = overall_rates[-1] - overall_rates[0] if len(overall_rates) >= 2 else 0

    return ComplianceTrendResponse(
        trend_type=period,
        data_points=data_points,
        obligation_trend=obligation_trend,
        sla_trend=sla_trend,
        overall_trend=overall_trend,
        obligation_change_pct=round(obligation_change, 2),
        sla_change_pct=round(sla_change, 2),
        overall_change_pct=round(overall_change, 2),
    )


@router.get("/compliance/export")
async def export_compliance_report(
    start_date: date = Query(...),
    end_date: date = Query(...),
    format: str = Query("csv", pattern="^(csv|excel)$"),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Export compliance report to CSV or Excel format.

    Returns a downloadable file.
    """
    report = await get_compliance_report(start_date, end_date, current_user, tenant_id, db)

    if format == "csv":
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Summary section
        writer.writerow(["COMPLIANCE REPORT"])
        writer.writerow(["Period", f"{start_date} to {end_date}"])
        writer.writerow(["Generated", datetime.utcnow().isoformat()])
        writer.writerow([])

        writer.writerow(["SUMMARY"])
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Obligations", report.summary.total_obligations])
        writer.writerow(["Obligations Completed", report.summary.obligations_completed])
        writer.writerow(["Obligations Overdue", report.summary.obligations_overdue])
        writer.writerow(["Obligation Compliance Rate", f"{report.summary.obligation_compliance_rate}%"])
        writer.writerow(["Total SLAs", report.summary.total_slas])
        writer.writerow(["SLAs Compliant", report.summary.slas_compliant])
        writer.writerow(["SLAs Breached", report.summary.slas_breached])
        writer.writerow(["SLA Compliance Rate", f"{report.summary.sla_compliance_rate}%"])
        writer.writerow(["Total Penalties", f"${report.summary.total_penalties:,.2f}"])
        writer.writerow(["Overall Compliance Rate", f"{report.summary.overall_compliance_rate}%"])
        writer.writerow([])

        # Obligations section
        writer.writerow(["OBLIGATIONS"])
        writer.writerow(["Contract", "Counterparty", "Title", "Category", "Owner", "Due Date", "Status", "RAG", "On Time"])
        for obl in report.obligations:
            writer.writerow([
                obl.contract_filename,
                obl.counterparty or "",
                obl.title,
                obl.category or "",
                obl.owner or "",
                obl.due_date.isoformat() if obl.due_date else "",
                obl.status,
                obl.rag_status or "",
                "Yes" if obl.was_on_time else ("No" if obl.was_on_time is False else ""),
            ])
        writer.writerow([])

        # SLAs section
        writer.writerow(["SLAs"])
        writer.writerow(["Contract", "Counterparty", "SLA Name", "Metric", "Target", "Compliance Rate", "Breaches", "Penalties"])
        for sla in report.slas:
            writer.writerow([
                sla.contract_filename,
                sla.counterparty or "",
                sla.sla_name,
                sla.metric_type,
                sla.target_value,
                f"{sla.compliance_rate:.1f}%" if sla.compliance_rate else "",
                sla.breaches_in_period,
                f"${sla.penalties_in_period:,.2f}",
            ])

        output.seek(0)
        filename = f"compliance_report_{start_date}_{end_date}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    else:
        # For Excel, we'd need openpyxl - return CSV for now with a note
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Excel export requires openpyxl. Use CSV format or install openpyxl."
        )


@router.get("/summary")
async def get_quick_summary(
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a quick compliance summary for the current month.
    """
    today = date.today()
    start_of_month = date(today.year, today.month, 1)

    report = await get_compliance_report(start_of_month, today, current_user, tenant_id, db)

    return {
        "period": f"{start_of_month} to {today}",
        "overall_compliance": report.summary.overall_compliance_rate,
        "obligation_compliance": report.summary.obligation_compliance_rate,
        "sla_compliance": report.summary.sla_compliance_rate,
        "obligations_overdue": report.summary.obligations_overdue,
        "slas_breached": report.summary.slas_breached,
        "total_penalties": report.summary.total_penalties,
        "high_risk_contracts": report.summary.high_risk_contracts,
    }

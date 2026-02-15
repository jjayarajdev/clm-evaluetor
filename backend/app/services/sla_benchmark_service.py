"""SLA Benchmark Service - Stores structured SLA data from Excel files.

Integrates the Excel SLA parser with database storage.
"""

import logging
import uuid
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sla import ContractSLA, SLAMetricType, SLASeverity, SLAUnit
from app.services.excel_sla_parser import (
    ExcelSLAParseResult,
    ParsedSLAMetric,
    get_excel_sla_parser,
)

logger = logging.getLogger(__name__)


async def extract_and_store_excel_slas(
    db: AsyncSession,
    contract_id: uuid.UUID,
    file_path: str,
) -> int:
    """Extract SLA metrics from Excel file and store in database.

    Args:
        db: Database session.
        contract_id: Contract ID to link SLAs to.
        file_path: Path to the Excel file.

    Returns:
        Number of SLA metrics stored.
    """
    path = Path(file_path)

    # Check if this is an Excel file
    if path.suffix.lower() not in (".xlsx", ".xls"):
        return 0

    parser = get_excel_sla_parser()

    # Check if this is an SLA-related file
    if not parser.is_sla_file(path.name):
        logger.info(f"Skipping non-SLA Excel file: {path.name}")
        return 0

    logger.info(f"Parsing SLA Excel file: {path.name}")

    # Parse the file
    result = parser.parse_file(file_path)

    if not result.success:
        logger.warning(f"Failed to parse SLA Excel: {result.parse_errors}")
        return 0

    # Store metrics
    stored_count = await store_sla_metrics(db, contract_id, result)

    logger.info(
        f"Stored {stored_count} SLA metrics from {path.name} "
        f"(type: {result.file_type}, {len(result.examples)} examples)"
    )

    return stored_count


async def store_sla_metrics(
    db: AsyncSession,
    contract_id: uuid.UUID,
    result: ExcelSLAParseResult,
) -> int:
    """Store parsed SLA metrics in the database.

    Args:
        db: Database session.
        contract_id: Contract ID.
        result: Parsed Excel result.

    Returns:
        Number of records created.
    """
    created_count = 0

    for metric in result.metrics:
        try:
            sla = _create_sla_from_metric(contract_id, metric, result)
            db.add(sla)
            created_count += 1
        except Exception as e:
            logger.warning(f"Error creating SLA from metric: {e}")

    # Also store examples as SLA definitions with benchmark data
    for example in result.examples:
        try:
            # Examples provide insight into earnback/default conditions
            # Store as a note in the SLA description
            logger.debug(
                f"Example {example.example_number}: {example.description} "
                f"(default={example.has_default}, earnback={example.has_earnback})"
            )
        except Exception as e:
            logger.warning(f"Error processing SLA example: {e}")

    await db.flush()
    return created_count


def _create_sla_from_metric(
    contract_id: uuid.UUID,
    metric: ParsedSLAMetric,
    result: ExcelSLAParseResult,
) -> ContractSLA:
    """Create ContractSLA from parsed metric.

    Args:
        contract_id: Contract ID.
        metric: Parsed SLA metric.
        result: Full parse result for context.

    Returns:
        ContractSLA instance.
    """
    # Determine metric type from name
    metric_type = _infer_metric_type(metric.sla_name)

    # Determine severity from category
    severity = SLASeverity.MEDIUM
    if metric.is_critical:
        severity = SLASeverity.CRITICAL
    elif metric.category and "key" in metric.category.lower():
        severity = SLASeverity.HIGH

    # Use expected value as target
    target_value = metric.expected_value or Decimal("0.95")

    # Check if penalty applies (at-risk percentage set)
    has_penalty = metric.at_risk_percentage is not None and metric.at_risk_percentage > 0

    sla = ContractSLA(
        contract_id=contract_id,
        sla_name=metric.sla_name[:200],  # Truncate to fit
        sla_description=metric.sla_description,
        section_reference=metric.section_reference,
        category=metric.category,
        service_tower=metric.service_tower,
        metric_type=metric_type,
        metric_unit=SLAUnit.PERCENTAGE,
        target_value=target_value,
        target_operator=">=",
        warning_threshold=metric.minimum_value,  # Minimum as warning
        minimum_service_level=metric.minimum_value,
        severity=severity,
        has_penalty=has_penalty,
        penalty_type="percentage" if has_penalty else None,
        at_risk_percentage=metric.at_risk_percentage,
        earnback_eligible=False,  # Will be updated from examples
        measurement_period=metric.measurement_window,
        is_active=True,
        source_text=f"Sheet: {metric.source_sheet}, Row: {metric.source_row}",
    )

    return sla


def _infer_metric_type(sla_name: str) -> SLAMetricType:
    """Infer metric type from SLA name.

    Args:
        sla_name: Name of the SLA.

    Returns:
        Appropriate SLAMetricType.
    """
    name_lower = sla_name.lower()

    if "availability" in name_lower or "uptime" in name_lower:
        return SLAMetricType.AVAILABILITY
    if "response" in name_lower:
        return SLAMetricType.RESPONSE_TIME
    if "resolution" in name_lower:
        return SLAMetricType.RESOLUTION_TIME
    if "delivery" in name_lower:
        return SLAMetricType.DELIVERY_TIME
    if "throughput" in name_lower or "volume" in name_lower:
        return SLAMetricType.THROUGHPUT
    if "error" in name_lower or "failure" in name_lower:
        return SLAMetricType.ERROR_RATE
    if "quality" in name_lower or "accuracy" in name_lower:
        return SLAMetricType.QUALITY_SCORE

    return SLAMetricType.CUSTOM


async def update_earnback_from_examples(
    db: AsyncSession,
    contract_id: uuid.UUID,
    result: ExcelSLAParseResult,
) -> None:
    """Update SLA earnback eligibility based on parsed examples.

    Args:
        db: Database session.
        contract_id: Contract ID.
        result: Parse result with examples.
    """
    if not result.examples:
        return

    # Check if any example shows earnback
    has_earnback_example = any(ex.has_earnback for ex in result.examples)

    if has_earnback_example:
        # Get example with earnback for conditions
        earnback_example = next(ex for ex in result.examples if ex.has_earnback)

        # Build conditions description
        conditions = f"Earnback scenario: {earnback_example.description}"
        if earnback_example.minimum_threshold:
            conditions += f"\nMinimum threshold: {earnback_example.minimum_threshold}"

        # Update all SLAs for this contract to indicate earnback eligibility
        from sqlalchemy import update

        await db.execute(
            update(ContractSLA)
            .where(ContractSLA.contract_id == contract_id)
            .values(
                earnback_eligible=True,
                earnback_conditions=conditions,
            )
        )

        logger.info(f"Updated earnback eligibility for contract {contract_id}")

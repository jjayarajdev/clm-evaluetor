"""Calculation Service - Computes service credits and penalties.

Handles:
- SLA breach service credit calculations
- Penalty computations based on contract terms
- Formula evaluation
- Cap enforcement
"""

import logging
import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.event import Event
from app.models.sla import ContractSLA

logger = logging.getLogger(__name__)


class CalculationService:
    """Service for financial calculations related to contracts."""

    def __init__(self, db: AsyncSession):
        """Initialize calculation service.

        Args:
            db: Database session.
        """
        self.db = db

    async def calculate_service_credit(
        self,
        event: Event,
        config: Optional[dict] = None,
    ) -> dict:
        """Calculate service credit for an SLA breach event.

        Args:
            event: The SLA breach event.
            config: Optional calculation configuration overrides.

        Returns:
            Calculation result with credit amount and details.
        """
        config = config or {}

        # Get event details
        details = event.details or {}

        # Extract key values
        deviation_percent = abs(details.get("deviation_percent", 0))
        contract_value = details.get("contract_value", 0)

        # Get SLA-specific penalties if available
        sla = None
        if event.sla_id:
            result = await self.db.execute(
                select(ContractSLA).where(ContractSLA.id == event.sla_id)
            )
            sla = result.scalar_one_or_none()

        # Determine credit calculation method
        if sla and sla.has_penalty:
            credit_result = self._calculate_from_sla(
                sla=sla,
                deviation_percent=deviation_percent,
                contract_value=contract_value,
            )
        else:
            credit_result = self._calculate_default(
                deviation_percent=deviation_percent,
                contract_value=contract_value,
                config=config,
            )

        # Apply any caps
        max_credit = config.get("max_credit")
        if max_credit and credit_result["credit_amount"] > max_credit:
            credit_result["credit_amount"] = max_credit
            credit_result["capped"] = True

        # Round to 2 decimal places
        credit_result["credit_amount"] = round(credit_result["credit_amount"], 2)

        logger.info(
            f"Calculated service credit: ${credit_result['credit_amount']} "
            f"(deviation: {deviation_percent}%, method: {credit_result['method']})"
        )

        return credit_result

    def _calculate_from_sla(
        self,
        sla: ContractSLA,
        deviation_percent: float,
        contract_value: float,
    ) -> dict:
        """Calculate credit using SLA-defined penalty terms.

        Args:
            sla: The SLA with penalty terms.
            deviation_percent: Deviation from target.
            contract_value: Contract value for percentage calculations.

        Returns:
            Calculation result.
        """
        penalty_type = sla.penalty_type or "percentage"
        penalty_value = float(sla.penalty_value) if sla.penalty_value else 0
        max_cap = float(sla.max_penalty_cap) if sla.max_penalty_cap else None

        if penalty_type == "fixed":
            # Fixed credit per breach
            credit_amount = penalty_value

        elif penalty_type == "percentage":
            # Percentage of contract value
            credit_amount = contract_value * (penalty_value / 100)

        elif penalty_type == "tiered":
            # Tiered based on deviation severity
            credit_amount = self._calculate_tiered_credit(
                deviation_percent=deviation_percent,
                contract_value=contract_value,
                base_rate=penalty_value,
            )

        elif penalty_type == "credit":
            # Direct service credit based on deviation
            credit_amount = deviation_percent * penalty_value

        else:
            # Default: deviation * rate
            credit_amount = deviation_percent * contract_value * 0.001

        # Apply SLA cap
        if max_cap and credit_amount > max_cap:
            credit_amount = max_cap

        return {
            "credit_amount": credit_amount,
            "method": f"sla_{penalty_type}",
            "penalty_type": penalty_type,
            "penalty_value": penalty_value,
            "deviation_percent": deviation_percent,
            "contract_value": contract_value,
            "capped": max_cap is not None and credit_amount >= max_cap,
        }

    def _calculate_default(
        self,
        deviation_percent: float,
        contract_value: float,
        config: dict,
    ) -> dict:
        """Calculate credit using default formula.

        Default formula: deviation% * contract_value * credit_rate

        Args:
            deviation_percent: Deviation from target.
            contract_value: Contract value.
            config: Configuration with rates.

        Returns:
            Calculation result.
        """
        credit_rate = config.get("credit_rate", 0.01)  # 1% per percentage point default
        formula = config.get("formula", "deviation_percent * contract_value * credit_rate")

        # Evaluate formula
        try:
            credit_amount = self._evaluate_formula(
                formula=formula,
                variables={
                    "deviation_percent": deviation_percent / 100,  # Convert to decimal
                    "contract_value": contract_value,
                    "credit_rate": credit_rate,
                    "breach_percentage": deviation_percent / 100,
                }
            )
        except Exception as e:
            logger.warning(f"Formula evaluation failed: {e}, using simple calculation")
            credit_amount = (deviation_percent / 100) * contract_value * credit_rate

        return {
            "credit_amount": credit_amount,
            "method": "default_formula",
            "formula": formula,
            "credit_rate": credit_rate,
            "deviation_percent": deviation_percent,
            "contract_value": contract_value,
            "capped": False,
        }

    def _calculate_tiered_credit(
        self,
        deviation_percent: float,
        contract_value: float,
        base_rate: float,
    ) -> float:
        """Calculate tiered credit based on severity.

        Tiers:
        - Minor (<5%): base_rate * 0.5
        - Moderate (5-15%): base_rate * 1.0
        - Major (15-30%): base_rate * 1.5
        - Critical (>30%): base_rate * 2.0

        Args:
            deviation_percent: Deviation from target.
            contract_value: Contract value.
            base_rate: Base rate for calculation.

        Returns:
            Calculated credit amount.
        """
        if deviation_percent < 5:
            multiplier = 0.5
        elif deviation_percent < 15:
            multiplier = 1.0
        elif deviation_percent < 30:
            multiplier = 1.5
        else:
            multiplier = 2.0

        return contract_value * (base_rate / 100) * multiplier

    def _evaluate_formula(self, formula: str, variables: dict) -> float:
        """Safely evaluate a calculation formula.

        Args:
            formula: Formula string with variable references.
            variables: Variable values.

        Returns:
            Calculated result.
        """
        # Only allow safe operations
        allowed_names = {
            **variables,
            "abs": abs,
            "min": min,
            "max": max,
            "round": round,
        }

        # Validate formula contains only allowed characters
        if not re.match(r'^[\w\s\+\-\*\/\(\)\.\,]+$', formula):
            raise ValueError(f"Invalid formula: {formula}")

        # Evaluate
        result = eval(formula, {"__builtins__": {}}, allowed_names)
        return float(result)

    async def calculate_penalty(
        self,
        event: Event,
        config: Optional[dict] = None,
    ) -> dict:
        """Calculate penalty for contract violation.

        Args:
            event: The violation event.
            config: Penalty configuration.

        Returns:
            Calculation result.
        """
        config = config or {}
        details = event.details or {}

        penalty_type = config.get("penalty_type", "percentage")
        base_amount = config.get("base_amount", 0)
        contract_value = details.get("contract_value", 0)

        if penalty_type == "fixed":
            penalty_amount = base_amount
        elif penalty_type == "percentage":
            penalty_amount = contract_value * (base_amount / 100)
        elif penalty_type == "daily":
            days_overdue = details.get("days_overdue", 0)
            penalty_amount = base_amount * days_overdue
        else:
            penalty_amount = base_amount

        return {
            "penalty_amount": round(penalty_amount, 2),
            "penalty_type": penalty_type,
            "base_amount": base_amount,
            "contract_value": contract_value,
        }

    async def get_credit_summary(
        self,
        contract_id: UUID,
    ) -> dict:
        """Get summary of credits/penalties for a contract.

        Args:
            contract_id: Contract to summarize.

        Returns:
            Summary of all credits and penalties.
        """
        from app.models.workflow import ActionExecution, ActionType, ExecutionStatus

        # Find all completed credit calculations for this contract's events
        query = (
            select(ActionExecution)
            .join(Event, ActionExecution.event_id == Event.id)
            .where(
                Event.contract_id == contract_id,
                ActionExecution.action_type == ActionType.calculate_service_credit,
                ActionExecution.status == ExecutionStatus.completed,
            )
        )

        result = await self.db.execute(query)
        executions = result.scalars().all()

        total_credits = 0
        credit_history = []

        for execution in executions:
            if execution.result and "credit_amount" in execution.result:
                amount = execution.result["credit_amount"]
                total_credits += amount
                credit_history.append({
                    "date": execution.completed_at.isoformat() if execution.completed_at else None,
                    "amount": amount,
                    "event_id": str(execution.event_id),
                })

        return {
            "contract_id": str(contract_id),
            "total_credits": round(total_credits, 2),
            "credit_count": len(credit_history),
            "history": credit_history,
        }


async def get_calculation_service(db: AsyncSession) -> CalculationService:
    """Factory function for calculation service."""
    return CalculationService(db)

"""ServiceNow Stub Connector.

Provides simulated SLA performance data for demo purposes.
Data is generated to create realistic scenarios including:
- SLAs meeting targets
- SLAs slightly below expected but above minimum
- SLAs in breach (below minimum)
- Monthly variance patterns
"""

import logging
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.connectors.base import (
    ConnectorResult,
    DataQuality,
    ITSMConnector,
    SLAActualValue,
)

logger = logging.getLogger(__name__)


# Realistic SLA configurations based on ING contract structure
# These map to the extracted SLA section references
SLA_CONFIGURATIONS = {
    # Critical Service Levels - CD (Contact Center/Desktop)
    "12.1": {
        "name": "Application Integration Services",
        "target": Decimal("0.54"),
        "minimum": Decimal("0.45"),
        "typical_performance": Decimal("0.52"),
        "volatility": Decimal("0.05"),
    },
    "12.1.1": {
        "name": "SM & EUC - Number of contacts handled within 15 mins",
        "target": Decimal("0.54"),
        "minimum": Decimal("0.45"),
        "typical_performance": Decimal("0.51"),
        "volatility": Decimal("0.04"),
    },
    "12.2.1": {
        "name": "SM & EUC - Electronic Authorisation request performance",
        "target": Decimal("0.45"),
        "minimum": Decimal("0.35"),
        "typical_performance": Decimal("0.43"),
        "volatility": Decimal("0.06"),
    },
    "12.2.2": {
        "name": "SM & EUC - Paper Authorisation request performance",
        "target": Decimal("0.75"),
        "minimum": Decimal("0.58"),
        "typical_performance": Decimal("0.72"),
        "volatility": Decimal("0.08"),
    },
    "12.3.1": {
        "name": "SD - Speed to answer voice calls < 60 sec after IVR",
        "target": Decimal("0.65"),
        "minimum": Decimal("0.59"),
        "typical_performance": Decimal("0.63"),
        "volatility": Decimal("0.05"),
    },
    "12.3.2": {
        "name": "SD - Call non-abandonment rate - NL",
        "target": Decimal("0.80"),
        "minimum": Decimal("0.77"),
        "typical_performance": Decimal("0.79"),
        "volatility": Decimal("0.03"),
    },
    "12.4.1": {
        "name": "SD - Percentage of In-Scope Incidents resolved by Service Desk",
        "target": Decimal("0.58"),
        "minimum": Decimal("0.54"),
        "typical_performance": Decimal("0.56"),
        "volatility": Decimal("0.04"),
    },

    # Desktop Services Availability
    "2.1.1": {
        "name": "DTHW - Base Workplace Service Availability",
        "target": Decimal("0.99"),
        "minimum": Decimal("0.97"),
        "typical_performance": Decimal("0.985"),
        "volatility": Decimal("0.01"),
    },
    "2.1.2": {
        "name": "Laptop Availability",
        "target": Decimal("0.99"),
        "minimum": Decimal("0.97"),
        "typical_performance": Decimal("0.988"),
        "volatility": Decimal("0.008"),
    },
    "2.2.1": {
        "name": "Network Service Availability",
        "target": Decimal("0.999"),
        "minimum": Decimal("0.995"),
        "typical_performance": Decimal("0.998"),
        "volatility": Decimal("0.002"),
    },

    # Key Measurements
    "11.1": {
        "name": "Accuracy of standard hardware catalog",
        "target": Decimal("0.98"),
        "minimum": Decimal("0.95"),
        "typical_performance": Decimal("0.97"),
        "volatility": Decimal("0.02"),
    },
    "11.2": {
        "name": "Accuracy of standard software catalog",
        "target": Decimal("0.98"),
        "minimum": Decimal("0.95"),
        "typical_performance": Decimal("0.96"),
        "volatility": Decimal("0.025"),
    },
}

# Incident metrics simulation
INCIDENT_METRICS_BASE = {
    "total_incidents": 1250,
    "p1_incidents": 3,
    "p2_incidents": 28,
    "p3_incidents": 156,
    "p4_incidents": 1063,
    "mttr_p1_hours": 2.5,
    "mttr_p2_hours": 8.0,
    "mttr_p3_hours": 24.0,
    "mttr_p4_hours": 72.0,
    "first_call_resolution_rate": 0.42,
    "reopened_incidents_rate": 0.03,
    "customer_satisfaction_score": 4.2,
}


class ServiceNowStubConnector(ITSMConnector):
    """Stub ServiceNow connector for demo purposes."""

    connector_name = "ServiceNow (Stub)"
    is_stub = True

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._seed = config.get("seed", 42) if config else 42
        random.seed(self._seed)

    async def connect(self) -> bool:
        """Simulate connection to ServiceNow."""
        logger.info("ServiceNow stub connector: Simulating connection...")
        self._connected = True
        return True

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False

    async def health_check(self) -> ConnectorResult:
        """Return healthy status for stub."""
        return ConnectorResult(
            success=True,
            data={"status": "healthy", "latency_ms": 45},
            quality=DataQuality.SIMULATED,
            source="ServiceNow Stub",
        )

    async def get_sla_actuals(
        self,
        sla_references: list[str],
        start_date: date,
        end_date: date,
    ) -> ConnectorResult:
        """Generate realistic SLA actual values.

        Args:
            sla_references: List of SLA section references.
            start_date: Start of measurement period.
            end_date: End of measurement period.

        Returns:
            ConnectorResult with simulated SLA actuals.
        """
        actuals = []

        for ref in sla_references:
            config = SLA_CONFIGURATIONS.get(ref)
            if not config:
                # Generate generic values for unknown SLAs
                config = self._generate_generic_config(ref)

            # Generate actual value with realistic variance
            actual = self._generate_actual_value(config, start_date, end_date)

            # Calculate compliance
            is_compliant = actual >= config["minimum"]
            deviation = ((actual - config["target"]) / config["target"]) * 100

            sla_actual = SLAActualValue(
                sla_reference=ref,
                sla_name=config["name"],
                actual_value=actual,
                target_value=config["target"],
                measurement_period_start=start_date,
                measurement_period_end=end_date,
                is_compliant=is_compliant,
                deviation_percentage=deviation.quantize(Decimal("0.01")),
                source_system="ServiceNow",
                source_ticket_id=f"SLA-{ref.replace('.', '')}-{start_date.strftime('%Y%m')}",
                notes=self._generate_notes(actual, config),
            )
            actuals.append(sla_actual)

        return ConnectorResult(
            success=True,
            data=actuals,
            quality=DataQuality.SIMULATED,
            source="ServiceNow Stub",
            metadata={
                "period": f"{start_date} to {end_date}",
                "sla_count": len(actuals),
            },
        )

    async def get_incident_metrics(
        self,
        start_date: date,
        end_date: date,
    ) -> ConnectorResult:
        """Generate realistic incident metrics.

        Args:
            start_date: Start date.
            end_date: End date.

        Returns:
            ConnectorResult with incident metrics.
        """
        # Calculate days in period for scaling
        days = (end_date - start_date).days + 1
        scale_factor = days / 30  # Base metrics are for 30 days

        # Add some randomness
        variance = random.uniform(0.85, 1.15)

        metrics = {
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_incidents": int(INCIDENT_METRICS_BASE["total_incidents"] * scale_factor * variance),
            "by_priority": {
                "P1": int(INCIDENT_METRICS_BASE["p1_incidents"] * scale_factor * random.uniform(0.5, 2.0)),
                "P2": int(INCIDENT_METRICS_BASE["p2_incidents"] * scale_factor * variance),
                "P3": int(INCIDENT_METRICS_BASE["p3_incidents"] * scale_factor * variance),
                "P4": int(INCIDENT_METRICS_BASE["p4_incidents"] * scale_factor * variance),
            },
            "mttr_hours": {
                "P1": round(INCIDENT_METRICS_BASE["mttr_p1_hours"] * random.uniform(0.7, 1.5), 1),
                "P2": round(INCIDENT_METRICS_BASE["mttr_p2_hours"] * random.uniform(0.8, 1.3), 1),
                "P3": round(INCIDENT_METRICS_BASE["mttr_p3_hours"] * random.uniform(0.9, 1.2), 1),
                "P4": round(INCIDENT_METRICS_BASE["mttr_p4_hours"] * random.uniform(0.9, 1.1), 1),
            },
            "first_call_resolution_rate": round(
                INCIDENT_METRICS_BASE["first_call_resolution_rate"] * random.uniform(0.95, 1.05), 3
            ),
            "reopened_incidents_rate": round(
                INCIDENT_METRICS_BASE["reopened_incidents_rate"] * random.uniform(0.8, 1.5), 3
            ),
            "customer_satisfaction_score": round(
                INCIDENT_METRICS_BASE["customer_satisfaction_score"] * random.uniform(0.95, 1.05), 2
            ),
        }

        return ConnectorResult(
            success=True,
            data=metrics,
            quality=DataQuality.SIMULATED,
            source="ServiceNow Stub",
        )

    async def get_monthly_sla_history(
        self,
        sla_references: list[str],
        months: int = 12,
    ) -> ConnectorResult:
        """Get monthly SLA history for trend analysis.

        Args:
            sla_references: List of SLA section references.
            months: Number of months of history.

        Returns:
            ConnectorResult with monthly SLA data.
        """
        history = {}
        today = date.today()

        for ref in sla_references:
            config = SLA_CONFIGURATIONS.get(ref) or self._generate_generic_config(ref)
            monthly_data = []

            for i in range(months - 1, -1, -1):
                # Calculate month boundaries
                month_end = today.replace(day=1) - timedelta(days=1)
                month_end = month_end.replace(day=1) - timedelta(days=i * 30)
                month_start = month_end.replace(day=1)
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

                # Generate value with seasonal/trend patterns
                actual = self._generate_actual_value(config, month_start, month_end, month_index=i)

                monthly_data.append({
                    "month": month_start.strftime("%Y-%m"),
                    "actual": float(actual),
                    "target": float(config["target"]),
                    "minimum": float(config["minimum"]),
                    "compliant": actual >= config["minimum"],
                    "meets_target": actual >= config["target"],
                })

            history[ref] = {
                "sla_name": config["name"],
                "monthly_values": monthly_data,
                "average": sum(m["actual"] for m in monthly_data) / len(monthly_data),
                "compliance_rate": sum(1 for m in monthly_data if m["compliant"]) / len(monthly_data),
                "target_achievement_rate": sum(1 for m in monthly_data if m["meets_target"]) / len(monthly_data),
            }

        return ConnectorResult(
            success=True,
            data=history,
            quality=DataQuality.SIMULATED,
            source="ServiceNow Stub",
            metadata={"months": months, "sla_count": len(sla_references)},
        )

    def _generate_actual_value(
        self,
        config: dict,
        start_date: date,
        end_date: date,
        month_index: int = 0,
    ) -> Decimal:
        """Generate realistic actual value with variance.

        Creates values that:
        - Usually hover near typical_performance
        - Occasionally dip below minimum (breach)
        - Sometimes exceed target (excellent performance)
        - Show seasonal patterns
        """
        typical = float(config["typical_performance"])
        volatility = float(config["volatility"])
        target = float(config["target"])
        minimum = float(config["minimum"])

        # Base value with normal distribution around typical
        base_value = random.gauss(typical, volatility)

        # Add seasonal pattern (worse in Dec-Jan, better in Q2)
        month = start_date.month
        if month in [12, 1]:
            seasonal_factor = -0.02  # Slightly worse during holidays
        elif month in [4, 5, 6]:
            seasonal_factor = 0.01  # Slightly better in Q2
        else:
            seasonal_factor = 0

        # Add trend (slight improvement over time for demo)
        trend_factor = month_index * 0.001 if month_index > 0 else 0

        # Occasional outliers (5% chance of significant deviation)
        if random.random() < 0.05:
            # Bad month - below minimum
            outlier = random.uniform(minimum - 0.1, minimum - 0.02)
            actual = min(outlier, base_value - volatility * 2)
        elif random.random() < 0.1:
            # Great month - above target
            actual = random.uniform(target, target + volatility)
        else:
            actual = base_value + seasonal_factor - trend_factor

        # Clamp to reasonable range
        actual = max(0, min(1.0, actual))

        return Decimal(str(round(actual, 4)))

    def _generate_generic_config(self, ref: str) -> dict:
        """Generate generic config for unknown SLA references."""
        return {
            "name": f"SLA {ref}",
            "target": Decimal("0.95"),
            "minimum": Decimal("0.90"),
            "typical_performance": Decimal("0.93"),
            "volatility": Decimal("0.04"),
        }

    def _generate_notes(self, actual: Decimal, config: dict) -> str:
        """Generate contextual notes based on performance."""
        target = config["target"]
        minimum = config["minimum"]

        if actual >= target:
            return "Performance meets or exceeds target."
        elif actual >= minimum:
            gap = float(target - actual) * 100
            return f"Performance below target by {gap:.1f}%. Above minimum threshold."
        else:
            gap = float(minimum - actual) * 100
            return f"BREACH: Performance {gap:.1f}% below minimum threshold. Service credit may apply."


def get_servicenow_stub() -> ServiceNowStubConnector:
    """Get ServiceNow stub connector instance."""
    return ServiceNowStubConnector()

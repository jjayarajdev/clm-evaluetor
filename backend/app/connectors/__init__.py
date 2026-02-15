"""External System Connectors.

This package provides connectors to external systems for retrieving
actual performance data to compare against contracted SLA targets.

For demo/POC purposes, stub implementations are provided that return
realistic simulated data. These can be swapped for real integrations.
"""

from app.connectors.base import ConnectorBase, ConnectorRegistry
from app.connectors.servicenow_stub import ServiceNowStubConnector
from app.connectors.milestone_stub import MilestoneStubConnector
from app.connectors.fx_stub import FXRateStubConnector

__all__ = [
    "ConnectorBase",
    "ConnectorRegistry",
    "ServiceNowStubConnector",
    "MilestoneStubConnector",
    "FXRateStubConnector",
]

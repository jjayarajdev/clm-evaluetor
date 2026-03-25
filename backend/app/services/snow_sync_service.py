"""ServiceNow SLA sync service.

Orchestrates the synchronization of SLA definitions from ServiceNow
into the platform's SLA mapping table, and manages the mapping lifecycle.
"""

import logging
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import IntegrationConfig, IntegrationSystem
from app.models.snow_sla_mapping import SnowSLAMapping
from app.integrations.servicenow import ServiceNowClient

logger = logging.getLogger(__name__)


class SnowSyncService:
    """Orchestrates SLA sync from ServiceNow to the platform."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_tenant_config(self, tenant_id: UUID) -> Optional[IntegrationConfig]:
        """Get active ServiceNow config for a tenant.

        Args:
            tenant_id: The tenant UUID.

        Returns:
            Active IntegrationConfig or None.
        """
        query = select(IntegrationConfig).where(
            IntegrationConfig.tenant_id == tenant_id,
            IntegrationConfig.system == IntegrationSystem.servicenow,
            IntegrationConfig.is_active == True,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def test_connection(self, config: IntegrationConfig) -> dict:
        """Test ServiceNow connection and update health status.

        Args:
            config: The IntegrationConfig to test.

        Returns:
            Dict with healthy (bool) and message (str).
        """
        async with ServiceNowClient(config, self.db) as client:
            healthy = await client.health_check()
            config.health_status = "healthy" if healthy else "unhealthy"
            config.last_health_check = datetime.utcnow()
            config.last_health_message = (
                "Connection successful" if healthy else "Connection failed"
            )
            await self.db.commit()
            return {
                "healthy": healthy,
                "message": config.last_health_message,
            }

    async def sync_sla_definitions(self, config: IntegrationConfig) -> dict:
        """Pull SLA definitions from ServiceNow and create/update mappings.

        Args:
            config: The IntegrationConfig for the ServiceNow instance.

        Returns:
            Stats dict with fetched, created, updated, and errors counts.
        """
        stats = {"fetched": 0, "created": 0, "updated": 0, "errors": 0}

        async with ServiceNowClient(config, self.db) as client:
            response = await client.get_sla_definitions()
            results = response.get("result", [])
            if not isinstance(results, list):
                results = [results] if results else []

            stats["fetched"] = len(results)

            for sla_def in results:
                try:
                    snow_sys_id = sla_def.get("sys_id")
                    if not snow_sys_id:
                        continue

                    # Check if mapping already exists
                    existing = await self.db.execute(
                        select(SnowSLAMapping).where(
                            SnowSLAMapping.integration_config_id == config.id,
                            SnowSLAMapping.snow_sys_id == snow_sys_id,
                        )
                    )
                    mapping = existing.scalar_one_or_none()

                    if mapping:
                        mapping.snow_sla_name = sla_def.get("name", "")
                        mapping.snow_metric_type = sla_def.get("collection", "")
                        mapping.snow_target = sla_def.get(
                            "target_percentage", sla_def.get("duration", "")
                        )
                        mapping.last_synced_at = datetime.utcnow()
                        mapping.sync_metadata = sla_def
                        stats["updated"] += 1
                    else:
                        new_mapping = SnowSLAMapping(
                            id=uuid4(),
                            tenant_id=config.tenant_id,
                            integration_config_id=config.id,
                            snow_sys_id=snow_sys_id,
                            snow_sla_name=sla_def.get("name", ""),
                            snow_metric_type=sla_def.get("collection", ""),
                            snow_target=sla_def.get(
                                "target_percentage", sla_def.get("duration", "")
                            ),
                            mapping_status="pending",
                            last_synced_at=datetime.utcnow(),
                            sync_metadata=sla_def,
                        )
                        self.db.add(new_mapping)
                        stats["created"] += 1
                except Exception as e:
                    logger.error(f"Error syncing SLA {sla_def.get('sys_id')}: {e}")
                    stats["errors"] += 1

            await self.db.commit()

        return stats

    async def get_mappings(
        self, tenant_id: UUID, config_id: Optional[UUID] = None
    ) -> list[SnowSLAMapping]:
        """Get all SLA mappings for a tenant.

        Args:
            tenant_id: The tenant UUID.
            config_id: Optional filter by integration config ID.

        Returns:
            List of SnowSLAMapping records.
        """
        query = select(SnowSLAMapping).where(
            SnowSLAMapping.tenant_id == tenant_id
        )
        if config_id:
            query = query.where(
                SnowSLAMapping.integration_config_id == config_id
            )
        query = query.order_by(SnowSLAMapping.snow_sla_name)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_mapping(
        self,
        mapping_id: UUID,
        tenant_id: UUID,
        platform_sla_id: Optional[UUID],
        status: str,
    ) -> SnowSLAMapping:
        """Link a SNOW SLA to a platform SLA or set mapping status.

        Args:
            mapping_id: The mapping record UUID.
            tenant_id: The tenant UUID (for tenant isolation).
            platform_sla_id: The platform ContractSLA UUID to link (or None).
            status: New mapping status (mapped, ignored, pending, error).

        Returns:
            Updated SnowSLAMapping.

        Raises:
            ValueError: If mapping not found.
        """
        result = await self.db.execute(
            select(SnowSLAMapping).where(
                SnowSLAMapping.id == mapping_id,
                SnowSLAMapping.tenant_id == tenant_id,
            )
        )
        mapping = result.scalar_one_or_none()
        if not mapping:
            raise ValueError("Mapping not found")

        mapping.platform_sla_id = platform_sla_id
        mapping.mapping_status = status
        await self.db.commit()
        return mapping

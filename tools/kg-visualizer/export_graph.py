"""Export knowledge graph data from the database as JSON for the visualizer."""

import asyncio
import json
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from app.database import async_session_maker
from sqlalchemy import text


async def export():
    async with async_session_maker() as db:
        # Get all entities
        result = await db.execute(text("""
            SELECT
                e.id::text,
                e.contract_id::text,
                e.entity_type,
                e.name,
                e.properties,
                e.confidence,
                c.filename
            FROM kg_entities e
            JOIN contracts c ON c.id = e.contract_id
            ORDER BY c.filename, e.entity_type, e.name
        """))
        entities = []
        for row in result.fetchall():
            entities.append({
                "id": row[0],
                "contract_id": row[1],
                "entity_type": row[2],
                "name": row[3],
                "properties": row[4] or {},
                "confidence": float(row[5]) if row[5] else 0.8,
                "contract": row[6],
            })

        # Get all relationships
        result = await db.execute(text("""
            SELECT
                r.id::text,
                r.contract_id::text,
                r.source_entity_id::text,
                r.target_entity_id::text,
                r.relationship_type,
                r.properties,
                r.confidence,
                c.filename
            FROM kg_relationships r
            JOIN contracts c ON c.id = r.contract_id
            ORDER BY c.filename
        """))
        relationships = []
        for row in result.fetchall():
            relationships.append({
                "id": row[0],
                "contract_id": row[1],
                "source": row[2],
                "target": row[3],
                "relationship_type": row[4],
                "properties": row[5] or {},
                "confidence": float(row[6]) if row[6] else 0.8,
                "contract": row[7],
            })

        # Get contracts list
        contract_set = {}
        for e in entities:
            contract_set[e["contract_id"]] = e["contract"]
        contracts = [{"id": k, "filename": v} for k, v in contract_set.items()]

        data = {
            "contracts": contracts,
            "entities": entities,
            "relationships": relationships,
            "stats": {
                "total_entities": len(entities),
                "total_relationships": len(relationships),
                "total_contracts": len(contracts),
            }
        }

        output_path = os.path.join(os.path.dirname(__file__), "graph_data.json")
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        print(f"Exported {len(entities)} entities, {len(relationships)} relationships from {len(contracts)} contracts")
        print(f"Written to: {output_path}")


if __name__ == "__main__":
    asyncio.run(export())

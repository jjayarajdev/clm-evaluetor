"""Contract schema definitions for structured extraction.

This module provides a schema-driven approach to contract data extraction:

1. **Schema Definitions** - JSON schemas define what data to extract for each contract type
2. **Schema Registry** - Manages loading and retrieving schemas
3. **Schema Extractor** - Uses schemas to generate prompts and extract data

Usage:
    from app.schemas import get_schema_registry, extract_with_schema

    # List available schemas
    registry = get_schema_registry()
    schemas = registry.list_schemas()

    # Extract data using a schema
    result = await extract_with_schema(
        contract_text=text,
        contract_type="MSA",
    )

Adding New Schemas:
    1. Create a JSON file in app/schemas/definitions/
    2. Follow the schema structure (see msa.json for example)
    3. The schema will be auto-loaded on startup
"""

from app.schemas.models import (
    ContractSchema,
    SchemaSection,
    SchemaField,
    FieldType,
    ExtractionResult,
)
from app.schemas.registry import SchemaRegistry, get_schema_registry
from app.schemas.extractor import (
    SchemaExtractor,
    get_schema_extractor,
    extract_with_schema,
)

__all__ = [
    # Models
    "ContractSchema",
    "SchemaSection",
    "SchemaField",
    "FieldType",
    "ExtractionResult",
    # Registry
    "SchemaRegistry",
    "get_schema_registry",
    # Extractor
    "SchemaExtractor",
    "get_schema_extractor",
    "extract_with_schema",
]

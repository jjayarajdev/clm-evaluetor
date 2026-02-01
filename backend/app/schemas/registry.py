"""Schema registry for managing contract extraction schemas."""

import json
import logging
from pathlib import Path
from typing import Any

from app.schemas.models import (
    ContractSchema,
    SchemaSection,
    SchemaField,
    FieldType,
)

logger = logging.getLogger(__name__)

# Default schema directory
SCHEMA_DIR = Path(__file__).parent / "definitions"


class SchemaRegistry:
    """Registry for contract extraction schemas.

    Manages loading, caching, and retrieval of contract schemas.
    Schemas can be loaded from:
    - JSON files in the definitions directory
    - Database (future)
    - Programmatically registered
    """

    def __init__(self, schema_dir: Path | None = None):
        """Initialize the registry.

        Args:
            schema_dir: Directory containing schema JSON files.
        """
        self.schema_dir = schema_dir or SCHEMA_DIR
        self._schemas: dict[str, ContractSchema] = {}
        self._loaded = False

    def load_schemas(self) -> None:
        """Load all schemas from the schema directory."""
        if self._loaded:
            return

        if not self.schema_dir.exists():
            logger.warning(f"Schema directory not found: {self.schema_dir}")
            self._loaded = True
            return

        for schema_file in self.schema_dir.glob("*.json"):
            try:
                schema = self._load_schema_file(schema_file)
                self._schemas[schema.schema_id] = schema
                logger.info(f"Loaded schema: {schema.schema_id} ({schema.contract_type})")
            except Exception as e:
                logger.error(f"Failed to load schema {schema_file}: {e}")

        self._loaded = True
        logger.info(f"Loaded {len(self._schemas)} schemas")

    def _load_schema_file(self, path: Path) -> ContractSchema:
        """Load a schema from a JSON file."""
        with open(path) as f:
            data = json.load(f)

        return self._parse_schema_dict(data)

    def _parse_schema_dict(self, data: dict[str, Any]) -> ContractSchema:
        """Parse a schema dictionary into a ContractSchema object."""
        sections = {}

        for section_name, section_data in data.get("sections", {}).items():
            fields = {}
            for field_name, field_data in section_data.get("fields", {}).items():
                fields[field_name] = self._parse_field(field_data)

            sections[section_name] = SchemaSection(
                name=section_name,
                description=section_data.get("description", ""),
                fields=fields,
                priority=section_data.get("priority", 1),
                max_context_chars=section_data.get("max_context_chars", 15000),
            )

        return ContractSchema(
            schema_id=data["schema_id"],
            contract_type=data["contract_type"],
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            sections=sections,
            extraction_model=data.get("extraction_model", "gpt-4o"),
            extraction_temperature=data.get("extraction_temperature", 0.0),
            max_tokens=data.get("max_tokens", 4000),
            required_sections=data.get("required_sections", []),
        )

    def _parse_field(self, data: dict[str, Any]) -> SchemaField:
        """Parse a field definition."""
        field_type = FieldType(data.get("type", "string"))

        properties = None
        if field_type == FieldType.OBJECT and "properties" in data:
            properties = {
                k: self._parse_field(v)
                for k, v in data["properties"].items()
            }

        return SchemaField(
            name=data.get("name", ""),
            type=field_type,
            description=data.get("description", ""),
            required=data.get("required", False),
            default=data.get("default"),
            enum_values=data.get("enum_values"),
            items_type=FieldType(data["items_type"]) if data.get("items_type") else None,
            items_schema=data.get("items_schema"),
            properties=properties,
            extraction_hints=data.get("extraction_hints", []),
            example_values=data.get("example_values", []),
            section_hints=data.get("section_hints", []),
        )

    def get_schema(self, schema_id: str) -> ContractSchema | None:
        """Get a schema by ID."""
        self.load_schemas()
        return self._schemas.get(schema_id)

    def get_schema_for_contract_type(self, contract_type: str) -> ContractSchema | None:
        """Get the schema for a contract type."""
        self.load_schemas()
        contract_type_upper = contract_type.upper()

        for schema in self._schemas.values():
            if schema.contract_type.upper() == contract_type_upper:
                return schema

        return None

    def list_schemas(self) -> list[dict[str, str]]:
        """List all available schemas."""
        self.load_schemas()
        return [
            {
                "schema_id": s.schema_id,
                "contract_type": s.contract_type,
                "version": s.version,
                "description": s.description,
            }
            for s in self._schemas.values()
        ]

    def register_schema(self, schema: ContractSchema) -> None:
        """Register a schema programmatically."""
        self._schemas[schema.schema_id] = schema
        logger.info(f"Registered schema: {schema.schema_id}")

    def register_from_json(self, json_data: dict[str, Any]) -> ContractSchema:
        """Register a schema from JSON data."""
        schema = self._parse_schema_dict(json_data)
        self.register_schema(schema)
        return schema

    def save_schema(self, schema: ContractSchema) -> Path:
        """Save a schema to a JSON file."""
        self.schema_dir.mkdir(parents=True, exist_ok=True)
        path = self.schema_dir / f"{schema.schema_id}.json"

        with open(path, "w") as f:
            json.dump(self._schema_to_dict(schema), f, indent=2)

        logger.info(f"Saved schema to: {path}")
        return path

    def _schema_to_dict(self, schema: ContractSchema) -> dict[str, Any]:
        """Convert a schema to a dictionary for serialization."""
        sections = {}
        for section_name, section in schema.sections.items():
            sections[section_name] = {
                "description": section.description,
                "priority": section.priority,
                "max_context_chars": section.max_context_chars,
                "fields": {
                    k: self._field_to_dict(v)
                    for k, v in section.fields.items()
                },
            }

        return {
            "schema_id": schema.schema_id,
            "contract_type": schema.contract_type,
            "version": schema.version,
            "description": schema.description,
            "sections": sections,
            "extraction_model": schema.extraction_model,
            "extraction_temperature": schema.extraction_temperature,
            "max_tokens": schema.max_tokens,
            "required_sections": schema.required_sections,
        }

    def _field_to_dict(self, field: SchemaField) -> dict[str, Any]:
        """Convert a field to a dictionary."""
        result = {
            "type": field.type.value,
            "description": field.description,
            "required": field.required,
        }

        if field.default is not None:
            result["default"] = field.default
        if field.enum_values:
            result["enum_values"] = field.enum_values
        if field.items_type:
            result["items_type"] = field.items_type.value
        if field.items_schema:
            result["items_schema"] = field.items_schema
        if field.properties:
            result["properties"] = {
                k: self._field_to_dict(v)
                for k, v in field.properties.items()
            }
        if field.extraction_hints:
            result["extraction_hints"] = field.extraction_hints
        if field.example_values:
            result["example_values"] = field.example_values
        if field.section_hints:
            result["section_hints"] = field.section_hints

        return result


# Singleton registry instance
_registry: SchemaRegistry | None = None


def get_schema_registry() -> SchemaRegistry:
    """Get the global schema registry instance."""
    global _registry
    if _registry is None:
        _registry = SchemaRegistry()
    return _registry

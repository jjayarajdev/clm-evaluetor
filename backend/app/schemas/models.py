"""Pydantic models for contract schema definitions."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FieldType(str, Enum):
    """Supported field types for schema definitions."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    ARRAY = "array"
    OBJECT = "object"
    ENUM = "enum"


class SchemaField(BaseModel):
    """Definition of a single field in a contract schema."""

    name: str = Field(..., description="Field name/key")
    type: FieldType = Field(..., description="Data type")
    description: str = Field("", description="Human-readable description for LLM")
    required: bool = Field(False, description="Whether field is required")
    default: Any = Field(None, description="Default value if not found")

    # For enum types
    enum_values: list[str] | None = Field(None, description="Allowed values for enum type")

    # For array types
    items_type: FieldType | None = Field(None, description="Type of array items")
    items_schema: str | None = Field(None, description="Schema reference for object items")

    # For object types
    properties: dict[str, "SchemaField"] | None = Field(None, description="Nested object properties")

    # Extraction hints for LLM
    extraction_hints: list[str] = Field(
        default_factory=list,
        description="Hints to help LLM locate this field"
    )
    example_values: list[str] = Field(
        default_factory=list,
        description="Example values for LLM guidance"
    )
    section_hints: list[str] = Field(
        default_factory=list,
        description="Likely sections where this field appears"
    )


class SchemaSection(BaseModel):
    """A logical section/group of fields in the schema."""

    name: str = Field(..., description="Section name (e.g., 'contract_metadata')")
    description: str = Field("", description="What this section captures")
    fields: dict[str, SchemaField] = Field(default_factory=dict)

    # Extraction configuration
    priority: int = Field(1, description="Extraction priority (higher = extract first)")
    max_context_chars: int = Field(
        15000,
        description="Max chars to send to LLM for this section"
    )


class ContractSchema(BaseModel):
    """Complete schema definition for a contract type."""

    schema_id: str = Field(..., description="Unique schema identifier")
    contract_type: str = Field(..., description="Contract type (MSA, SOW, NDA, etc.)")
    version: str = Field("1.0.0", description="Schema version")
    description: str = Field("", description="Description of this contract type")

    # Schema sections
    sections: dict[str, SchemaSection] = Field(default_factory=dict)

    # Extraction configuration
    extraction_model: str = Field("gpt-4o", description="Preferred model for extraction")
    extraction_temperature: float = Field(0.0, description="Temperature for extraction")
    max_tokens: int = Field(4000, description="Max tokens for response")

    # Validation rules
    required_sections: list[str] = Field(
        default_factory=list,
        description="Sections that must be present"
    )

    def to_prompt_instructions(self) -> str:
        """Generate extraction instructions from this schema."""
        lines = [
            f"Extract structured data from this {self.contract_type} contract.",
            f"Schema: {self.description}",
            "",
            "You MUST return valid JSON matching this exact structure:",
            ""
        ]

        for section_name, section in self.sections.items():
            lines.append(f"## {section_name}")
            lines.append(f"{section.description}")
            lines.append("")

            for field_name, field in section.fields.items():
                field_desc = f"- **{field_name}** ({field.type.value})"
                if field.required:
                    field_desc += " [REQUIRED]"
                field_desc += f": {field.description}"
                lines.append(field_desc)

                if field.extraction_hints:
                    lines.append(f"  Look for: {', '.join(field.extraction_hints)}")
                if field.example_values:
                    lines.append(f"  Examples: {', '.join(field.example_values)}")
                if field.enum_values:
                    lines.append(f"  Must be one of: {', '.join(field.enum_values)}")

            lines.append("")

        lines.extend([
            "IMPORTANT GUIDELINES:",
            "1. Extract ONLY information explicitly stated in the contract",
            "2. Use null for fields that cannot be determined",
            "3. Include section_reference where the information was found",
            "4. Maintain exact quotes for source_text fields",
            "5. Use ISO date format (YYYY-MM-DD) for all dates",
            "",
            "Respond with ONLY the JSON object, no explanation.",
        ])

        return "\n".join(lines)

    def get_json_template(self) -> dict[str, Any]:
        """Generate a JSON template from this schema."""
        template = {}

        for section_name, section in self.sections.items():
            template[section_name] = self._build_section_template(section)

        return template

    def _build_section_template(self, section: SchemaSection) -> dict[str, Any]:
        """Build template for a section."""
        result = {}

        for field_name, field in section.fields.items():
            result[field_name] = self._get_field_template(field)

        return result

    def _get_field_template(self, field: SchemaField) -> Any:
        """Get template value for a field."""
        if field.default is not None:
            return field.default

        match field.type:
            case FieldType.STRING:
                return ""
            case FieldType.INTEGER:
                return None
            case FieldType.NUMBER:
                return None
            case FieldType.BOOLEAN:
                return False
            case FieldType.DATE | FieldType.DATETIME:
                return None
            case FieldType.ARRAY:
                return []
            case FieldType.OBJECT:
                if field.properties:
                    return {
                        k: self._get_field_template(v)
                        for k, v in field.properties.items()
                    }
                return {}
            case FieldType.ENUM:
                return field.enum_values[0] if field.enum_values else None
            case _:
                return None


class ExtractionResult(BaseModel):
    """Result of schema-driven extraction."""

    schema_id: str
    contract_id: str
    extracted_data: dict[str, Any]

    # Quality metrics
    overall_confidence: float = Field(0.0, ge=0.0, le=1.0)
    section_confidences: dict[str, float] = Field(default_factory=dict)
    missing_required_fields: list[str] = Field(default_factory=list)
    extraction_warnings: list[str] = Field(default_factory=list)

    # Metadata
    model_used: str = ""
    tokens_used: int = 0
    extraction_time_ms: int = 0

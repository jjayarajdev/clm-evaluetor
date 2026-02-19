"""Custom field extraction service.

Extracts tenant-defined custom fields from contract text using AI.
Integrates with the existing metadata extraction pipeline.
"""

import json
import logging
from typing import Any

from app.agents.base import extract_json_from_response
from app.models.tenant import Tenant
from app.schemas.custom_fields import FieldType
from app.services.custom_field_validator import CustomFieldValidator
from app.services.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)


class CustomFieldExtractor:
    """Extracts custom fields from contract text using AI."""

    def __init__(self, tenant: Tenant, entity_type: str = "contract"):
        """Initialize extractor with tenant and entity type.

        Args:
            tenant: The tenant whose field definitions to use.
            entity_type: The entity type (contract, obligation, etc.).
        """
        self.tenant = tenant
        self.entity_type = entity_type
        self.field_definitions = self._load_field_definitions()
        self.validator = CustomFieldValidator(tenant, entity_type)

    def _load_field_definitions(self) -> list[dict]:
        """Load active field definitions from tenant."""
        definitions = self.tenant.custom_field_definitions or {}
        fields = definitions.get(self.entity_type, [])
        return [f for f in fields if not f.get("is_archived", False)]

    def has_custom_fields(self) -> bool:
        """Check if tenant has custom fields defined."""
        return len(self.field_definitions) > 0

    def build_extraction_prompt(self, include_instructions: bool = True) -> str:
        """Build the extraction prompt section for custom fields.

        Args:
            include_instructions: Whether to include extraction instructions.

        Returns:
            Prompt section for custom field extraction.
        """
        if not self.field_definitions:
            return ""

        lines = []

        if include_instructions:
            lines.append("CUSTOM FIELDS (tenant-specific, extract if present in the document):")
            lines.append("")

        for field in sorted(self.field_definitions, key=lambda f: f.get("display_order", 0)):
            field_desc = self._build_field_description(field)
            lines.append(field_desc)

        if include_instructions:
            lines.append("")
            lines.append("For custom fields you cannot find in the document, use null.")
            lines.append("For dropdown fields, match to the closest valid option or use null.")

        return "\n".join(lines)

    def _build_field_description(self, field: dict) -> str:
        """Build description for a single field to include in prompt."""
        name = field["name"]
        label = field.get("label", name)
        field_type = field.get("field_type", "text")
        help_text = field.get("help_text", "")

        # Base description
        desc = f"- {name}: {help_text or label}"

        # Add type-specific hints
        if field_type == FieldType.DROPDOWN.value:
            options = field.get("options", [])
            if options:
                desc += f" (must be one of: {', '.join(options)})"
        elif field_type == FieldType.NUMBER.value:
            desc += " (numeric value)"
        elif field_type == FieldType.DATE.value:
            desc += " (date in YYYY-MM-DD format)"
        elif field_type == FieldType.CHECKBOX.value:
            desc += " (true or false)"
        elif field_type == FieldType.CURRENCY.value:
            desc += " (currency amount)"
        elif field_type == FieldType.EMAIL.value:
            desc += " (email address)"
        elif field_type == FieldType.URL.value:
            desc += " (URL)"

        # Add extraction hints if provided
        extraction_hints = field.get("extraction_hints")
        if extraction_hints:
            desc += f"\n  [Look for: {extraction_hints}]"

        # Add examples if provided
        examples = field.get("extraction_examples")
        if examples:
            desc += f"\n  [Examples: {', '.join(examples[:3])}]"

        return desc

    def get_json_schema(self) -> dict:
        """Get JSON schema for custom fields output."""
        properties = {}

        for field in self.field_definitions:
            name = field["name"]
            field_type = field.get("field_type", "text")

            if field_type in (FieldType.NUMBER.value, FieldType.CURRENCY.value):
                properties[name] = {"type": ["number", "null"]}
            elif field_type == FieldType.CHECKBOX.value:
                properties[name] = {"type": ["boolean", "null"]}
            elif field_type == FieldType.MULTI_SELECT.value:
                properties[name] = {
                    "type": ["array", "null"],
                    "items": {"type": "string"},
                }
            else:
                properties[name] = {"type": ["string", "null"]}

        return {
            "type": "object",
            "properties": properties,
        }

    async def extract(
        self,
        contract_text: str,
        contract_id: str | None = None,
    ) -> dict[str, Any]:
        """Extract custom fields from contract text.

        Args:
            contract_text: The contract text to extract from.
            contract_id: Optional contract ID for logging.

        Returns:
            Dictionary of field_name -> extracted_value pairs.
        """
        if not self.field_definitions:
            return {}

        # Build extraction prompt
        custom_fields_prompt = self.build_extraction_prompt()

        prompt = f"""You are a contract data extraction specialist. Extract the following custom fields from the contract text.

{custom_fields_prompt}

CONTRACT TEXT:
{contract_text[:15000]}

Respond ONLY with valid JSON containing the extracted field values.
Example format:
```json
{{
  "field_name_1": "extracted value",
  "field_name_2": 12345,
  "field_name_3": null
}}
```

If a field cannot be found, use null.
"""

        try:
            orchestrator = get_orchestrator()
            response = await orchestrator.process_direct(
                prompt=prompt,
                agent_name="custom_field_extraction",
                model="gpt-4o-mini",  # Use faster model for extraction
                temperature=0.0,
                max_tokens=1000,
            )

            # Parse JSON response
            extracted = extract_json_from_response(response)

            if not isinstance(extracted, dict):
                logger.warning(
                    "Custom field extraction returned non-dict",
                    extra={"contract_id": contract_id, "response": str(extracted)[:200]},
                )
                return {}

            # Validate and normalize extracted values
            normalized = self.validator.normalize_values(extracted)

            logger.info(
                "Custom fields extracted",
                extra={
                    "contract_id": contract_id,
                    "fields_extracted": len(normalized),
                    "field_names": list(normalized.keys()),
                },
            )

            return normalized

        except Exception as e:
            logger.error(
                "Custom field extraction failed",
                extra={"contract_id": contract_id, "error": str(e)},
                exc_info=True,
            )
            return {}

    async def extract_with_standard(
        self,
        contract_text: str,
        contract_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Extract both standard metadata and custom fields in one call.

        This is more efficient than two separate extractions.

        Args:
            contract_text: The contract text to extract from.
            contract_id: Optional contract ID for logging.

        Returns:
            Tuple of (standard_metadata, custom_fields) dictionaries.
        """
        if not self.field_definitions:
            # No custom fields, let standard extraction handle it
            return {}, {}

        custom_fields_prompt = self.build_extraction_prompt()

        prompt = f"""You are a contract data extraction specialist. Extract structured information from the contract text.

STANDARD FIELDS (always extract):
- contract_type: Type of contract (NDA, MSA, SOW, AMENDMENT, VENDOR, EMPLOYMENT, OTHER)
- counterparty: The other party's legal entity name (not addresses or placeholders)
- effective_date: When contract takes effect (YYYY-MM-DD)
- expiration_date: When contract expires (YYYY-MM-DD)
- contract_value: Monetary value (number only)
- currency: Currency code (USD, EUR, etc.)
- jurisdiction: Governing law jurisdiction

{custom_fields_prompt}

CONTRACT TEXT:
{contract_text[:15000]}

Respond ONLY with valid JSON in this format:
```json
{{
  "standard": {{
    "contract_type": "MSA",
    "counterparty": "Acme Corp",
    "effective_date": "2024-01-01",
    "expiration_date": "2025-01-01",
    "contract_value": 50000,
    "currency": "USD",
    "jurisdiction": "State of Delaware"
  }},
  "custom": {{
    "custom_field_1": "value",
    "custom_field_2": 123
  }}
}}
```

Use null for fields that cannot be found.
"""

        try:
            orchestrator = get_orchestrator()
            response = await orchestrator.process_direct(
                prompt=prompt,
                agent_name="combined_extraction",
                model="gpt-4o",
                temperature=0.0,
                max_tokens=2000,
            )

            extracted = extract_json_from_response(response)

            if not isinstance(extracted, dict):
                logger.warning(
                    "Combined extraction returned non-dict",
                    extra={"contract_id": contract_id},
                )
                return {}, {}

            standard = extracted.get("standard", {})
            custom = extracted.get("custom", {})

            # Normalize custom fields
            if custom:
                custom = self.validator.normalize_values(custom)

            logger.info(
                "Combined extraction completed",
                extra={
                    "contract_id": contract_id,
                    "standard_fields": len(standard),
                    "custom_fields": len(custom),
                },
            )

            return standard, custom

        except Exception as e:
            logger.error(
                "Combined extraction failed",
                extra={"contract_id": contract_id, "error": str(e)},
                exc_info=True,
            )
            return {}, {}


async def extract_custom_fields(
    tenant: Tenant,
    contract_text: str,
    contract_id: str | None = None,
    entity_type: str = "contract",
) -> dict[str, Any]:
    """Convenience function to extract custom fields.

    Args:
        tenant: The tenant whose field definitions to use.
        contract_text: The contract text to extract from.
        contract_id: Optional contract ID for logging.
        entity_type: The entity type (default: contract).

    Returns:
        Dictionary of extracted custom fields.
    """
    extractor = CustomFieldExtractor(tenant, entity_type)

    if not extractor.has_custom_fields():
        return {}

    return await extractor.extract(contract_text, contract_id)

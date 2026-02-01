"""Schema-driven contract extraction service."""

import json
import logging
import time
from typing import Any

from app.agents.base import extract_json_from_response
from app.config import settings
from app.schemas.models import ContractSchema, ExtractionResult
from app.schemas.registry import get_schema_registry
from app.services.orchestrator import get_orchestrator, AgentRequest

logger = logging.getLogger(__name__)


class SchemaExtractor:
    """Extracts structured data from contracts using schema definitions.

    This extractor:
    1. Takes a contract text and schema
    2. Generates extraction prompts from the schema
    3. Calls the LLM to extract structured data
    4. Validates the result against the schema
    5. Returns typed extraction results
    """

    def __init__(self):
        """Initialize the extractor."""
        self.registry = get_schema_registry()
        self.orchestrator = get_orchestrator()

    async def extract(
        self,
        contract_text: str,
        schema_id: str | None = None,
        contract_type: str | None = None,
        contract_id: str | None = None,
        user_id: str = "system",
    ) -> ExtractionResult:
        """Extract structured data from contract text using a schema.

        Args:
            contract_text: The full contract text.
            schema_id: Specific schema ID to use.
            contract_type: Contract type to auto-select schema.
            contract_id: Contract ID for tracking.
            user_id: User ID for tracking.

        Returns:
            ExtractionResult with extracted data and quality metrics.
        """
        start_time = time.time()

        # Get the schema
        schema = self._get_schema(schema_id, contract_type)
        if not schema:
            raise ValueError(
                f"No schema found for schema_id={schema_id}, contract_type={contract_type}"
            )

        # Build extraction prompt
        system_prompt = self._build_system_prompt(schema)
        user_prompt = self._build_user_prompt(contract_text, schema)

        # Register a temporary agent for this extraction
        agent_name = f"schema_extractor_{schema.schema_id}"
        self._ensure_agent_registered(agent_name, system_prompt, schema)

        # Make the extraction request
        try:
            response = await self.orchestrator.route_request(
                AgentRequest(
                    query=user_prompt,
                    user_id=user_id,
                    session_id=f"extract_{contract_id or 'unknown'}",
                    contract_id=contract_id,
                    context={
                        "task": "schema_extraction",
                        "schema_id": schema.schema_id,
                        "contract_type": schema.contract_type,
                    },
                )
            )

            # Parse the JSON response
            extracted_data = extract_json_from_response(response.response)
            if not extracted_data:
                logger.warning(f"Failed to parse extraction response: {response.response[:500]}")
                extracted_data = {}

            # Validate and build result
            result = self._build_result(
                schema=schema,
                contract_id=contract_id or "unknown",
                extracted_data=extracted_data,
                start_time=start_time,
            )

            return result

        except Exception as e:
            logger.exception(f"Extraction failed: {e}")
            return ExtractionResult(
                schema_id=schema.schema_id,
                contract_id=contract_id or "unknown",
                extracted_data={},
                overall_confidence=0.0,
                extraction_warnings=[f"Extraction failed: {str(e)}"],
            )

    async def extract_section(
        self,
        contract_text: str,
        schema: ContractSchema,
        section_name: str,
        contract_id: str | None = None,
        user_id: str = "system",
    ) -> dict[str, Any]:
        """Extract a single section from a contract.

        Useful for:
        - Large contracts that need section-by-section extraction
        - Re-extracting specific sections with updated prompts
        - Testing schema definitions

        Args:
            contract_text: Contract text.
            schema: The schema to use.
            section_name: Which section to extract.
            contract_id: Contract ID for tracking.
            user_id: User ID for tracking.

        Returns:
            Extracted section data as dictionary.
        """
        section = schema.sections.get(section_name)
        if not section:
            raise ValueError(f"Section '{section_name}' not found in schema")

        # Build section-specific prompt
        system_prompt = self._build_section_prompt(schema, section_name)

        # Limit text based on section config
        text_limit = section.max_context_chars
        limited_text = contract_text[:text_limit]

        user_prompt = f"""Extract the '{section_name}' section from this contract:

---
{limited_text}
---

Return ONLY the JSON for this section."""

        agent_name = f"section_extractor_{schema.schema_id}_{section_name}"
        self._ensure_agent_registered(agent_name, system_prompt, schema)

        response = await self.orchestrator.route_request(
            AgentRequest(
                query=user_prompt,
                user_id=user_id,
                session_id=f"extract_section_{contract_id or 'unknown'}",
                contract_id=contract_id,
                context={
                    "task": "section_extraction",
                    "schema_id": schema.schema_id,
                    "section": section_name,
                },
            )
        )

        return extract_json_from_response(response.response) or {}

    def _get_schema(
        self,
        schema_id: str | None,
        contract_type: str | None,
    ) -> ContractSchema | None:
        """Get the appropriate schema."""
        if schema_id:
            return self.registry.get_schema(schema_id)
        if contract_type:
            return self.registry.get_schema_for_contract_type(contract_type)
        return None

    def _build_system_prompt(self, schema: ContractSchema) -> str:
        """Build the system prompt for extraction."""
        template = schema.get_json_template()
        template_json = json.dumps(template, indent=2)

        return f"""You are a contract data extraction specialist. Your task is to extract
structured data from {schema.contract_type} contracts according to a precise schema.

{schema.to_prompt_instructions()}

EXPECTED OUTPUT STRUCTURE:
```json
{template_json}
```

CRITICAL RULES:
1. Return ONLY valid JSON - no markdown, no explanations
2. Use null for any field you cannot determine from the text
3. Preserve exact quotes in source_text and description fields
4. Use ISO 8601 date format (YYYY-MM-DD)
5. For arrays, include all relevant items found
6. Include section_reference for traceability where applicable"""

    def _build_user_prompt(self, contract_text: str, schema: ContractSchema) -> str:
        """Build the user prompt with contract text."""
        # Sort sections by priority
        sorted_sections = sorted(
            schema.sections.items(),
            key=lambda x: x[1].priority,
            reverse=True
        )

        # Determine text limits
        total_limit = sum(s.max_context_chars for _, s in sorted_sections)
        text_limit = min(len(contract_text), total_limit, 50000)

        return f"""Extract all structured data from this {schema.contract_type} contract:

---CONTRACT START---
{contract_text[:text_limit]}
---CONTRACT END---

Extract data for ALL sections in the schema. Return the complete JSON structure."""

    def _build_section_prompt(self, schema: ContractSchema, section_name: str) -> str:
        """Build prompt for extracting a single section."""
        section = schema.sections[section_name]

        lines = [
            f"You are extracting the '{section_name}' section from a {schema.contract_type} contract.",
            "",
            f"Section: {section.description}",
            "",
            "Fields to extract:",
        ]

        for field_name, field in section.fields.items():
            lines.append(f"- {field_name} ({field.type.value}): {field.description}")
            if field.extraction_hints:
                lines.append(f"  Hints: {', '.join(field.extraction_hints)}")

        lines.extend([
            "",
            "Return ONLY valid JSON matching this section's structure.",
            "Use null for fields that cannot be determined.",
        ])

        return "\n".join(lines)

    def _ensure_agent_registered(
        self,
        agent_name: str,
        system_prompt: str,
        schema: ContractSchema,
    ) -> None:
        """Ensure the extraction agent is registered."""
        if not self.orchestrator.get_agent(agent_name):
            self.orchestrator.register_agent(
                name=agent_name,
                description=f"Schema-driven extractor for {schema.contract_type}",
                system_prompt=system_prompt,
                temperature=schema.extraction_temperature,
                max_tokens=schema.max_tokens,
            )

    def _build_result(
        self,
        schema: ContractSchema,
        contract_id: str,
        extracted_data: dict[str, Any],
        start_time: float,
    ) -> ExtractionResult:
        """Build the extraction result with validation."""
        warnings = []
        missing_required = []

        # Check required sections
        for section_name in schema.required_sections:
            if section_name not in extracted_data:
                missing_required.append(section_name)
                warnings.append(f"Missing required section: {section_name}")

        # Check required fields in each section
        section_confidences = {}
        for section_name, section in schema.sections.items():
            section_data = extracted_data.get(section_name, {})

            fields_found = 0
            fields_total = len(section.fields)

            for field_name, field in section.fields.items():
                value = section_data.get(field_name) if isinstance(section_data, dict) else None

                if value is not None and value != "" and value != []:
                    fields_found += 1
                elif field.required:
                    missing_required.append(f"{section_name}.{field_name}")
                    warnings.append(f"Missing required field: {section_name}.{field_name}")

            section_confidences[section_name] = (
                fields_found / fields_total if fields_total > 0 else 0.0
            )

        # Calculate overall confidence
        overall_confidence = (
            sum(section_confidences.values()) / len(section_confidences)
            if section_confidences
            else 0.0
        )

        extraction_time_ms = int((time.time() - start_time) * 1000)

        return ExtractionResult(
            schema_id=schema.schema_id,
            contract_id=contract_id,
            extracted_data=extracted_data,
            overall_confidence=overall_confidence,
            section_confidences=section_confidences,
            missing_required_fields=missing_required,
            extraction_warnings=warnings,
            model_used=schema.extraction_model,
            extraction_time_ms=extraction_time_ms,
        )


# Singleton instance
_extractor: SchemaExtractor | None = None


def get_schema_extractor() -> SchemaExtractor:
    """Get the global schema extractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = SchemaExtractor()
    return _extractor


async def extract_with_schema(
    contract_text: str,
    schema_id: str | None = None,
    contract_type: str | None = None,
    contract_id: str | None = None,
    user_id: str = "system",
) -> ExtractionResult:
    """Convenience function for schema-based extraction.

    Args:
        contract_text: The contract text to extract from.
        schema_id: Specific schema ID to use.
        contract_type: Contract type to auto-select schema.
        contract_id: Contract ID for tracking.
        user_id: User ID for tracking.

    Returns:
        ExtractionResult with extracted data.
    """
    extractor = get_schema_extractor()
    return await extractor.extract(
        contract_text=contract_text,
        schema_id=schema_id,
        contract_type=contract_type,
        contract_id=contract_id,
        user_id=user_id,
    )

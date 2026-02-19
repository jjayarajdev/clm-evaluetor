"""Custom field validation service."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from difflib import get_close_matches
from typing import Any

from app.models.tenant import Tenant
from app.schemas.custom_fields import CustomFieldValue, CustomFieldsValidationResult, FieldType


class CustomFieldValidator:
    """Validates custom field values against tenant's field definitions."""

    def __init__(self, tenant: Tenant, entity_type: str):
        """Initialize validator with tenant and entity type.

        Args:
            tenant: The tenant whose field definitions to use.
            entity_type: The entity type (contract, obligation, clause, client).
        """
        self.tenant = tenant
        self.entity_type = entity_type
        self.field_definitions = self._load_field_definitions()

    def _load_field_definitions(self) -> dict[str, dict]:
        """Load field definitions from tenant config."""
        definitions = self.tenant.custom_field_definitions or {}
        fields = definitions.get(self.entity_type, [])
        return {f["name"]: f for f in fields if not f.get("is_archived", False)}

    def validate(self, custom_fields: dict[str, Any]) -> CustomFieldsValidationResult:
        """Validate custom fields against tenant's definitions.

        Args:
            custom_fields: Dictionary of field_name -> value pairs.

        Returns:
            Validation result with validity status and any errors.
        """
        errors: list[str] = []
        validated_fields: list[CustomFieldValue] = []

        # Check for required fields
        for name, definition in self.field_definitions.items():
            if definition.get("required", False):
                if name not in custom_fields or custom_fields.get(name) in (None, "", []):
                    label = definition.get("label", name)
                    errors.append(f"Required field '{label}' is missing")
                    validated_fields.append(
                        CustomFieldValue(
                            name=name,
                            value=None,
                            is_valid=False,
                            validation_error=f"Required field is missing",
                        )
                    )

        # Validate each provided field
        for name, value in custom_fields.items():
            if name not in self.field_definitions:
                # Unknown field - skip but don't error (allow flexibility)
                continue

            definition = self.field_definitions[name]
            field_result = self._validate_field(name, value, definition)
            validated_fields.append(field_result)

            if not field_result.is_valid:
                errors.append(field_result.validation_error or f"Invalid value for '{name}'")

        return CustomFieldsValidationResult(
            is_valid=len(errors) == 0,
            fields=validated_fields,
            errors=errors,
        )

    def _validate_field(
        self, name: str, value: Any, definition: dict
    ) -> CustomFieldValue:
        """Validate a single field value."""
        field_type = definition.get("field_type", "text")
        label = definition.get("label", name)

        # Allow None/empty for non-required fields
        if value in (None, "", []) and not definition.get("required", False):
            return CustomFieldValue(name=name, value=value, is_valid=True)

        try:
            if field_type == FieldType.TEXT.value:
                return self._validate_text(name, value, definition)
            elif field_type == FieldType.NUMBER.value:
                return self._validate_number(name, value, definition)
            elif field_type == FieldType.DATE.value:
                return self._validate_date(name, value, definition)
            elif field_type == FieldType.DROPDOWN.value:
                return self._validate_dropdown(name, value, definition)
            elif field_type == FieldType.MULTI_SELECT.value:
                return self._validate_multi_select(name, value, definition)
            elif field_type == FieldType.CHECKBOX.value:
                return self._validate_checkbox(name, value, definition)
            elif field_type == FieldType.URL.value:
                return self._validate_url(name, value, definition)
            elif field_type == FieldType.EMAIL.value:
                return self._validate_email(name, value, definition)
            elif field_type == FieldType.CURRENCY.value:
                return self._validate_currency(name, value, definition)
            else:
                # Unknown type - accept as text
                return CustomFieldValue(name=name, value=str(value), is_valid=True)
        except Exception as e:
            return CustomFieldValue(
                name=name,
                value=value,
                is_valid=False,
                validation_error=f"Validation error for '{label}': {str(e)}",
            )

    def _validate_text(self, name: str, value: Any, definition: dict) -> CustomFieldValue:
        """Validate text field."""
        str_value = str(value)
        return CustomFieldValue(name=name, value=str_value, is_valid=True)

    def _validate_number(self, name: str, value: Any, definition: dict) -> CustomFieldValue:
        """Validate number field."""
        label = definition.get("label", name)

        if isinstance(value, (int, float, Decimal)):
            return CustomFieldValue(name=name, value=float(value), is_valid=True)

        # Try to parse string as number
        try:
            num_value = float(str(value).replace(",", ""))
            return CustomFieldValue(name=name, value=num_value, is_valid=True)
        except (ValueError, InvalidOperation):
            return CustomFieldValue(
                name=name,
                value=value,
                is_valid=False,
                validation_error=f"'{label}' must be a valid number",
            )

    def _validate_date(self, name: str, value: Any, definition: dict) -> CustomFieldValue:
        """Validate date field."""
        label = definition.get("label", name)

        if isinstance(value, date):
            return CustomFieldValue(name=name, value=value.isoformat(), is_valid=True)

        if isinstance(value, datetime):
            return CustomFieldValue(name=name, value=value.date().isoformat(), is_valid=True)

        # Try to parse string as date
        str_value = str(value)
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"]:
            try:
                parsed = datetime.strptime(str_value, fmt)
                return CustomFieldValue(
                    name=name, value=parsed.date().isoformat(), is_valid=True
                )
            except ValueError:
                continue

        return CustomFieldValue(
            name=name,
            value=value,
            is_valid=False,
            validation_error=f"'{label}' must be a valid date (YYYY-MM-DD)",
        )

    def _validate_dropdown(
        self, name: str, value: Any, definition: dict
    ) -> CustomFieldValue:
        """Validate dropdown field with fuzzy matching."""
        label = definition.get("label", name)
        options = definition.get("options", [])

        if not options:
            return CustomFieldValue(name=name, value=value, is_valid=True)

        str_value = str(value).strip()
        options_lower = {o.lower(): o for o in options}

        # Exact match (case insensitive)
        if str_value.lower() in options_lower:
            return CustomFieldValue(
                name=name, value=options_lower[str_value.lower()], is_valid=True
            )

        # Fuzzy match
        matches = get_close_matches(str_value.lower(), options_lower.keys(), n=1, cutoff=0.6)
        if matches:
            return CustomFieldValue(
                name=name, value=options_lower[matches[0]], is_valid=True
            )

        return CustomFieldValue(
            name=name,
            value=value,
            is_valid=False,
            validation_error=f"'{label}' must be one of: {', '.join(options)}",
        )

    def _validate_multi_select(
        self, name: str, value: Any, definition: dict
    ) -> CustomFieldValue:
        """Validate multi-select field."""
        label = definition.get("label", name)
        options = definition.get("options", [])

        if not isinstance(value, list):
            value = [value]

        valid_values = []
        invalid_values = []

        options_lower = {o.lower(): o for o in options}

        for v in value:
            str_v = str(v).strip().lower()
            if str_v in options_lower:
                valid_values.append(options_lower[str_v])
            else:
                # Try fuzzy match
                matches = get_close_matches(str_v, options_lower.keys(), n=1, cutoff=0.6)
                if matches:
                    valid_values.append(options_lower[matches[0]])
                else:
                    invalid_values.append(v)

        if invalid_values:
            return CustomFieldValue(
                name=name,
                value=value,
                is_valid=False,
                validation_error=f"'{label}' contains invalid options: {', '.join(map(str, invalid_values))}",
            )

        return CustomFieldValue(name=name, value=valid_values, is_valid=True)

    def _validate_checkbox(
        self, name: str, value: Any, definition: dict
    ) -> CustomFieldValue:
        """Validate checkbox/boolean field."""
        if isinstance(value, bool):
            return CustomFieldValue(name=name, value=value, is_valid=True)

        str_value = str(value).lower()
        if str_value in ("true", "yes", "1", "on"):
            return CustomFieldValue(name=name, value=True, is_valid=True)
        elif str_value in ("false", "no", "0", "off"):
            return CustomFieldValue(name=name, value=False, is_valid=True)

        label = definition.get("label", name)
        return CustomFieldValue(
            name=name,
            value=value,
            is_valid=False,
            validation_error=f"'{label}' must be true or false",
        )

    def _validate_url(self, name: str, value: Any, definition: dict) -> CustomFieldValue:
        """Validate URL field."""
        label = definition.get("label", name)
        str_value = str(value).strip()

        url_pattern = re.compile(
            r"^https?://"
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
            r"localhost|"
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
            r"(?::\d+)?"
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )

        if url_pattern.match(str_value):
            return CustomFieldValue(name=name, value=str_value, is_valid=True)

        return CustomFieldValue(
            name=name,
            value=value,
            is_valid=False,
            validation_error=f"'{label}' must be a valid URL",
        )

    def _validate_email(self, name: str, value: Any, definition: dict) -> CustomFieldValue:
        """Validate email field."""
        label = definition.get("label", name)
        str_value = str(value).strip()

        email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

        if email_pattern.match(str_value):
            return CustomFieldValue(name=name, value=str_value, is_valid=True)

        return CustomFieldValue(
            name=name,
            value=value,
            is_valid=False,
            validation_error=f"'{label}' must be a valid email address",
        )

    def _validate_currency(
        self, name: str, value: Any, definition: dict
    ) -> CustomFieldValue:
        """Validate currency field (number with optional currency symbol)."""
        label = definition.get("label", name)

        # Remove currency symbols and whitespace
        str_value = str(value).strip()
        cleaned = re.sub(r"[£$€¥₹\s,]", "", str_value)

        try:
            num_value = float(cleaned)
            return CustomFieldValue(name=name, value=num_value, is_valid=True)
        except ValueError:
            return CustomFieldValue(
                name=name,
                value=value,
                is_valid=False,
                validation_error=f"'{label}' must be a valid currency amount",
            )

    def normalize_values(self, custom_fields: dict[str, Any]) -> dict[str, Any]:
        """Normalize field values according to their definitions.

        This cleans and standardizes values without full validation.
        Useful for AI-extracted data that needs normalization.

        Args:
            custom_fields: Dictionary of field_name -> value pairs.

        Returns:
            Normalized dictionary with cleaned values.
        """
        normalized = {}

        for name, value in custom_fields.items():
            if name not in self.field_definitions:
                # Keep unknown fields as-is
                normalized[name] = value
                continue

            definition = self.field_definitions[name]
            result = self._validate_field(name, value, definition)

            if result.is_valid:
                normalized[name] = result.value
            else:
                # Keep original value if validation fails
                normalized[name] = value

        return normalized


def get_validator(tenant: Tenant, entity_type: str) -> CustomFieldValidator:
    """Factory function to create a validator."""
    return CustomFieldValidator(tenant, entity_type)

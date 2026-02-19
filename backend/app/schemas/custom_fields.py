"""Schemas for custom field definitions and values."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FieldType(str, Enum):
    """Supported custom field types."""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    DROPDOWN = "dropdown"
    MULTI_SELECT = "multi_select"
    CHECKBOX = "checkbox"
    URL = "url"
    EMAIL = "email"
    CURRENCY = "currency"


class EntityType(str, Enum):
    """Entity types that support custom fields."""

    CONTRACT = "contract"
    OBLIGATION = "obligation"
    CLAUSE = "clause"
    CLIENT = "client"


class CustomFieldDefinition(BaseModel):
    """Schema for defining a custom field."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Field identifier (lowercase, underscores allowed)",
    )
    label: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display label for the field",
    )
    field_type: FieldType = Field(
        ...,
        description="Type of the field",
    )
    required: bool = Field(
        default=False,
        description="Whether the field is required",
    )
    options: list[str] | None = Field(
        default=None,
        description="Options for dropdown/multi_select fields",
    )
    default_value: Any | None = Field(
        default=None,
        description="Default value for the field",
    )
    placeholder: str | None = Field(
        default=None,
        max_length=200,
        description="Placeholder text for input",
    )
    help_text: str | None = Field(
        default=None,
        max_length=500,
        description="Help text shown to users",
    )
    display_order: int = Field(
        default=0,
        ge=0,
        description="Order in which to display the field",
    )
    is_searchable: bool = Field(
        default=True,
        description="Whether this field should be searchable",
    )
    is_visible_in_list: bool = Field(
        default=False,
        description="Whether to show this field in list/table views",
    )

    # AI Extraction helpers
    extraction_hints: str | None = Field(
        default=None,
        max_length=500,
        description="Hints to help AI extract this field (e.g., 'Look for Department:, Business Unit:')",
    )
    extraction_patterns: list[str] | None = Field(
        default=None,
        description="Regex patterns to help identify the field value",
    )
    extraction_examples: list[str] | None = Field(
        default=None,
        description="Example values to help AI understand the expected format",
    )


class CustomFieldCreate(BaseModel):
    """Request schema for creating a custom field."""

    field: CustomFieldDefinition


class CustomFieldUpdate(BaseModel):
    """Request schema for updating a custom field."""

    label: str | None = Field(default=None, min_length=1, max_length=100)
    required: bool | None = None
    options: list[str] | None = None
    default_value: Any | None = None
    placeholder: str | None = None
    help_text: str | None = None
    display_order: int | None = None
    is_searchable: bool | None = None
    is_visible_in_list: bool | None = None
    extraction_hints: str | None = None
    extraction_patterns: list[str] | None = None
    extraction_examples: list[str] | None = None


class CustomFieldResponse(BaseModel):
    """Response schema for a custom field."""

    name: str
    label: str
    field_type: FieldType
    required: bool
    options: list[str] | None = None
    default_value: Any | None = None
    placeholder: str | None = None
    help_text: str | None = None
    display_order: int
    is_searchable: bool
    is_visible_in_list: bool
    extraction_hints: str | None = None
    extraction_patterns: list[str] | None = None
    extraction_examples: list[str] | None = None


class CustomFieldsListResponse(BaseModel):
    """Response schema for listing custom fields."""

    entity_type: EntityType
    fields: list[CustomFieldResponse]


class CustomFieldValue(BaseModel):
    """Schema for a custom field value with validation info."""

    name: str
    value: Any
    is_valid: bool = True
    validation_error: str | None = None


class CustomFieldsValidationResult(BaseModel):
    """Result of validating custom fields."""

    is_valid: bool
    fields: list[CustomFieldValue]
    errors: list[str]

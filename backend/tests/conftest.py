"""Pytest configuration and fixtures for CLM tests."""

import pytest
import uuid
from datetime import datetime


@pytest.fixture
def tenant_id():
    """Generate a test tenant ID."""
    return uuid.uuid4()


@pytest.fixture
def user_id():
    """Generate a test user ID."""
    return uuid.uuid4()


@pytest.fixture
def contract_id():
    """Generate a test contract ID."""
    return uuid.uuid4()


@pytest.fixture
def business_unit_id():
    """Generate a test business unit ID."""
    return uuid.uuid4()


@pytest.fixture
def external_user_id():
    """Generate a test external user ID."""
    return uuid.uuid4()

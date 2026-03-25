"""Tests for Contract Document functionality."""

import pytest
import uuid
from datetime import datetime

from app.models.contract_document import (
    ContractDocument,
    DocumentSignature,
    DocumentSection,
    DocumentType,
    SignatureType,
    SignatureStatus,
)
from app.schemas.contract_document import (
    ContractDocumentCreate,
    ContractDocumentUpdate,
    DocumentSignatureCreate,
    DocumentSectionCreate,
)


class TestContractDocumentModel:
    """Tests for ContractDocument model."""

    def test_create_document(self):
        """Test ContractDocument model creation with required fields."""
        contract_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        doc = ContractDocument(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            contract_id=contract_id,
            document_type="amendment",
            title="First Amendment",
            description="Amendment to extend term",
            language="en",
            is_active=True,
        )
        assert doc.contract_id == contract_id
        assert doc.tenant_id == tenant_id
        assert doc.document_type == "amendment"
        assert doc.title == "First Amendment"
        assert doc.description == "Amendment to extend term"

    def test_document_repr(self):
        """Test ContractDocument string representation."""
        doc = ContractDocument(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            document_type="main_agreement",
            title="Master Services Agreement",
        )
        result = repr(doc)
        assert "Master Services Agreement" in result
        assert "main_agreement" in result

    def test_default_language(self):
        """Test ContractDocument default language is 'en'."""
        lang_col = ContractDocument.__table__.columns["language"]
        assert lang_col.default.arg == "en"

    def test_default_is_active(self):
        """Test ContractDocument default is_active is True."""
        is_active_col = ContractDocument.__table__.columns["is_active"]
        assert is_active_col.default.arg is True


class TestDocumentSignatureModel:
    """Tests for DocumentSignature model."""

    def test_create_signature(self):
        """Test DocumentSignature model creation with all fields."""
        doc_id = uuid.uuid4()
        sig = DocumentSignature(
            id=uuid.uuid4(),
            document_id=doc_id,
            signer_name="Jane Doe",
            signer_title="CEO",
            signer_organization="Acme Corp",
            signer_email="jane@acme.com",
            signature_type="digital",
            signature_status="signed",
            notes="Signed via DocuSign",
        )
        assert sig.document_id == doc_id
        assert sig.signer_name == "Jane Doe"
        assert sig.signer_title == "CEO"
        assert sig.signer_organization == "Acme Corp"
        assert sig.signer_email == "jane@acme.com"
        assert sig.signature_type == "digital"
        assert sig.signature_status == "signed"
        assert sig.notes == "Signed via DocuSign"

    def test_signature_types(self):
        """Test all expected signature types exist."""
        expected = ["wet_ink", "digital", "electronic", "stamp"]
        actual = [t.value for t in SignatureType]
        for stype in expected:
            assert stype in actual
        assert len(actual) == len(expected)

    def test_signature_statuses(self):
        """Test all expected signature statuses exist."""
        expected = ["pending", "signed", "declined", "expired"]
        actual = [s.value for s in SignatureStatus]
        for status in expected:
            assert status in actual
        assert len(actual) == len(expected)


class TestDocumentSectionModel:
    """Tests for DocumentSection model."""

    def test_create_section(self):
        """Test DocumentSection model creation with title and section_number."""
        doc_id = uuid.uuid4()
        section = DocumentSection(
            id=uuid.uuid4(),
            document_id=doc_id,
            title="Definitions",
            section_number="1.0",
            content_summary="Key terms and definitions",
            page_start=3,
            page_end=5,
            order_index=1,
        )
        assert section.document_id == doc_id
        assert section.title == "Definitions"
        assert section.section_number == "1.0"
        assert section.content_summary == "Key terms and definitions"
        assert section.page_start == 3
        assert section.page_end == 5
        assert section.order_index == 1

    def test_self_referencing_parent(self):
        """Test DocumentSection with parent_section_id set."""
        parent_id = uuid.uuid4()
        section = DocumentSection(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            parent_section_id=parent_id,
            title="Sub-definitions",
            section_number="1.1",
            order_index=0,
        )
        assert section.parent_section_id == parent_id


class TestContractDocumentSchemas:
    """Tests for ContractDocument Pydantic schemas."""

    def test_create_schema(self):
        """Test ContractDocumentCreate schema validation."""
        data = ContractDocumentCreate(
            title="Statement of Work #1",
            document_type="statement_of_work",
        )
        assert data.title == "Statement of Work #1"
        assert data.document_type == "statement_of_work"
        assert data.language == "en"
        assert data.description is None
        assert data.version is None
        assert data.file_path is None
        assert data.file_size is None
        assert data.mime_type is None

    def test_update_schema_partial(self):
        """Test ContractDocumentUpdate with partial data."""
        data = ContractDocumentUpdate(title="Updated Title", is_active=False)
        assert data.title == "Updated Title"
        assert data.is_active is False
        assert data.document_type is None
        assert data.description is None
        assert data.language is None
        assert data.version is None
        assert data.file_path is None
        assert data.file_size is None
        assert data.mime_type is None

    def test_signature_create_schema(self):
        """Test DocumentSignatureCreate schema validation."""
        data = DocumentSignatureCreate(
            signer_name="John Smith",
            signer_title="General Counsel",
            signer_organization="TechStart Inc",
            signer_email="john@techstart.com",
            signature_type="electronic",
            signature_status="pending",
        )
        assert data.signer_name == "John Smith"
        assert data.signer_title == "General Counsel"
        assert data.signature_type == "electronic"
        assert data.signature_status == "pending"
        assert data.notes is None

    def test_section_create_schema(self):
        """Test DocumentSectionCreate schema validation."""
        parent_id = uuid.uuid4()
        data = DocumentSectionCreate(
            parent_section_id=parent_id,
            section_number="2.3",
            title="Payment Terms",
            content_summary="Details of payment schedule and methods",
            page_start=10,
            page_end=12,
            order_index=5,
        )
        assert data.parent_section_id == parent_id
        assert data.section_number == "2.3"
        assert data.title == "Payment Terms"
        assert data.content_summary == "Details of payment schedule and methods"
        assert data.page_start == 10
        assert data.page_end == 12
        assert data.order_index == 5


class TestDocumentTypeEnum:
    """Tests for DocumentType enum."""

    def test_all_types(self):
        """Test all 10 expected document types exist."""
        expected = [
            "main_agreement",
            "amendment",
            "addendum",
            "schedule",
            "exhibit",
            "statement_of_work",
            "side_letter",
            "appendix",
            "certificate",
            "other",
        ]
        actual = [t.value for t in DocumentType]
        for dtype in expected:
            assert dtype in actual
        assert len(actual) == 10

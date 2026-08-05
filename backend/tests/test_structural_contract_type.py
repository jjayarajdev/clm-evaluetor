"""Filename-based structural contract-type correction (pipeline + backfill)."""

import pytest

from app.services.contract_types import structural_contract_type_from_filename as fix


@pytest.mark.parametrize(
    "filename,current,expected",
    [
        # A schedule/exhibit/attachment mis-typed as a master is downgraded.
        ("Schedule 13 Audit Controls and Compliance-Nov2022.docx", "msa", "schedule"),
        ("Exhibit 34 (Benchmarking) Final v1.91.doc", "service_agreement", "schedule"),
        ("Attachment 3-C (Critical Deliverables) Final v1.8.doc", "msa", "schedule"),
        ("Appendix B Pricing.pdf", "vendor_agreement", "schedule"),
        # SOW-named masters become sow.
        ("SOW 122 SAP & Replicon.pdf", "msa", "sow"),
        ("CSOW0004949 change.pdf", "service_agreement", "sow"),
        # Amendments/allonges are always corrected, regardless of current type.
        ("OL159.01 HOVK Dental Divas allonge #1 2016.pdf", "lease", "amendment"),
        ("Avenant 2 au contrat.pdf", "service_agreement", "amendment"),
        ("MSA Amendment 3.pdf", "msa", "amendment"),
        ("Addendum to Lease.pdf", "lease", "amendment"),
    ],
)
def test_corrects_structural_and_amendment(filename, current, expected):
    assert fix(filename, current) == expected


@pytest.mark.parametrize(
    "filename,current",
    [
        # A specific subordinate type the model got right is NOT clobbered:
        # only MASTER mis-types are downgraded on structural filenames.
        ("Schedule 08 Pricing.docx", "pricing"),
        ("Exhibit 6 Governance.doc", "governance"),
        ("Schedule 03 Service Levels.docx", "sla"),
        # A genuine master with a normal name is left alone.
        ("AlgoLeap Technologies MSA - DocuSign.pdf", "msa"),
        ("LSA Belgium Final v1.3 KPN.doc", "service_agreement"),
        # Already an amendment — no-op (idempotent).
        ("allonge #2.pdf", "amendment"),
        # No decisive signal.
        ("Random Contract.pdf", "other"),
        ("", "msa"),
    ],
)
def test_leaves_correct_or_ambiguous_types_untouched(filename, current):
    assert fix(filename, current) is None


def test_idempotent_on_rerun():
    # First pass corrects; second pass (with the corrected type) is a no-op.
    fn = "Schedule 13 Audit Controls.docx"
    first = fix(fn, "msa")
    assert first == "schedule"
    assert fix(fn, first) is None

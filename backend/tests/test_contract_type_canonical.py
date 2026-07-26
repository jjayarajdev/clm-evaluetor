"""Contract-type canonicalization — the controlled display/filter/storage vocab.

Pins `canonical_contract_type` so the messy long tail of AI-extracted types
("roles_and_responsibilities_matrix", "termination_charges", NL "oplevering", …)
keeps collapsing into a small, stable set instead of leaking into filters/lists.
"""

import pytest

from app.services.contract_types import (
    CANONICAL_CONTRACT_TYPES,
    canonical_contract_type,
    normalize_contract_type,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        # real agreement types survive as themselves
        ("sow", "sow"),
        ("Statement of Work (SOW)", "sow"),
        ("msa", "msa"),
        ("Master Services Agreement", "msa"),
        ("nda", "nda"),
        # service-level vs generic service agreements split correctly
        ("service_levels_agreement", "sla"),
        ("Service Level Agreement", "sla"),
        ("network_services_agreement", "service_agreement"),
        ("managed_voice_services", "service_agreement"),
        ("end_user_computing_design_and_support_services_agreement", "service_agreement"),
        # lease family
        ("lease", "lease"),
        ("huurovereenkomst_kantoorruimte", "lease"),  # NL: office lease
        # amendments win over the parent type
        ("significant_change_control_notice", "amendment"),
        ("amendment", "amendment"),
        # pricing / financial schedules
        ("termination_charges", "pricing"),
        ("tariff_agreement", "pricing"),
        ("financial_provisions_agreement", "pricing"),
        # governance / operating model
        ("roles_and_responsibilities_matrix", "governance"),
        ("governance_and_operating_model_agreement", "governance"),
        ("continuous_improvement_and_benefit_sharing_agreement", "governance"),
        # policies & procedures (NOT amendments, even with "change" in the name)
        ("policies", "policy"),
        ("change_control_procedure", "policy"),
        ("procedural_change_management_procedure", "policy"),
        ("compliance_agreement", "policy"),
        # memoranda
        ("memorandum_of_understanding", "mou"),
        # procurement / hardware
        ("hardware_procurement_contract", "order"),
        # NL delivery/handover schedules
        ("medikliniek_oplevering", "schedule"),
        ("proces_verbaal_van_oplevering", "schedule"),
        # truly generic → other (never a raw slug)
        ("photo_agreement", "other"),
        ("business_agreement", "other"),
    ],
)
def test_canonicalization(raw, expected):
    assert canonical_contract_type(raw) == expected


def test_empty_input_returns_none_so_existing_value_is_left_intact():
    assert canonical_contract_type(None) is None
    assert canonical_contract_type("") is None
    assert canonical_contract_type("   ") is None


def test_always_lands_in_the_controlled_vocabulary():
    samples = [
        "roles_and_responsibilities_matrix", "termination_charges", "policies",
        "network_services_agreement", "photo_agreement", "sow", "lease",
    ]
    for raw in samples:
        assert canonical_contract_type(raw) in CANONICAL_CONTRACT_TYPES


def test_idempotent_no_collision_with_strict_aliases():
    # "service_agreement" spelled out is a strict alias for msa; canonicalizing
    # an already-canonical code must NOT re-map it (would corrupt on re-runs and
    # make the framework linker treat a service agreement as a master).
    assert canonical_contract_type("service_agreement") == "service_agreement"
    assert normalize_contract_type("service_agreement") == "msa"  # documents the trap
    for code in CANONICAL_CONTRACT_TYPES:
        assert canonical_contract_type(code) == code

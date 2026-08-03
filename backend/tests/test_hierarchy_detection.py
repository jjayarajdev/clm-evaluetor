"""Tests for hierarchy-detection dedupe + document-card caching.

Covers the cost fixes: single detection trigger, pre-classification pair
filtering against existing links/suggestions, cross-run suggestion dedupe,
and the contracts.hierarchy_card cache that avoids re-extracting cards.
"""

import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import JSON, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.database import Base
from app.models.contract import Contract, ContractStatus
from app.models.contract_link import ContractLink
from app.models.suggested_link import SuggestedContractLink
from app.models.tenant import Tenant
from app.services.hierarchy_detection import (
    _load_existing_pairs,
    detect_hierarchy,
    get_hierarchy_scope,
    should_detect,
)
from app.services.hierarchy_detection.hierarchy_builder import HierarchyBuilder
from app.services.hierarchy_detection.models import (
    ClassifiedPair,
    DocumentCard,
    PairCandidate,
    ParentReference,
    PartyInfo,
    RelationshipType,
)
from app.services.hierarchy_detection.relationship_classifier import RelationshipClassifier
from app.services.hierarchy_detection.smart_extractor import SmartDocumentExtractor

TENANT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
USER_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest_asyncio.fixture(scope="function")
async def db():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    # Map PostgreSQL JSONB → JSON so SQLite can create tables
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
    # Dedupe indexes declared both column-level and in __table_args__
    seen_idx = set()
    for table in Base.metadata.tables.values():
        deduped = [i for i in table.indexes if i.name not in seen_idx and not seen_idx.add(i.name)]
        table.indexes.clear()
        table.indexes.update(deduped)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(eng, expire_on_commit=False)
    async with maker() as session:
        yield session
    await eng.dispose()


def _contract(name: str, text: str = "some contract text", status=ContractStatus.COMPLETED) -> Contract:
    return Contract(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        filename=name,
        file_path=f"/tmp/{name}",
        status=status,
        extracted_text=text,
        uploaded_by=USER_ID,
    )


def _card(contract: Contract, doc_type: str = "SOW") -> DocumentCard:
    return DocumentCard(
        contract_id=contract.id,
        filename=contract.filename,
        doc_type=doc_type,
        parties=[PartyInfo(name="Algoleap", role="provider")],
        extraction_confidence=0.9,
        content_hash="h",
    )


def _suggestion(a: Contract, b: Contract, status: str = "pending") -> SuggestedContractLink:
    return SuggestedContractLink(
        source_contract_id=a.id,
        target_contract_id=b.id,
        suggested_link_type="sow",
        suggested_direction="source_is_child",
        confidence_score=0.9,
        status=status,
        tenant_id=TENANT_ID,
    )


async def _seed(db, *objs):
    from app.models.user import Role, User

    db.add(Tenant(id=TENANT_ID, name="T", slug="t", is_active=True))
    db.add(User(
        id=USER_ID, tenant_id=TENANT_ID, username="u", email="u@t.com",
        full_name="U", password_hash="x", role=Role.ADMIN, is_active=True,
    ))
    db.add_all(objs)
    await db.commit()


class TestShouldDetect:
    @pytest.mark.asyncio
    async def test_false_when_link_exists(self, db):
        a, b = _contract("a.pdf"), _contract("b.pdf")
        await _seed(db, a, b, ContractLink(
            parent_contract_id=b.id, child_contract_id=a.id, link_type="sow",
        ))
        assert await should_detect(db, a.id) is False

    @pytest.mark.asyncio
    async def test_false_when_pending_suggestion(self, db):
        a, b = _contract("a.pdf"), _contract("b.pdf")
        await _seed(db, a, b, _suggestion(a, b, "pending"))
        assert await should_detect(db, a.id) is False
        assert await should_detect(db, b.id) is False

    @pytest.mark.asyncio
    async def test_true_when_only_rejected_or_expired(self, db):
        a, b = _contract("a.pdf"), _contract("b.pdf")
        await _seed(db, a, b, _suggestion(a, b, "rejected"), _suggestion(b, a, "expired"))
        assert await should_detect(db, a.id) is True


class TestHierarchyScope:
    @pytest.mark.asyncio
    async def test_union_includes_seed_and_portfolio(self, db):
        seed_contract = _contract("new.pdf", status=ContractStatus.PROCESSING)
        old = [_contract(f"old{i}.pdf") for i in range(3)]
        await _seed(db, seed_contract, *old)
        scope = await get_hierarchy_scope(db, TENANT_ID, [seed_contract.id])
        assert scope[0] == seed_contract.id  # seed first, even if not COMPLETED
        assert set(scope) == {seed_contract.id, *[c.id for c in old]}

    @pytest.mark.asyncio
    async def test_seed_not_duplicated_when_in_portfolio(self, db):
        a, b = _contract("a.pdf"), _contract("b.pdf")
        await _seed(db, a, b)
        scope = await get_hierarchy_scope(db, TENANT_ID, [a.id])
        assert scope.count(a.id) == 1
        assert len(scope) == 2  # 1-doc batch + portfolio ≥ 2 enables detection


class TestPairFilter:
    def _stub_cards(self, monkeypatch, contracts):
        cards = {c.id: _card(c) for c in contracts}
        monkeypatch.setattr(
            SmartDocumentExtractor, "extract_batch",
            AsyncMock(return_value=cards),
        )
        return cards

    def _stub_candidates(self, monkeypatch, pairs):
        from app.services.hierarchy_detection.candidate_generator import CandidatePairGenerator
        monkeypatch.setattr(
            CandidatePairGenerator, "generate",
            lambda self, cards: [PairCandidate(contract_a_id=a, contract_b_id=b) for a, b in pairs],
        )

    @pytest.mark.asyncio
    async def test_linked_pair_not_classified(self, db, monkeypatch):
        a, b, c = _contract("a.pdf"), _contract("b.pdf"), _contract("c.pdf")
        await _seed(db, a, b, c, ContractLink(
            parent_contract_id=a.id, child_contract_id=b.id, link_type="sow",
        ))
        self._stub_cards(monkeypatch, [a, b, c])
        self._stub_candidates(monkeypatch, [(a.id, b.id), (a.id, c.id)])
        classify = AsyncMock(return_value=[])
        monkeypatch.setattr(RelationshipClassifier, "classify_batch", classify)

        await detect_hierarchy(db, [a.id, b.id, c.id], TENANT_ID, "t1")

        seen = {(min(p.contract_a_id, p.contract_b_id), max(p.contract_a_id, p.contract_b_id))
                for p in classify.await_args.args[0]}
        assert (min(a.id, b.id), max(a.id, b.id)) not in seen
        assert (min(a.id, c.id), max(a.id, c.id)) in seen

    @pytest.mark.asyncio
    async def test_reversed_direction_suggestion_filtered(self, db, monkeypatch):
        a, b = _contract("a.pdf"), _contract("b.pdf")
        await _seed(db, a, b, _suggestion(b, a, "pending"))  # reversed direction
        self._stub_cards(monkeypatch, [a, b])
        self._stub_candidates(monkeypatch, [(a.id, b.id)])
        classify = AsyncMock(return_value=[])
        monkeypatch.setattr(RelationshipClassifier, "classify_batch", classify)

        result = await detect_hierarchy(db, [a.id, b.id], TENANT_ID, "t2")

        assert result == 0
        classify.assert_not_awaited()  # all pairs filtered before classification

    @pytest.mark.asyncio
    async def test_repeat_run_creates_no_duplicates(self, db, monkeypatch):
        a, b = _contract("a.pdf"), _contract("b.pdf")
        await _seed(db, a, b)
        self._stub_cards(monkeypatch, [a, b])
        self._stub_candidates(monkeypatch, [(a.id, b.id)])
        monkeypatch.setattr(
            RelationshipClassifier, "classify_batch",
            AsyncMock(return_value=[ClassifiedPair(
                contract_a_id=a.id, contract_b_id=b.id,
                relationship=RelationshipType.SAME_DOCUMENT_FAMILY,
                parent_id=b.id, child_id=a.id,
                link_type="sow_to_msa", confidence=0.95, reasoning="family",
            )]),
        )

        n1 = await detect_hierarchy(db, [a.id, b.id], TENANT_ID, "run1")
        await db.commit()
        n2 = await detect_hierarchy(db, [a.id, b.id], TENANT_ID, "run2")
        await db.commit()

        rows = (await db.execute(select(SuggestedContractLink))).scalars().all()
        assert n1 == 1 and n2 == 0
        assert len(rows) == 1  # the actual regression: no duplicate suggestions

    @pytest.mark.asyncio
    async def test_builder_skips_existing_pairs(self):
        a_id, b_id = uuid.uuid4(), uuid.uuid4()
        pair = ClassifiedPair(
            contract_a_id=a_id, contract_b_id=b_id,
            relationship=RelationshipType.SAME_DOCUMENT_FAMILY,
            parent_id=b_id, child_id=a_id,
            link_type="sow_to_msa", confidence=0.95, reasoning="x",
        )
        cards = {}
        builder = HierarchyBuilder()
        out = await builder.build_and_persist(
            db=None, classified_pairs=[pair], cards=cards,
            tenant_id=TENANT_ID, batch_id="b",
            existing_pairs={(min(a_id, b_id), max(a_id, b_id))},
        )
        assert out == []

    @pytest.mark.asyncio
    async def test_load_existing_pairs_normalizes(self, db):
        a, b, c = _contract("a.pdf"), _contract("b.pdf"), _contract("c.pdf")
        await _seed(
            db, a, b, c,
            ContractLink(parent_contract_id=a.id, child_contract_id=b.id, link_type="sow"),
            _suggestion(c, a, "pending"),
            _suggestion(c, b, "rejected"),  # dead — must not count
        )
        pairs = await _load_existing_pairs(db, [a.id, b.id, c.id])
        assert (min(a.id, b.id), max(a.id, b.id)) in pairs
        assert (min(a.id, c.id), max(a.id, c.id)) in pairs
        assert (min(b.id, c.id), max(b.id, c.id)) not in pairs


class TestCardCache:
    @pytest.mark.asyncio
    async def test_cache_hit_skips_llm(self, db, monkeypatch):
        a = _contract("a.pdf", text="stable text")
        extractor = SmartDocumentExtractor()
        a.hierarchy_card = _card(a).to_dict() | {"content_hash": extractor._content_hash(a)}
        await _seed(db, a)

        extract_single = AsyncMock()
        monkeypatch.setattr(SmartDocumentExtractor, "_extract_single", extract_single)

        cards = await extractor.extract_batch(db, [a.id])

        extract_single.assert_not_awaited()
        assert cards[a.id].contract_id == a.id
        assert cards[a.id].doc_type == "SOW"
        assert cards[a.id].parties[0].name == "Algoleap"

    @pytest.mark.asyncio
    async def test_cache_miss_on_changed_text(self, db, monkeypatch):
        a = _contract("a.pdf", text="NEW text after re-parse")
        stale = _card(a).to_dict() | {"content_hash": "stale-hash"}
        a.hierarchy_card = stale
        await _seed(db, a)

        extractor = SmartDocumentExtractor()
        fresh = _card(a)
        fresh.content_hash = extractor._content_hash(a)
        monkeypatch.setattr(
            SmartDocumentExtractor, "_extract_single", AsyncMock(return_value=fresh)
        )

        cards = await extractor.extract_batch(db, [a.id])
        await db.commit()

        assert cards[a.id] is fresh
        assert a.hierarchy_card["content_hash"] == extractor._content_hash(a)
        assert a.hierarchy_card["content_hash"] != stale["content_hash"]

    @pytest.mark.asyncio
    async def test_fallback_card_not_cached(self, db, monkeypatch):
        a = _contract("a.pdf", text="")  # no text → fallback card, no LLM
        await _seed(db, a)

        extractor = SmartDocumentExtractor()
        cards = await extractor.extract_batch(db, [a.id])
        await db.commit()

        assert cards[a.id].extraction_confidence == 0.2  # fallback
        assert a.hierarchy_card is None

    def test_document_card_roundtrip(self):
        card = DocumentCard(
            contract_id=uuid.uuid4(),
            filename="msa.pdf",
            title="Master Services Agreement",
            doc_type="MSA",
            parties=[PartyInfo(name="Vialto", role="client")],
            parent_references=[ParentReference(
                referenced_type="MSA", relationship="child_of",
                party_names=["Vialto", "Algoleap"],
            )],
            child_references=["SOW 122"],
            extraction_confidence=0.85,
            content_hash="abc",
        )
        restored = DocumentCard.from_dict(card.to_dict())
        assert restored == card

    def test_from_dict_tolerates_missing_keys(self):
        cid = uuid.uuid4()
        card = DocumentCard.from_dict({"contract_id": str(cid)})
        assert card.contract_id == cid
        assert card.parties == [] and card.parent_references == []

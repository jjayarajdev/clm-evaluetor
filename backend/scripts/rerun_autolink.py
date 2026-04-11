"""Re-run auto-link detection for all completed contracts.

Steps:
1. Clear all existing suggested_contract_links and contract_links
2. For contracts with NULL contract_type, run GPT fallback classification
3. For contracts with no _contract_references, run focused extraction
4. Fix child documents: reclassify MSA→SOW, fix filename-as-counterparty
5. Run auto-link detection for every completed contract

Usage:
    docker exec deploy-backend-1 python -m scripts.rerun_autolink
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def main():
    from app.database import async_session_maker
    from app.models.contract import Contract, ContractType, ContractStatus
    from app.models.contract_link import ContractLink
    from app.models.suggested_link import SuggestedContractLink
    from app.services.auto_link_detector import AutoLinkDetector
    from app.services.orchestrator import (
        get_orchestrator,
        AgentRequest,
        initialize_default_agents,
    )
    from app.agents import register_all_agents
    from app.agents.base import extract_json_from_response
    from app.agents.contract_reference_extraction import (
        _parse_reference_response,
        store_contract_references,
    )
    from sqlalchemy import select, delete

    initialize_default_agents()
    register_all_agents()
    orchestrator = get_orchestrator()

    # Step 1: Clear old suggestions and links
    logger.info("=== Step 1: Clearing old suggestions and links ===")
    async with async_session_maker() as session:
        result = await session.execute(delete(SuggestedContractLink))
        logger.info(f"Deleted {result.rowcount} suggested links")
        result = await session.execute(delete(ContractLink))
        logger.info(f"Deleted {result.rowcount} contract links")
        await session.commit()

    # Step 2: Load all completed contracts
    async with async_session_maker() as session:
        result = await session.execute(
            select(Contract).where(Contract.status == ContractStatus.COMPLETED)
        )
        contracts = result.scalars().all()
        logger.info(f"Found {len(contracts)} completed contracts")

    # Step 3: Fix NULL contract_type via GPT fallback
    logger.info("=== Step 2: Classifying contracts with NULL type ===")
    null_type_count = 0
    classified_count = 0
    for c in contracts:
        if c.contract_type is not None:
            continue
        null_type_count += 1
        logger.info(f"  Classifying: {c.filename} (counterparty: {c.counterparty})")
        try:
            text_sample = (c.extracted_text or "")[:3000]
            if not text_sample:
                logger.warning(f"    No extracted text, skipping")
                continue

            classify_prompt = (
                f"Classify this contract into exactly ONE of these types: "
                f"NDA, MSA, SOW, AMENDMENT, VENDOR_AGREEMENT, EMPLOYMENT_CONTRACT.\n\n"
                f"Rules:\n"
                f"- NDA: non-disclosure, confidentiality agreements\n"
                f"- MSA: master services, framework, consulting, professional services, BPO agreements\n"
                f"- SOW: statement of work, work order, schedule, service order, purchase order, EXHIBIT, ATTACHMENT, APPENDIX\n"
                f"- AMENDMENT: amendments, addenda, modifications, change orders, supplements\n"
                f"- VENDOR_AGREEMENT: license, SaaS, subscription, supply, lease, distribution agreements\n"
                f"- EMPLOYMENT_CONTRACT: employment, offer letters, contractor, non-compete agreements\n\n"
                f"IMPORTANT: Exhibits, Attachments, Schedules, and Appendices to an agreement are SOW, NOT MSA.\n\n"
                f"Respond with ONLY the type name (e.g., 'MSA'). No explanation.\n\n"
                f"Document title: {c.filename}\n"
                f"Counterparty: {c.counterparty or 'unknown'}\n\n"
                f"First 3000 chars:\n{text_sample}"
            )
            resp = await orchestrator.route_request(
                AgentRequest(
                    query=classify_prompt,
                    user_id="system",
                    session_id=f"classify_{c.id}",
                    contract_id=str(c.id),
                    context={"task": "contract_type_classification"},
                )
            )
            classified = resp.response.strip().upper().replace(" ", "_")
            type_enum_map = {t.name: t for t in ContractType}
            if classified in type_enum_map:
                async with async_session_maker() as session:
                    result = await session.execute(
                        select(Contract).where(Contract.id == c.id)
                    )
                    contract = result.scalar_one()
                    contract.contract_type = type_enum_map[classified]
                    await session.commit()
                classified_count += 1
                logger.info(f"    → {classified}")
            else:
                logger.warning(f"    → Unrecognized: {classified}")
        except Exception as e:
            logger.error(f"    Classification failed: {e}")

    logger.info(f"Classified {classified_count}/{null_type_count} contracts with NULL type")

    # Step 4: Run focused relationship extraction for contracts missing references
    logger.info("=== Step 3: Running focused relationship extraction ===")
    no_refs_count = 0
    refs_found_count = 0
    for c in contracts:
        existing_refs = (c.schema_data or {}).get("_contract_references", {})
        has_parent_refs = bool(existing_refs.get("parent_references"))
        has_child_refs = bool(existing_refs.get("child_references"))
        # Skip if we already have parent OR child references
        if has_parent_refs and has_child_refs:
            continue
        # Skip if already marked standalone with no refs
        if existing_refs.get("document_role") == "standalone" and not has_parent_refs:
            # Re-run for standalone docs that might have child_references we missed
            if has_child_refs:
                continue

        text_sample = (c.extracted_text or "")[:10000]
        if not text_sample:
            continue

        no_refs_count += 1
        logger.info(f"  Extracting refs: {c.filename}")
        try:
            rel_prompt = (
                f"You are a contract relationship analyst. Read this contract carefully and answer:\n\n"
                f"1. Does this contract explicitly reference, amend, supplement, or attach to another agreement?\n"
                f"2. If yes, what is the exact name/type of that parent agreement?\n"
                f"3. Who are the parties in the referenced agreement?\n"
                f"4. What date was the referenced agreement signed/effective?\n\n"
                f"5. Does this contract mention any attached Exhibits, Schedules, Attachments, or Appendices?\n"
                f"   List ALL that are mentioned (e.g., 'Exhibit 1', 'Schedule A', 'Attachment 3-B').\n\n"
                f"Look for phrases like:\n"
                f"- 'pursuant to the Master Services Agreement...'\n"
                f"- 'This Amendment modifies the Agreement dated...'\n"
                f"- 'under the terms of the [Agreement Name]...'\n"
                f"- 'This Schedule is part of...'\n"
                f"- 'as referenced in the [Agreement] between...'\n"
                f"- 'The following Exhibits are attached hereto...'\n\n"
                f'Respond ONLY with JSON:\n'
                f'{{"is_child_document": true/false, "document_role": "amendment|schedule|exhibit|sow|standalone", '
                f'"parent_references": [{{"referenced_type": "MSA", "relationship": "parent|amends|renews", '
                f'"party_names": ["Company A", "Company B"], "referenced_date": "YYYY-MM-DD", '
                f'"reference_identifier": "Amendment No. 2", '
                f'"reference_text": "exact quote from document", "confidence": 0.9}}], '
                f'"child_references": ["Exhibit 1", "Exhibit 2", "Schedule A"], "overall_confidence": 0.9}}\n\n'
                f"If this is a standalone contract with attached exhibits/schedules, return:\n"
                f'{{"is_child_document": false, "document_role": "standalone", '
                f'"parent_references": [], "child_references": ["Exhibit 1", "Schedule A"], "overall_confidence": 0.9}}\n\n'
                f"Document filename: {c.filename}\n"
                f"---\n{text_sample}\n---"
            )
            resp = await orchestrator.route_request(
                AgentRequest(
                    query=rel_prompt,
                    user_id="system",
                    session_id=f"rel_extract_{c.id}",
                    contract_id=str(c.id),
                    context={"task": "contract_reference_extraction"},
                )
            )
            json_data = extract_json_from_response(resp.response)
            if json_data:
                has_parent = bool(json_data.get("parent_references"))
                has_child = bool(json_data.get("child_references"))
                if has_parent or has_child:
                    ref_result = _parse_reference_response(json_data)
                    if ref_result.parent_references or ref_result.child_references:
                        async with async_session_maker() as session:
                            result = await session.execute(
                                select(Contract).where(Contract.id == c.id)
                            )
                            contract = result.scalar_one()
                            await store_contract_references(session, contract, ref_result)
                            await session.commit()
                        refs_found_count += 1
                        logger.info(
                            f"    → Found {len(ref_result.parent_references)} parent refs, "
                            f"{len(ref_result.child_references)} child refs"
                        )
                    else:
                        logger.info(f"    → Standalone")
                else:
                    logger.info(f"    → Standalone")
            else:
                logger.info(f"    → Standalone (no JSON)")
        except Exception as e:
            logger.error(f"    Ref extraction failed: {e}")

    logger.info(f"Found refs for {refs_found_count}/{no_refs_count} contracts")

    # Step 5: Fix child documents — reclassify MSA→SOW and fix bad counterparties
    logger.info("=== Step 4: Fixing child document metadata ===")
    type_fixed = 0
    cp_fixed = 0

    async with async_session_maker() as session:
        result = await session.execute(
            select(Contract).where(Contract.status == ContractStatus.COMPLETED)
        )
        all_contracts = result.scalars().all()

        for c in all_contracts:
            refs = (c.schema_data or {}).get("_contract_references", {})
            is_child = refs.get("is_child_document", False)
            doc_role = refs.get("document_role", "")
            changed = False

            # Fix 1: Child documents classified as MSA → SOW
            if is_child and doc_role in ("exhibit", "attachment", "schedule", "appendix", "annex", "sow"):
                if c.contract_type and c.contract_type.value == "msa":
                    c.contract_type = ContractType.SOW
                    changed = True
                    type_fixed += 1
                    logger.info(f"  Type fix: {c.filename} MSA → SOW (role={doc_role})")

            # Fix 2: Counterparty = filename fallback → use parent reference parties
            if c.counterparty and c.filename:
                fname_base = c.filename.rsplit(".", 1)[0]
                cp = c.counterparty.strip()
                is_filename_fallback = (
                    cp == fname_base
                    or cp == c.filename
                    or (len(cp) > 40 and fname_base[:30] in cp)
                )
                if is_filename_fallback:
                    parent_refs = refs.get("parent_references", [])
                    for pref in parent_refs:
                        parties = pref.get("party_names", [])
                        for party in parties:
                            if party and len(party.strip()) >= 3 and party.strip().lower() not in (
                                "client", "vendor", "supplier", "company", "party",
                                "party a", "party b", "the company", "the client",
                            ):
                                c.counterparty = party.strip()
                                changed = True
                                cp_fixed += 1
                                logger.info(f"  CP fix: {c.filename} → '{party.strip()}'")
                                break
                        if changed:
                            break

        await session.commit()

    logger.info(f"Fixed {type_fixed} contract types, {cp_fixed} counterparties")

    # Step 6: Re-run auto-link detection for all contracts
    logger.info("=== Step 5: Running auto-link detection for all contracts ===")
    total_suggestions = 0

    # Reload contracts with updated data
    async with async_session_maker() as session:
        result = await session.execute(
            select(Contract).where(Contract.status == ContractStatus.COMPLETED)
        )
        contracts = result.scalars().all()

    for c in contracts:
        logger.info(f"  Auto-linking: {c.filename} (type={c.contract_type}, counterparty={c.counterparty})")
        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(Contract).where(Contract.id == c.id)
                )
                contract = result.scalar_one()

                detector = AutoLinkDetector(
                    db=session,
                    tenant_id=contract.tenant_id,
                )

                suggestions = await detector.detect_links(
                    contract=contract,
                    batch_contract_ids=[],
                    min_confidence=0.2,
                    max_suggestions=5,
                )

                if suggestions:
                    for s in suggestions:
                        session.add(s)
                    await session.commit()
                    total_suggestions += len(suggestions)
                    logger.info(f"    → {len(suggestions)} suggestions")
                else:
                    logger.info(f"    → No suggestions")
        except Exception as e:
            logger.error(f"    Auto-link failed: {e}")

    logger.info(f"=== DONE: Created {total_suggestions} total link suggestions ===")


if __name__ == "__main__":
    asyncio.run(main())

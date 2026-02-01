#!/usr/bin/env python3
"""Test clause and obligation extraction on a contract."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.parser import get_parser
from app.agents.clause_extraction import extract_clauses
from app.agents.obligation_tracking import extract_obligations


async def test_extraction():
    """Test extraction on the uploaded contract."""
    # Parse the document
    contract_path = "/Users/jjayaraj/workspaces/studios/clm/backend/storage/uploads/20260201_023003_c80ed737615a_Master-Service-Agreement-Feb-2023_v2.pdf"

    parser = get_parser()
    parsed = parser.parse_file(contract_path)

    if not parsed.success:
        print(f"Parse failed: {parsed.error}")
        return

    print(f"Parsed {len(parsed.full_text)} characters")
    print(f"First 500 chars: {parsed.full_text[:500]}")
    print("\n" + "="*50 + "\n")

    # Test clause extraction
    print("Running clause extraction...")
    try:
        clause_result = await extract_clauses(
            contract_text=parsed.full_text,
            contract_id="test",
            user_id="test",
        )
        print(f"Extracted {len(clause_result.extracted_clauses)} clauses")
        for clause in clause_result.extracted_clauses[:5]:
            print(f"  - {clause.clause_type}: {clause.text[:100]}...")
    except Exception as e:
        print(f"Clause extraction error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*50 + "\n")

    # Test obligation extraction
    print("Running obligation extraction...")
    try:
        obl_result = await extract_obligations(
            contract_text=parsed.full_text,
            contract_id="test",
            user_id="test",
        )
        print(f"Extracted {len(obl_result.obligations)} obligations")
        for obl in obl_result.obligations[:5]:
            print(f"  - {obl.obligation_type}: {obl.description[:100]}...")
    except Exception as e:
        print(f"Obligation extraction error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_extraction())

#!/usr/bin/env python3
"""
Upload Sample Contracts Script - Uploads real PDF contracts for AI processing.

This script uploads contracts from the sample_contracts folder and triggers
AI extraction for metadata, clauses, obligations, and SLAs.

Run with: python -m scripts.upload_sample_contracts
Or: cd backend && uv run python -m scripts.upload_sample_contracts

Prerequisites:
- Backend server must be running at http://localhost:8000
- Demo users must exist (run seed_demo.py first)
"""

import asyncio
import sys
from pathlib import Path
import httpx
import json

# Configuration
API_BASE = "http://localhost:8000"
SAMPLE_CONTRACTS_DIR = Path(__file__).parent.parent / "data" / "sample_contracts"
TEST_SCENARIOS_DIR = Path(__file__).parent.parent / "data" / "test-scenarios"

# Default credentials
DEFAULT_EMAIL = "admin@example.com"
DEFAULT_PASSWORD = "admin123"

# Contracts to upload (filename, client_code if applicable)
CONTRACTS_TO_UPLOAD = [
    # Test contracts (synthetic, good for demo)
    ("test_contracts/MSA_TechServices_Acme.pdf", "ACME"),
    ("test_contracts/NDA_TechServices_Acme.pdf", "ACME"),
    ("test_contracts/SLA_ITServices_Acme.pdf", "ACME"),
    ("test_contracts/SOW_InfraManagement_Acme.pdf", "ACME"),
    ("test_contracts/Amendment_001_MSA_TechServices.pdf", "ACME"),

    # Real public domain contracts (various types)
    ("MSA_GlobalSign.pdf", None),
    ("MSA_MercyCorps_Template.pdf", None),
    ("NDA_NYU_Stern.pdf", None),
    ("SLA_PMI_Agreement.pdf", None),
    ("SOW_SDLC_Template.pdf", None),
    ("Vendor_Agreement_Pace_University.pdf", None),
]


async def get_auth_token(client: httpx.AsyncClient) -> str:
    """Get authentication token."""
    print(f"Authenticating as {DEFAULT_EMAIL}...")

    response = await client.post(
        f"{API_BASE}/api/auth/login",
        json={"username": "admin", "password": DEFAULT_PASSWORD}
    )

    if response.status_code != 200:
        print(f"  Authentication failed: {response.text}")
        raise Exception("Failed to authenticate. Make sure you've run seed_demo.py first.")

    token = response.json()["access_token"]
    print("  Authenticated successfully")
    return token


async def get_clients(client: httpx.AsyncClient, headers: dict) -> dict:
    """Get client mapping from API."""
    response = await client.get(f"{API_BASE}/api/clients", headers=headers)
    if response.status_code == 200:
        clients = response.json().get("clients", [])
        return {c["code"]: c["id"] for c in clients}
    return {}


async def upload_contract(
    client: httpx.AsyncClient,
    headers: dict,
    file_path: Path,
    client_id: str = None
) -> dict:
    """Upload a single contract."""
    if not file_path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/pdf")}
        data = {}
        if client_id:
            data["client_id"] = client_id

        response = await client.post(
            f"{API_BASE}/api/contracts/upload",
            headers=headers,
            files=files,
            data=data,
            timeout=120.0  # 2 minute timeout for large files
        )

    if response.status_code in [200, 201]:
        result = response.json()
        return {"success": True, "contract_id": result.get("id"), "filename": file_path.name}
    else:
        return {"success": False, "error": response.text, "filename": file_path.name}


async def check_contract_status(
    client: httpx.AsyncClient,
    headers: dict,
    contract_id: str
) -> str:
    """Check the processing status of a contract."""
    response = await client.get(f"{API_BASE}/api/contracts/{contract_id}", headers=headers)
    if response.status_code == 200:
        return response.json().get("status", "unknown")
    return "error"


async def wait_for_processing(
    client: httpx.AsyncClient,
    headers: dict,
    contract_id: str,
    filename: str,
    timeout: int = 300
) -> bool:
    """Wait for contract processing to complete."""
    import time
    start_time = time.time()

    while time.time() - start_time < timeout:
        status = await check_contract_status(client, headers, contract_id)

        if status == "completed":
            return True
        elif status == "failed":
            print(f"    Processing failed for {filename}")
            return False
        elif status in ["pending", "processing"]:
            await asyncio.sleep(5)  # Check every 5 seconds
        else:
            print(f"    Unknown status '{status}' for {filename}")
            return False

    print(f"    Timeout waiting for {filename}")
    return False


async def main():
    """Main upload function."""
    print("=" * 60)
    print("Sample Contract Upload Script")
    print("=" * 60)
    print(f"\nAPI: {API_BASE}")
    print(f"Source: {SAMPLE_CONTRACTS_DIR}")

    async with httpx.AsyncClient() as client:
        # Authenticate
        try:
            token = await get_auth_token(client)
        except Exception as e:
            print(f"\nError: {e}")
            return

        headers = {"Authorization": f"Bearer {token}"}

        # Get client mapping
        print("\nFetching clients...")
        clients = await get_clients(client, headers)
        print(f"  Found {len(clients)} clients")

        # Upload contracts
        print("\nUploading contracts...")
        results = []
        uploaded_ids = []

        for filename, client_code in CONTRACTS_TO_UPLOAD:
            file_path = SAMPLE_CONTRACTS_DIR / filename

            # Get client ID if specified
            client_id = clients.get(client_code) if client_code else None

            print(f"\n  Uploading: {filename}")
            if client_code:
                print(f"    Client: {client_code}")

            result = await upload_contract(client, headers, file_path, client_id)
            results.append(result)

            if result["success"]:
                print(f"    Uploaded: {result['contract_id']}")
                uploaded_ids.append((result["contract_id"], filename))
            else:
                print(f"    Failed: {result.get('error', 'Unknown error')[:100]}")

        # Wait for processing (optional)
        print("\n" + "-" * 60)
        print("Waiting for AI processing to complete...")
        print("(This may take several minutes for large contracts)")
        print("-" * 60)

        completed = 0
        for contract_id, filename in uploaded_ids:
            print(f"\n  Processing: {filename}...")
            if await wait_for_processing(client, headers, contract_id, filename):
                print(f"    Completed: {filename}")
                completed += 1

        # Summary
        print("\n" + "=" * 60)
        print("Upload Summary")
        print("=" * 60)
        successful = sum(1 for r in results if r["success"])
        print(f"  Total files:     {len(CONTRACTS_TO_UPLOAD)}")
        print(f"  Uploaded:        {successful}")
        print(f"  AI Processed:    {completed}")
        print(f"  Failed:          {len(CONTRACTS_TO_UPLOAD) - successful}")

        if successful > 0:
            print(f"\nView contracts at: http://localhost:3000/contracts")


if __name__ == "__main__":
    asyncio.run(main())

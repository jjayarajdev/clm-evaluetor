# 02 - Metadata Extraction Testing

## Purpose
Test AI-powered extraction of contract metadata including parties, dates, values, and key terms.

## Documents
| File | Type | Key Metadata |
|------|------|--------------|
| `MSA_TechServices_Acme.pdf` | MSA | Parties, dates, $4.5M value, auto-renewal |
| `SOW_InfraManagement_Acme.pdf` | SOW | Reference contract, $2.09M value, milestones |

## Functionality Tested
- Party extraction (provider, counterparty)
- Date extraction (effective, expiration)
- Value extraction (contract value, currency)
- Term extraction (duration, renewal terms)
- Contract type classification

## Test Workflow

### 1. Upload Contracts
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}' | jq -r '.access_token')

# Upload MSA
curl -X POST http://localhost:8000/api/contracts/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@MSA_TechServices_Acme.pdf"

# Upload SOW
curl -X POST http://localhost:8000/api/contracts/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@SOW_InfraManagement_Acme.pdf"
```

### 2. Wait for Processing
```bash
# Check status (wait for 'processed')
curl http://localhost:8000/api/contracts/{contract_id} \
  -H "Authorization: Bearer $TOKEN"
```

### 3. View Extracted Metadata
```bash
# Get cockpit view with extracted data
curl http://localhost:8000/api/dashboard/cockpit/{contract_id} \
  -H "Authorization: Bearer $TOKEN"
```

## Expected Extraction Results

### MSA_TechServices_Acme.pdf
| Field | Expected Value |
|-------|----------------|
| Contract Type | MSA |
| Provider | TechServices Global Inc. |
| Counterparty | Acme Corporation |
| Contract Number | MSA-2024-001 |
| Effective Date | 2024-01-01 |
| Expiration Date | 2026-12-31 |
| Contract Value | 4,500,000 |
| Currency | USD |
| Monthly Fee | 125,000 |
| Auto-Renewal | Yes |
| Notice Period | 90 days |

### SOW_InfraManagement_Acme.pdf
| Field | Expected Value |
|-------|----------------|
| Contract Type | SOW |
| Reference Contract | MSA-2024-001 |
| SOW Number | SOW-2024-001 |
| Effective Date | 2024-01-15 |
| End Date | 2025-01-14 |
| Total Value | 2,090,000 |
| Monthly Fee | 125,000 |
| Project Fees | 400,000 |

## Success Criteria
- [ ] Contract type correctly identified
- [ ] Both parties extracted
- [ ] Dates parsed correctly
- [ ] Monetary values extracted with correct currency
- [ ] Auto-renewal terms identified

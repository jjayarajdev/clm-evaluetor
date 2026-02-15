# 06 - Contract Linking Testing

## Purpose
Test parent-child contract relationships including MSA-SOW hierarchies and amendments.

## Documents
| File | Type | Relationship |
|------|------|--------------|
| `NDA_TechServices_Acme.pdf` | NDA | Standalone (precedes MSA) |
| `MSA_TechServices_Acme.pdf` | MSA | Parent contract |
| `SOW_InfraManagement_Acme.pdf` | SOW | Child of MSA |
| `Amendment_001_MSA_TechServices.pdf` | Amendment | Amends MSA |

## Hierarchy Structure
```
NDA_TechServices_Acme (standalone)
    |
MSA_TechServices_Acme (MSA-2024-001)
    |
    +-- SOW_InfraManagement_Acme (SOW-2024-001)
    |
    +-- Amendment_001 (AMD-2024-001)
```

## Functionality Tested
- Contract reference detection
- Parent-child link creation
- Amendment tracking
- Hierarchy visualization
- Cascading status updates
- Term inheritance

## Test Workflow

### 1. Upload All Contracts
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}' | jq -r '.access_token')

# Upload in order
for file in NDA_TechServices_Acme.pdf MSA_TechServices_Acme.pdf SOW_InfraManagement_Acme.pdf Amendment_001_MSA_TechServices.pdf; do
  curl -X POST http://localhost:8000/api/contracts/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$file"
  sleep 2
done
```

### 2. Create Contract Links
```bash
# Link SOW to MSA (get IDs from upload responses)
curl -X POST http://localhost:8000/api/contracts/{msa_id}/links \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "child_contract_id": "{sow_id}",
    "link_type": "sow"
  }'

# Link Amendment to MSA
curl -X POST http://localhost:8000/api/contracts/{msa_id}/links \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "child_contract_id": "{amendment_id}",
    "link_type": "amendment"
  }'
```

### 3. View Contract Hierarchy
```bash
# Get contract with linked documents
curl http://localhost:8000/api/contracts/{msa_id}?include_links=true \
  -H "Authorization: Bearer $TOKEN"
```

### 4. View Contract Family Tree
```bash
curl http://localhost:8000/api/contracts/{msa_id}/hierarchy \
  -H "Authorization: Bearer $TOKEN"
```

## Link Types
| Type | Description | Example |
|------|-------------|---------|
| `sow` | Statement of Work under MSA | MSA -> SOW |
| `amendment` | Contract modification | MSA -> Amendment |
| `addendum` | Additional terms | MSA -> Addendum |
| `renewal` | Contract renewal | MSA v1 -> MSA v2 |
| `nda` | Related NDA | NDA -> MSA |

## Expected Amendment Changes (AMD-2024-001)
| Field | Original (MSA) | Amended |
|-------|----------------|---------|
| Monthly Fee | $125,000 | $275,000 |
| Contract Value | $4,500,000 | $8,250,000 |
| Expiration | 2026-12-31 | 2027-12-31 |
| Services | IT Infrastructure | + SOC, DevOps, Analytics |
| Service Credits | 30% max | 40% max |

## Success Criteria
- [ ] Contracts uploaded successfully
- [ ] Links created between contracts
- [ ] Hierarchy correctly displayed
- [ ] Amendment changes tracked
- [ ] Reference numbers (MSA-2024-001) detected

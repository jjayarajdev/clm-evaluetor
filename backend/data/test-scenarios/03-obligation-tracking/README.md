# 03 - Obligation Tracking Testing

## Purpose
Test extraction and tracking of contractual obligations with responsible parties and deadlines.

## Documents
| File | Type | Key Obligations |
|------|------|-----------------|
| `MSA_MercyCorps_Template.pdf` | MSA | Payment terms, deliverables, reporting |
| `Vendor_Agreement_Pace_University.pdf` | Vendor | Insurance requirements, compliance, procurement |

## Functionality Tested
- Obligation extraction from contract text
- Assignment of responsible party (provider/customer)
- Deadline/frequency extraction
- Obligation status tracking
- Alert generation for upcoming deadlines

## Test Workflow

### 1. Upload Contracts
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}' | jq -r '.access_token')

curl -X POST http://localhost:8000/api/contracts/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@MSA_MercyCorps_Template.pdf"
```

### 2. View Extracted Obligations
```bash
# Get obligations for contract
curl http://localhost:8000/api/contracts/{contract_id}/obligations \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Update Obligation Status
```bash
# Mark obligation as completed
curl -X PATCH http://localhost:8000/api/obligations/{obligation_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "completed", "completion_date": "2024-02-15"}'
```

### 4. Check Dashboard Alerts
```bash
curl http://localhost:8000/api/dashboard/alerts \
  -H "Authorization: Bearer $TOKEN"
```

## Expected Obligations

### MSA_MercyCorps_Template.pdf
| Obligation | Owner | Frequency | Deadline Type |
|------------|-------|-----------|---------------|
| Invoice submission | Provider | Monthly | Recurring |
| Payment processing | Customer | Net 30 | After invoice |
| Progress reports | Provider | Monthly | Recurring |
| Deliverable acceptance | Customer | Per deliverable | 10 days |
| Insurance certificate | Provider | Annual | Recurring |

### Vendor_Agreement_Pace_University.pdf
| Obligation | Owner | Frequency | Deadline Type |
|------------|-------|-----------|---------------|
| Liability insurance ($1M) | Provider | Annual | Maintain |
| Background checks | Provider | Per employee | Before start |
| Compliance certifications | Provider | Annual | Recurring |
| Indemnification notice | Both | On event | 30 days |

## Success Criteria
- [ ] Obligations extracted from contract text
- [ ] Responsible party correctly assigned
- [ ] Deadlines/frequencies identified
- [ ] Status tracking works (pending -> completed)
- [ ] Alerts generated for upcoming deadlines

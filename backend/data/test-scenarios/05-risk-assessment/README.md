# 05 - Risk Assessment Testing

## Purpose
Test AI-powered identification and scoring of contractual risks.

## Documents
| File | Type | Key Risk Areas |
|------|------|----------------|
| `MSA_GlobalSign.pdf` | MSA | Liability caps, indemnification, auto-renewal, termination |
| `NDA_OJP_Gov.pdf` | NDA | Government compliance, survival clauses, breach penalties |

## Functionality Tested
- Risk clause identification
- Risk category classification
- Risk severity scoring
- Mitigation recommendations
- Risk dashboard aggregation

## Risk Categories Analyzed
1. **Financial Risk** - Liability caps, penalties, uncapped obligations
2. **Termination Risk** - Notice periods, termination for convenience, survival
3. **Compliance Risk** - Regulatory requirements, audit rights
4. **IP Risk** - Ownership, licensing, confidentiality
5. **Operational Risk** - Service dependencies, change control

## Test Workflow

### 1. Upload Contracts
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}' | jq -r '.access_token')

curl -X POST http://localhost:8000/api/contracts/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@MSA_GlobalSign.pdf"
```

### 2. View Risk Assessment
```bash
# Get risks for contract
curl http://localhost:8000/api/contracts/{contract_id}/risks \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Check Risk Dashboard
```bash
# Portfolio risk summary
curl http://localhost:8000/api/dashboard/risk-summary \
  -H "Authorization: Bearer $TOKEN"
```

## Expected Risk Findings

### MSA_GlobalSign.pdf
| Risk | Category | Severity | Description |
|------|----------|----------|-------------|
| Liability Cap | Financial | Medium | Cap at 2x annual fees |
| Auto-Renewal | Termination | Low | 1-year auto-renewal periods |
| 90-Day Notice | Termination | Low | Long notice period required |
| Indemnification | Financial | High | Broad indemnification scope |
| IP Assignment | IP | Medium | Work product assignment clause |

### NDA_OJP_Gov.pdf
| Risk | Category | Severity | Description |
|------|----------|----------|-------------|
| Government Compliance | Compliance | High | Federal compliance requirements |
| 5-Year Survival | Termination | Medium | Extended post-term obligations |
| Breach Notification | Operational | Medium | Strict notification requirements |
| Audit Rights | Compliance | Low | Government audit provisions |

## Risk Scoring Matrix
| Severity | Score | Action Required |
|----------|-------|-----------------|
| Critical | 9-10 | Immediate escalation |
| High | 7-8 | Review before signing |
| Medium | 4-6 | Note for negotiation |
| Low | 1-3 | Acceptable |

## Success Criteria
- [ ] Risk clauses identified in contract
- [ ] Categories correctly assigned
- [ ] Severity scores reasonable
- [ ] Mitigation suggestions provided
- [ ] Dashboard shows portfolio risk summary

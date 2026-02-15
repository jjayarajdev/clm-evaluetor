# 09 - Enterprise Suite Testing

## Purpose
Test handling of complex enterprise contracts with multiple exhibits, attachments, and cross-references.

## Documents
| File | Type | Description |
|------|------|-------------|
| `MSA_Main_Agreement.docx` | MSA | Master agreement (~75 pages) |
| `Exhibit_1_Definitions.docx` | Exhibit | Contract definitions glossary |
| `Exhibit_2_SOW.docx` | Exhibit | Statement of work (~100+ pages) |
| `Exhibit_4_Pricing.docx` | Exhibit | Pricing model and rates |
| `Exhibit_5_HR.docx` | Exhibit | Human resource provisions |

## Full Contract Suite (ing_anonymized/)
This enterprise contract includes 97 documents:
- Main MSA
- 35+ Exhibits (SOW, Governance, Service Levels, Pricing, etc.)
- 60+ Attachments (detailed schedules, matrices, templates)

## Functionality Tested
- Large document processing
- Multi-document upload
- Cross-reference linking
- Exhibit/attachment hierarchy
- Complex SLA extraction
- Governance structure parsing
- Pricing model extraction

## Test Workflow

### 1. Upload Main Agreement
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}' | jq -r '.access_token')

# Upload MSA first
curl -X POST http://localhost:8000/api/contracts/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@MSA_Main_Agreement.docx"
```

### 2. Upload Supporting Exhibits
```bash
# Upload exhibits (link to MSA after)
for file in Exhibit_*.docx; do
  curl -X POST http://localhost:8000/api/contracts/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$file" \
    -F "parent_id={msa_id}"
  sleep 2
done
```

### 3. Link Exhibits to MSA
```bash
# Link each exhibit
curl -X POST http://localhost:8000/api/contracts/{msa_id}/links \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "child_contract_id": "{exhibit_id}",
    "link_type": "exhibit"
  }'
```

### 4. View Complete Contract Package
```bash
curl http://localhost:8000/api/contracts/{msa_id}/package \
  -H "Authorization: Bearer $TOKEN"
```

### 5. Search Across Package
```bash
# Search within contract family
curl "http://localhost:8000/api/contracts/{msa_id}/search?q=service+levels" \
  -H "Authorization: Bearer $TOKEN"
```

## Key Exhibits in Full Suite
| Exhibit | Content | Key Data |
|---------|---------|----------|
| Exhibit 1 | Definitions | 100+ defined terms |
| Exhibit 2.x | SOW by service | Service descriptions |
| Exhibit 3 | Service Levels | SLA metrics |
| Exhibit 4 | Pricing | Rate cards, baselines |
| Exhibit 5 | HR Provisions | Transfer terms |
| Exhibit 6 | Governance | Meeting cadence, escalation |
| Exhibit 30 | Transition | Migration plan |

## Complexity Handling
| Challenge | Expected Behavior |
|-----------|------------------|
| Large files (1MB+) | Async processing |
| Cross-references | Detected and linked |
| Defined terms | Parsed from Exhibit 1 |
| Version numbers | Tracked in metadata |
| Multiple formats | .docx and .xlsx supported |

## Performance Expectations
| Metric | Target |
|--------|--------|
| Upload time (per file) | < 5 seconds |
| Processing time (large doc) | < 60 seconds |
| Search response | < 2 seconds |
| Hierarchy load | < 3 seconds |

## Success Criteria
- [ ] All documents upload successfully
- [ ] Processing completes without timeout
- [ ] Exhibits linked to MSA
- [ ] Cross-references detected
- [ ] Search works across package
- [ ] Hierarchy displays correctly
- [ ] No memory errors on large docs

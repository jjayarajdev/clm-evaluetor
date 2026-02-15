# CLM Test Scenarios

This folder contains organized test data for validating all CLM system functionalities.

## Folder Structure

| Folder | Functionality | Documents |
|--------|---------------|-----------|
| [01-contract-upload](./01-contract-upload/) | Basic upload & parsing | 1 PDF |
| [02-metadata-extraction](./02-metadata-extraction/) | AI metadata extraction | 2 PDFs |
| [03-obligation-tracking](./03-obligation-tracking/) | Obligation management | 2 PDFs |
| [04-sla-management](./04-sla-management/) | SLA comparison & credits | 3 PDFs |
| [05-risk-assessment](./05-risk-assessment/) | Risk identification | 2 PDFs |
| [06-contract-linking](./06-contract-linking/) | Parent/child hierarchy | 4 PDFs |
| [07-milestone-tracking](./07-milestone-tracking/) | Deliverable tracking | 2 PDFs |
| [08-relationship-governance](./08-relationship-governance/) | KPIs & perception scoring | 4 DOCX/XLSX |
| [09-enterprise-suite](./09-enterprise-suite/) | Complex multi-doc contracts | 5 DOCX |

## Quick Start

### 1. Start the Backend
```bash
cd backend
uv run uvicorn app.main:app --reload
```

### 2. Get Auth Token
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}' | jq -r '.access_token')
```

### 3. Run Test Scenario
```bash
# Navigate to test scenario
cd data/test-scenarios/01-contract-upload

# Follow the README.md instructions
cat README.md
```

## Testing Order (Recommended)

1. **01-contract-upload** - Verify basic upload works
2. **02-metadata-extraction** - Test AI extraction
3. **05-risk-assessment** - Verify risk scoring
4. **04-sla-management** - Test SLA comparison (seed master data first)
5. **03-obligation-tracking** - Test obligation extraction
6. **07-milestone-tracking** - Test milestone extraction
7. **06-contract-linking** - Test contract hierarchy
8. **08-relationship-governance** - Test Evaluetor features
9. **09-enterprise-suite** - Stress test with complex docs

## Document Sources

| Source | Documents |
|--------|-----------|
| `sample_contracts/` | Public domain PDFs (MSAs, NDAs, SLAs) |
| `sample_contracts/test_contracts/` | Synthetic test contracts (TechServices/Acme) |
| `sample_contracts/ing_anonymized/` | Enterprise contract suite (97 documents) |

## API Endpoints Reference

| Category | Endpoints |
|----------|-----------|
| **Contracts** | `POST /api/contracts/upload`, `GET /api/contracts/{id}` |
| **Metadata** | `GET /api/dashboard/cockpit/{id}` |
| **Obligations** | `GET /api/contracts/{id}/obligations` |
| **SLAs** | `GET /api/contracts/{id}/sla-comparison` |
| **Risks** | `GET /api/contracts/{id}/risks` |
| **Links** | `POST /api/contracts/{id}/links` |
| **Milestones** | `GET /api/contracts/{id}/milestones` |
| **Relationships** | `GET /api/relationships`, `GET /api/relationships/{id}/kpis` |
| **Surveys** | `GET /api/surveys/templates`, `POST /api/surveys/instances` |

## Success Criteria Checklist

- [ ] All 9 test scenarios pass
- [ ] No timeout errors on large documents
- [ ] AI extraction returns reasonable results
- [ ] SLA comparison matches master data
- [ ] Contract hierarchy displays correctly
- [ ] Perception gaps calculate properly
- [ ] Survey distribution works

## Troubleshooting

### Upload Fails
- Check file size (max 50MB)
- Verify file is valid PDF/DOCX
- Check backend logs: `docker-compose logs backend`

### Extraction Empty
- Verify document is text-based (not scanned image)
- Check OpenAI API key is set
- Review agent logs for errors

### SLA Comparison Empty
- Run `POST /api/admin/master-data/seed-all` first
- Verify SLA codes match master data entries
- Check scheduler is running

---
*Generated: 2026-02-14*

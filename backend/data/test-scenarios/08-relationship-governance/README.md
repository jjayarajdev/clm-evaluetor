# 08 - Relationship Governance Testing

## Purpose
Test Evaluetor-style relationship governance features including KPI tracking, perception scoring, and stakeholder surveys.

## Documents
| File | Type | Purpose |
|------|------|---------|
| `Exhibit_6_Governance.docx` | Governance | Governance structure, meeting cadence, escalation |
| `Exhibit_3_Service_Levels.docx` | SLA | Service level definitions and metrics |
| `Attachment_14A_Survey.docx` | Survey | Point of service survey template |
| `Attachment_3A_SLA_Matrix.xlsx` | Matrix | Service level matrix with targets |

## Functionality Tested
- Business relationship management
- KPI definition and tracking
- Perception score collection (internal/external)
- Gap analysis (internal vs external perception)
- Improvement point tracking
- Survey template creation and distribution
- Governance tier assignment

## Test Workflow

### 1. Create Organizations
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}' | jq -r '.access_token')

# Organizations should be seeded already
curl http://localhost:8000/api/organizations \
  -H "Authorization: Bearer $TOKEN"
```

### 2. View Business Relationships
```bash
curl http://localhost:8000/api/relationships \
  -H "Authorization: Bearer $TOKEN"
```

### 3. View KPIs for Relationship
```bash
curl http://localhost:8000/api/relationships/{relationship_id}/kpis \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Submit Perception Scores
```bash
# Submit internal perception score
curl -X POST http://localhost:8000/api/kpis/{kpi_id}/scores \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "score": 8.5,
    "period": "2024-Q1",
    "is_internal": true,
    "comments": "Good performance overall"
  }'

# Submit external perception score
curl -X POST http://localhost:8000/api/kpis/{kpi_id}/scores \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "score": 7.0,
    "period": "2024-Q1",
    "is_internal": false,
    "comments": "Some communication delays"
  }'
```

### 5. Calculate Perception Gaps
```bash
curl -X POST http://localhost:8000/api/relationships/{relationship_id}/calculate-gaps \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"period": "2024-Q1"}'
```

### 6. View Gap Analysis
```bash
curl http://localhost:8000/api/relationships/{relationship_id}/gaps \
  -H "Authorization: Bearer $TOKEN"
```

### 7. Create Improvement Points
```bash
curl -X POST http://localhost:8000/api/relationships/{relationship_id}/improvements \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Improve communication response times",
    "description": "External perception lower than internal - gap of 1.5 points",
    "kpi_id": "{kpi_id}",
    "priority": "high",
    "target_date": "2024-06-30"
  }'
```

## KPI Categories
| Category | Example KPIs |
|----------|--------------|
| Service Delivery | On-time delivery, quality score |
| Communication | Response time, proactive updates |
| Quality | Defect rate, rework percentage |
| Innovation | New ideas proposed, improvements |
| Cost Efficiency | Budget adherence, value delivered |
| Compliance | Audit findings, policy adherence |

## Governance Tiers
| Tier | Review Frequency | Attendees |
|------|------------------|-----------|
| Operational | Weekly | Working team |
| Tactical | Monthly | Managers |
| Strategic | Quarterly | Directors |
| Executive | Annual | C-level |

## Gap Severity Classification
| Gap | Severity | Action |
|-----|----------|--------|
| < 1 point | Minor | Monitor |
| 1-2 points | Moderate | Address in review |
| 2-3 points | Significant | Improvement plan |
| > 3 points | Critical | Immediate action |

## Success Criteria
- [ ] Organizations and relationships visible
- [ ] KPIs defined for relationship
- [ ] Perception scores submitted (internal + external)
- [ ] Gaps calculated correctly
- [ ] Improvement points created and tracked
- [ ] Survey templates work

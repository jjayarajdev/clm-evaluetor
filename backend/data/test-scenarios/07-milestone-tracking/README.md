# 07 - Milestone Tracking Testing

## Purpose
Test extraction and tracking of project milestones, deliverables, and payment schedules.

## Documents
| File | Type | Key Milestones |
|------|------|----------------|
| `SOW_SDLC_Template.pdf` | SOW | Project phases, deliverables, timeline |
| `SOW_InfraManagement_Acme.pdf` | SOW | 9 milestones with credits at risk |

## Functionality Tested
- Milestone extraction from SOW
- Deliverable identification
- Timeline/date extraction
- Credit-at-risk tracking
- Milestone status updates
- Progress reporting

## Test Workflow

### 1. Upload SOW
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}' | jq -r '.access_token')

curl -X POST http://localhost:8000/api/contracts/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@SOW_InfraManagement_Acme.pdf"
```

### 2. View Extracted Milestones
```bash
curl http://localhost:8000/api/contracts/{contract_id}/milestones \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Update Milestone Status
```bash
# Mark milestone as completed
curl -X PATCH http://localhost:8000/api/milestones/{milestone_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed",
    "actual_date": "2024-02-25",
    "notes": "Assessment delivered and accepted"
  }'
```

### 4. View Milestone Dashboard
```bash
curl http://localhost:8000/api/dashboard/milestones \
  -H "Authorization: Bearer $TOKEN"
```

## Expected Milestones (SOW_InfraManagement_Acme.pdf)

| ID | Name | Target Date | Credit at Risk | Phase |
|----|------|-------------|----------------|-------|
| MS-1.1 | Kick-off Meeting | Jan 22, 2024 | - | Initiation |
| MS-1.2 | Project Plan Approved | Jan 31, 2024 | - | Initiation |
| MS-2.1 | Assessment Complete | Feb 28, 2024 | $25,000 | Assessment |
| MS-2.2 | Migration Plan Approved | Mar 15, 2024 | $50,000 | Assessment |
| MS-3.1 | Phase 1 (25%) | Apr 30, 2024 | $75,000 | Migration |
| MS-3.2 | Phase 2 (50%) | Jun 30, 2024 | $100,000 | Migration |
| MS-3.3 | Phase 3 (75%) | Sep 30, 2024 | $125,000 | Migration |
| MS-4.0 | Migration Complete (80%) | Nov 30, 2024 | $150,000 | Completion |
| MS-5.0 | Stabilization Complete | Jan 14, 2025 | - | Closeout |

## Milestone Statuses
| Status | Description |
|--------|-------------|
| `pending` | Not yet started |
| `in_progress` | Work underway |
| `completed` | Delivered and accepted |
| `delayed` | Past target date |
| `at_risk` | May miss deadline |
| `cancelled` | No longer required |

## Deliverables by Phase
| Phase | Deliverables |
|-------|--------------|
| Assessment | Current state report, migration plan |
| Migration | Server migrations (batches), testing reports |
| Completion | UAT sign-off, operational handover |
| Closeout | Final documentation, lessons learned |

## Success Criteria
- [ ] Milestones extracted from SOW
- [ ] Target dates parsed correctly
- [ ] Credit-at-risk values captured
- [ ] Status updates work correctly
- [ ] Dashboard shows upcoming milestones
- [ ] Alerts generated for at-risk milestones

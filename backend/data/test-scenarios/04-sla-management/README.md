# 04 - SLA Management Testing

## Purpose
Test SLA extraction, comparison against master data, and service credit/penalty calculations.

## Documents
| File | Type | Key SLAs |
|------|------|----------|
| `SLA_ITServices_Acme.pdf` | SLA | 50+ metrics with codes, maps to master data |
| `SLA_Ohio_Gov_Performance.pdf` | SLA | Performance metrics, earn-back, 10-20% penalties |
| `SLA_PMI_Agreement.pdf` | SLA | Severity codes, financial penalties, service credits |

## Functionality Tested
- SLA metric extraction
- SLA code matching to master data
- Comparison against standard benchmarks
- Service credit calculation
- Penalty identification
- Gap analysis (contracted vs standard)

## Test Workflow

### 1. Seed Master Data First
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}' | jq -r '.access_token')

# Seed SLA master data
curl -X POST http://localhost:8000/api/admin/master-data/seed-all \
  -H "Authorization: Bearer $TOKEN"
```

### 2. Upload SLA Documents
```bash
curl -X POST http://localhost:8000/api/contracts/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@SLA_ITServices_Acme.pdf"
```

### 3. Trigger SLA Comparison
```bash
# Run SLA comparison job
curl -X POST http://localhost:8000/api/admin/scheduler/jobs/sla_comparison/run \
  -H "Authorization: Bearer $TOKEN"
```

### 4. View Comparison Results
```bash
# Get SLA comparison for contract
curl http://localhost:8000/api/contracts/{contract_id}/sla-comparison \
  -H "Authorization: Bearer $TOKEN"
```

## Expected SLA Metrics

### SLA_ITServices_Acme.pdf
| SLA Code | Description | Target | Standard | Gap |
|----------|-------------|--------|----------|-----|
| 12.1 | Core Business Apps | 99.95% | 99.9% | +0.05% |
| 12.2 | Database Services | 99.95% | 99.9% | +0.05% |
| 2.1.1 | Network Core | 99.99% | 99.9% | +0.09% |
| 2.1.2 | WAN Connectivity | 99.9% | 99.5% | +0.4% |
| 4.1.1 | P1 Response Time | 10 min | 15 min | Better |
| 5.1.3 | First Call Resolution | 75% | 70% | +5% |
| 5.2.1 | Change Success Rate | 98% | 95% | +3% |
| 6.2.1 | Critical Patch Deploy | 24 hrs | 48 hrs | Better |

### Service Credit Structure
| SLA Category | Miss Threshold | Credit % |
|--------------|----------------|----------|
| Availability | < 99.9% | 5% |
| Availability | < 99.5% | 10% |
| Availability | < 99.0% | 20% |
| Response Time | > 150% target | 5% |
| Resolution | > 200% target | 10% |
| **Maximum Credit** | | **30%** |

## Success Criteria
- [ ] SLA metrics extracted with codes
- [ ] Codes matched to master data entries
- [ ] Comparison shows gaps (better/worse than standard)
- [ ] Service credits calculated correctly
- [ ] Penalty thresholds identified

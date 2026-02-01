# Sample Contracts for Testing

These public domain contracts are used to test post-signing contract management features.

## Contract Inventory

| File | Type | Pages | Key Features to Test |
|------|------|-------|---------------------|
| **MSA_GlobalSign.pdf** | MSA | 18 | Liability caps, indemnification, auto-renewal, termination |
| **MSA_MercyCorps_Template.pdf** | MSA | 11 | Payment terms, deliverables, obligations, amendments |
| **NDA_NYU_Stern.pdf** | NDA | 2 | Confidentiality term (2 years), expiration, definitions |
| **NDA_OJP_Gov.pdf** | NDA | 4 | Government NDA, survival clauses, compliance obligations |
| **SLA_Northwestern_IT.pdf** | SLA | - | IT services, support tiers, response times, escalation |
| **SLA_Ohio_Gov_Performance.pdf** | SLA | 7 | Performance metrics, earn-back, penalties (10-20%) |
| **SLA_PMI_Agreement.pdf** | SLA | 10 | Severity codes, financial penalties, service credits |
| **SLA_Sana_Labs.pdf** | SLA | 7 | Uptime SLA, service credits, unavailability definitions |
| **SLA_UKZN_Template.pdf** | SLA | - | Formal legal SLA, schedules, annual review |
| **SLA_UptimeRobot_Template.pdf** | SLA | 3 | Priority response times (High/Medium/Low), metrics |
| **SOW_SDLC_Template.pdf** | SOW | - | Project scope, milestones, deliverables, timeline |
| **Vendor_Agreement_Pace_University.pdf** | Vendor | 7 | Insurance requirements, indemnification, procurement |

## Feature Coverage Matrix

| Feature | Contracts |
|---------|-----------|
| **Obligations** | MSA_MercyCorps, Vendor_Agreement_Pace, SLA_PMI |
| **SLA Terms** | SLA_* (all 6 SLA contracts) |
| **Penalties/Service Credits** | SLA_Ohio_Gov, SLA_PMI, SLA_Sana_Labs |
| **Auto-Renewal** | MSA_GlobalSign, SLA_Northwestern_IT |
| **Termination Clauses** | MSA_GlobalSign, MSA_MercyCorps, Vendor_Agreement_Pace |
| **Confidentiality/NDA** | NDA_NYU_Stern, NDA_OJP_Gov |
| **Indemnification** | MSA_GlobalSign, Vendor_Agreement_Pace |
| **Performance Metrics** | SLA_Ohio_Gov, SLA_PMI, SLA_UptimeRobot |
| **Milestones/Deliverables** | SOW_SDLC, MSA_MercyCorps |
| **Payment Terms** | MSA_MercyCorps, Vendor_Agreement_Pace |

## Sources

All contracts are from public domain sources:

- **Mercy Corps** - Nonprofit MSA template
- **GlobalSign** - Public repository MSA
- **NYU Stern** - Educational NDA sample
- **OJP.gov** - US Government NDA
- **Northwestern IT** - University IT SLA
- **Ohio State** - Government contract performance guide
- **PMI** - Project Management Institute SLA
- **Sana Labs** - SaaS SLA (public legal docs)
- **UKZN** - University of KwaZulu-Natal legal template
- **UptimeRobot** - Monitoring service SLA template
- **SDLC Forms** - SOW/SLA project template
- **Pace University** - Procurement vendor agreement

## Usage

Upload these contracts via the API to populate test data:

```bash
# Upload all sample contracts
for f in /path/to/sample_contracts/*.pdf; do
  curl -X POST "http://localhost:8000/api/contracts/upload" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$f"
done
```

Or use the batch upload endpoint with a ZIP file.

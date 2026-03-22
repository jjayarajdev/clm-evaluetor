# Test Contracts for CLM System

This folder contains sample contracts designed to test all CLM system features including:
- Metadata extraction
- SLA comparison engine
- Obligation tracking
- Risk detection
- Milestone tracking
- Contract linking (parent/child relationships)

---

## Contract Suite Overview

| File | Type | Related To | Key Test Data |
|------|------|------------|---------------|
| `NDA_TechServices_Acme.md` | NDA | - | Confidentiality terms, IP, 5-year term |
| `MSA_TechServices_Acme.md` | MSA | Parent of SOW | SLAs, fees, obligations, 3-year term |
| `SOW_InfraManagement_Acme.md` | SOW | Child of MSA | Milestones, deliverables, pricing |
| `Amendment_001_MSA_TechServices.md` | Amendment | Amends MSA | Scope expansion, price changes |
| `SLA_ITServices_Acme.md` | SLA | Attachment to MSA | 50+ SLA metrics with codes |

---

## Key Data Points by Contract

### NDA_TechServices_Acme.md
- **Parties:** TechServices Global Inc. ↔ Acme Corporation
- **Effective Date:** December 1, 2023
- **Expiration Date:** December 1, 2028
- **Term:** 5 years
- **Key Obligations:**
  - Notify unauthorized access within 24 hours
  - Return/destroy within 15 business days
  - 30 days termination notice
  - 5-year survival post-disclosure

### MSA_TechServices_Acme.md
- **Contract Number:** MSA-2024-001
- **Effective Date:** January 1, 2024
- **Expiration Date:** December 31, 2026
- **Contract Value:** $4,500,000 (3 years)
- **Monthly Fee:** $125,000
- **Auto-Renewal:** Yes (1-year periods)
- **Notice Period:** 90 days
- **Key SLAs:**
  - System Availability: 99.9% target
  - Network Availability: 99.95% target
  - P1 Response: 15 minutes
  - First Call Resolution: 75%
- **Service Credits:** Up to 30% monthly fee
- **Liability Cap:** 2x annual fees

### SOW_InfraManagement_Acme.md
- **SOW Number:** SOW-2024-001
- **Reference MSA:** MSA-2024-001
- **Effective Date:** January 15, 2024
- **End Date:** January 14, 2025
- **Total Value:** $2,090,000
- **Monthly Fee:** $125,000
- **Project Fees:** $400,000
- **Key Milestones:**
  | ID | Name | Date | Credit at Risk |
  |----|------|------|----------------|
  | MS-2.1 | Assessment Complete | Feb 28, 2024 | $25,000 |
  | MS-2.2 | Migration Plan | Mar 15, 2024 | $50,000 |
  | MS-3.1 | Phase 1 (25%) | Apr 30, 2024 | $75,000 |
  | MS-3.2 | Phase 2 (50%) | Jun 30, 2024 | $100,000 |
  | MS-3.3 | Phase 3 (75%) | Sep 30, 2024 | $125,000 |
  | MS-4.0 | Final (80%) | Nov 30, 2024 | $150,000 |

### Amendment_001_MSA_TechServices.md
- **Amendment Number:** AMD-2024-001
- **Reference:** MSA-2024-001
- **Effective Date:** July 1, 2024
- **Key Changes:**
  - Monthly fee increased from $125,000 to $275,000
  - Contract value increased to $8,250,000
  - Term extended to December 31, 2027
  - New services: SOC, DevOps, Data Analytics
  - New SLAs for security and DevOps
  - Service credits increased to 40%

### SLA_ITServices_Acme.md
- **SLA Number:** SLA-2024-001
- **50+ SLA metrics with reference codes:**
  - 12.x: Application Availability
  - 2.1.x: Network Infrastructure
  - 3.x.x: Cloud Services
  - 4.x.x: Incident Management
  - 5.x.x: Operational Metrics
  - 6.x.x: Security Metrics
- **Matches master data SLA codes for comparison testing**

---

## Converting to PDF

### Option 1: Using Pandoc (Recommended)

```bash
# Install pandoc if not installed
# macOS: brew install pandoc
# Ubuntu: sudo apt-get install pandoc

# Convert all markdown files to PDF
cd backend/data/sample_contracts/test_contracts

for f in *.md; do
  pandoc "$f" -o "${f%.md}.pdf" --pdf-engine=xelatex
done
```

### Option 2: Using VS Code
1. Install "Markdown PDF" extension
2. Open .md file
3. Right-click → "Markdown PDF: Export (pdf)"

### Option 3: Using Python (markdown-pdf)

```bash
pip install markdown-pdf

python << 'EOF'
import os
from markdown_pdf import MarkdownPdf, Section

input_dir = "backend/data/sample_contracts/test_contracts"
for filename in os.listdir(input_dir):
    if filename.endswith('.md') and filename != 'README.md':
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(input_dir, filename.replace('.md', '.pdf'))

        with open(input_path, 'r') as f:
            content = f.read()

        pdf = MarkdownPdf()
        pdf.add_section(Section(content))
        pdf.save(output_path)
        print(f"Created: {output_path}")
EOF
```

### Option 4: Using wkhtmltopdf

```bash
# Install: brew install wkhtmltopdf

# First convert to HTML, then to PDF
for f in *.md; do
  pandoc "$f" -o "${f%.md}.html"
  wkhtmltopdf "${f%.md}.html" "${f%.md}.pdf"
  rm "${f%.md}.html"
done
```

---

## Testing Workflow

### 1. Convert and Upload
```bash
# Convert to PDF
cd backend/data/sample_contracts/test_contracts
pandoc MSA_TechServices_Acme.md -o MSA_TechServices_Acme.pdf

# Upload via API
curl -X POST http://localhost:8000/api/contracts/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@MSA_TechServices_Acme.pdf"
```

### 2. Process and Verify Extraction
```bash
# Check contract status
curl http://localhost:8000/api/contracts/{contract_id} \
  -H "Authorization: Bearer $TOKEN"

# Verify extracted metadata
curl http://localhost:8000/api/dashboard/cockpit/{contract_id} \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Test SLA Comparison
```bash
# Seed master data
curl -X POST http://localhost:8000/api/admin/master-data/seed-all \
  -H "Authorization: Bearer $TOKEN"

# Trigger SLA comparison
curl -X POST http://localhost:8000/api/admin/scheduler/jobs/sla_comparison/run \
  -H "Authorization: Bearer $TOKEN"

# Check comparison results
curl http://localhost:8000/api/contracts/{contract_id}/sla-comparison \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Test Contract Linking
After uploading MSA and SOW, link them:
```bash
# Create parent-child link
curl -X POST http://localhost:8000/api/contracts/{msa_id}/links \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "child_contract_id": "{sow_id}",
    "link_type": "sow"
  }'
```

---

## Expected Extraction Results

### From MSA_TechServices_Acme.md

| Field | Expected Value |
|-------|----------------|
| Contract Type | MSA |
| Counterparty | Acme Corporation |
| Provider | TechServices Global Inc. |
| Effective Date | 2024-01-01 |
| Expiration Date | 2026-12-31 |
| Contract Value | 4,500,000 |
| Currency | USD |
| Auto-Renewal | Yes |
| Notice Period | 90 days |
| Risk Level | Medium |

### From SOW_InfraManagement_Acme.md

| Field | Expected Value |
|-------|----------------|
| Contract Type | SOW |
| Reference Contract | MSA-2024-001 |
| Effective Date | 2024-01-15 |
| End Date | 2025-01-14 |
| Total Value | 2,090,000 |
| Monthly Fee | 125,000 |
| Milestones | 9 milestones |

---

## SLA Codes for Comparison Testing

The SLA document includes codes that map to the master data:

| SLA Code | Description | Target |
|----------|-------------|--------|
| 12.1 | Core Business Applications | 99.95% |
| 12.2 | Database Services | 99.95% |
| 2.1.1 | Network Core | 99.99% |
| 2.1.2 | WAN Connectivity | 99.9% |
| 4.1.1 | P1 Response Time | 10 min |
| 5.1.3 | First Call Resolution | 75% |
| 5.2.1 | Change Success Rate | 98% |
| 6.2.1 | Critical Patch Deployment | 24 hrs |

These codes should match entries in the `sla_master_data` table after seeding.

---

## Troubleshooting

### PDF Conversion Issues
- Ensure fonts are installed for non-ASCII characters
- Use `--pdf-engine=xelatex` for better Unicode support
- Check that input file is valid UTF-8

### Extraction Issues
- Verify document is text-searchable (not scanned image)
- Check parser logs for errors
- Try smaller documents first

### SLA Comparison Not Working
- Ensure master data is seeded
- Verify SLA codes in contract match master data codes
- Check scheduler is running

---

*Last updated: 2026-02-12*

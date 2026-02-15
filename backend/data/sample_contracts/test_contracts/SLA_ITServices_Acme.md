# SERVICE LEVEL AGREEMENT

**Agreement Number:** SLA-2024-001
**Reference Contract:** MSA-2024-001
**Effective Date:** January 1, 2024
**Review Date:** January 1, 2025

---

## PARTIES

This Service Level Agreement ("SLA") is established between:

**SERVICE PROVIDER:**
TechServices Global Inc.
("Provider")

**CLIENT:**
Acme Corporation
("Client")

---

## 1. PURPOSE AND SCOPE

### 1.1 Purpose

This SLA defines the service levels, performance metrics, and measurement methodologies that Provider shall deliver to Client under the Master Services Agreement.

### 1.2 Scope

This SLA covers all services provided under:
- MSA-2024-001 (Master Services Agreement)
- SOW-2024-001 (Infrastructure Modernization)
- All subsequent Statements of Work

---

## 2. SERVICE AVAILABILITY

### 2.1 Production Environment Availability

| Service Component | SLA Reference | Target | Minimum | Measurement Window |
|-------------------|---------------|--------|---------|-------------------|
| Core Business Applications | 12.1 | 99.95% | 99.9% | Monthly |
| Database Services | 12.2 | 99.95% | 99.9% | Monthly |
| Application Servers | 12.3 | 99.9% | 99.7% | Monthly |
| Web Services/APIs | 12.4 | 99.9% | 99.5% | Monthly |
| Authentication Services | 12.5 | 99.99% | 99.95% | Monthly |
| Email Services | 12.6 | 99.9% | 99.5% | Monthly |
| File/Storage Services | 12.7 | 99.95% | 99.9% | Monthly |

### 2.2 Infrastructure Availability

| Service Component | SLA Reference | Target | Minimum | Measurement Window |
|-------------------|---------------|--------|---------|-------------------|
| Network Core | 2.1.1 | 99.99% | 99.95% | Monthly |
| WAN Connectivity | 2.1.2 | 99.9% | 99.5% | Monthly |
| LAN Connectivity | 2.1.3 | 99.95% | 99.9% | Monthly |
| Firewall Services | 2.1.4 | 99.99% | 99.95% | Monthly |
| Load Balancers | 2.1.5 | 99.95% | 99.9% | Monthly |
| DNS Services | 2.1.6 | 99.999% | 99.99% | Monthly |
| VPN Services | 2.1.7 | 99.9% | 99.5% | Monthly |

### 2.3 Cloud Infrastructure Availability

| Service Component | SLA Reference | Target | Minimum | Measurement Window |
|-------------------|---------------|--------|---------|-------------------|
| AWS Compute (EC2) | 3.1.1 | 99.95% | 99.9% | Monthly |
| AWS Storage (S3) | 3.1.2 | 99.99% | 99.95% | Monthly |
| AWS Database (RDS) | 3.1.3 | 99.95% | 99.9% | Monthly |
| Azure Active Directory | 3.2.1 | 99.99% | 99.95% | Monthly |
| Azure Virtual Machines | 3.2.2 | 99.95% | 99.9% | Monthly |
| Kubernetes Cluster | 3.3.1 | 99.9% | 99.5% | Monthly |

### 2.4 Availability Calculation

```
Availability % = ((Total Minutes - Downtime Minutes) / Total Minutes) × 100

Where:
- Total Minutes = Minutes in measurement period (e.g., 43,200 for 30-day month)
- Downtime Minutes = Unplanned outage duration (excluding scheduled maintenance)
```

### 2.5 Scheduled Maintenance Windows

| Day | Time (UTC) | Duration | Notification |
|-----|------------|----------|--------------|
| Sunday | 02:00 - 06:00 | 4 hours | 7 days advance |
| Wednesday | 02:00 - 04:00 | 2 hours | 7 days advance |

Emergency maintenance requires **4 hours** minimum notice (or as soon as practicable).

---

## 3. INCIDENT RESPONSE AND RESOLUTION

### 3.1 Incident Priority Definitions

| Priority | Definition | Business Impact |
|----------|------------|-----------------|
| P1 - Critical | Complete system failure, all users affected | Business operations stopped |
| P2 - High | Major functionality impaired, many users affected | Significant business impact |
| P3 - Medium | Limited functionality impact, some users affected | Moderate business impact |
| P4 - Low | Minor issue, workaround available | Minimal business impact |

### 3.2 Response Time SLAs

| Priority | SLA Reference | Target Response | Maximum Response | Escalation |
|----------|---------------|-----------------|------------------|------------|
| P1 - Critical | 4.1.1 | 10 minutes | 15 minutes | Immediate to management |
| P2 - High | 4.1.2 | 20 minutes | 30 minutes | 1 hour to management |
| P3 - Medium | 4.1.3 | 1 hour | 2 hours | 4 hours to management |
| P4 - Low | 4.1.4 | 2 hours | 4 hours | Next business day |

### 3.3 Resolution Time SLAs

| Priority | SLA Reference | Target Resolution | Maximum Resolution |
|----------|---------------|-------------------|-------------------|
| P1 - Critical | 4.2.1 | 2 hours | 4 hours |
| P2 - High | 4.2.2 | 4 hours | 8 hours |
| P3 - Medium | 4.2.3 | 8 hours | 24 hours |
| P4 - Low | 4.2.4 | 24 hours | 72 hours |

### 3.4 Incident Communication

| Priority | Initial Update | Ongoing Updates | Final Report |
|----------|----------------|-----------------|--------------|
| P1 | 15 minutes | Every 30 minutes | Within 24 hours |
| P2 | 30 minutes | Every 1 hour | Within 48 hours |
| P3 | 2 hours | Every 4 hours | Within 5 days |
| P4 | 4 hours | Daily | Within 7 days |

---

## 4. PERFORMANCE METRICS

### 4.1 Service Desk Performance

| Metric | SLA Reference | Target | Minimum | Measurement |
|--------|---------------|--------|---------|-------------|
| Average Speed to Answer | 5.1.1 | 30 seconds | 60 seconds | Monthly |
| Call Abandonment Rate | 5.1.2 | < 3% | < 5% | Monthly |
| First Call Resolution | 5.1.3 | 75% | 65% | Monthly |
| Ticket Acknowledgment | 5.1.4 | 15 minutes | 30 minutes | Per ticket |
| Customer Satisfaction (CSAT) | 5.1.5 | 4.5/5.0 | 4.0/5.0 | Monthly survey |
| Net Promoter Score (NPS) | 5.1.6 | > 50 | > 30 | Quarterly |

### 4.2 Change Management

| Metric | SLA Reference | Target | Minimum | Measurement |
|--------|---------------|--------|---------|-------------|
| Change Success Rate | 5.2.1 | 98% | 95% | Monthly |
| Emergency Change Rate | 5.2.2 | < 5% | < 10% | Monthly |
| Change-Related Incidents | 5.2.3 | < 2% | < 5% | Monthly |
| Change Lead Time (Standard) | 5.2.4 | 5 days | 10 days | Per change |
| Change Lead Time (Normal) | 5.2.5 | 3 days | 5 days | Per change |
| Rollback Success Rate | 5.2.6 | 100% | 95% | Per rollback |

### 4.3 Capacity and Performance

| Metric | SLA Reference | Target | Threshold | Measurement |
|--------|---------------|--------|-----------|-------------|
| CPU Utilization | 5.3.1 | < 70% | < 85% | Real-time |
| Memory Utilization | 5.3.2 | < 75% | < 90% | Real-time |
| Storage Utilization | 5.3.3 | < 80% | < 90% | Daily |
| Network Bandwidth | 5.3.4 | < 60% | < 80% | Real-time |
| Application Response Time | 5.3.5 | < 2 seconds | < 5 seconds | Real-time |
| Database Query Time | 5.3.6 | < 500ms | < 2 seconds | Real-time |

### 4.4 Backup and Recovery

| Metric | SLA Reference | Target | Minimum | Measurement |
|--------|---------------|--------|---------|-------------|
| Backup Success Rate | 5.4.1 | 99.9% | 99% | Daily |
| Backup Completion (Daily) | 5.4.2 | 100% by 06:00 | 100% by 08:00 | Daily |
| Recovery Point Objective (RPO) | 5.4.3 | 1 hour | 4 hours | Per system |
| Recovery Time Objective (RTO) | 5.4.4 | 4 hours | 8 hours | Per system |
| DR Test Success | 5.4.5 | 100% | 95% | Quarterly |
| Restore Request Completion | 5.4.6 | 4 hours | 8 hours | Per request |

---

## 5. SECURITY METRICS

### 5.1 Security Monitoring

| Metric | SLA Reference | Target | Minimum | Measurement |
|--------|---------------|--------|---------|-------------|
| Threat Detection Time | 6.1.1 | < 5 minutes | < 15 minutes | Per threat |
| Security Event Triage | 6.1.2 | < 15 minutes | < 30 minutes | Per event |
| False Positive Rate | 6.1.3 | < 5% | < 10% | Monthly |
| Security Alert Closure | 6.1.4 | 24 hours | 48 hours | Per alert |

### 5.2 Vulnerability Management

| Metric | SLA Reference | Target | Maximum | Measurement |
|--------|---------------|--------|---------|-------------|
| Critical Patch Deployment | 6.2.1 | 24 hours | 48 hours | Per patch |
| High Patch Deployment | 6.2.2 | 72 hours | 7 days | Per patch |
| Medium Patch Deployment | 6.2.3 | 14 days | 30 days | Per patch |
| Low Patch Deployment | 6.2.4 | 30 days | 60 days | Per patch |
| Vulnerability Scan Completion | 6.2.5 | Weekly | Bi-weekly | Per scan |
| Patch Compliance Rate | 6.2.6 | > 98% | > 95% | Monthly |

### 5.3 Security Incident Response

| Metric | SLA Reference | Target | Maximum | Measurement |
|--------|---------------|--------|---------|-------------|
| Security Incident Response | 6.3.1 | 15 minutes | 30 minutes | Per incident |
| Incident Containment | 6.3.2 | 1 hour | 4 hours | Per incident |
| Incident Eradication | 6.3.3 | 4 hours | 24 hours | Per incident |
| Post-Incident Report | 6.3.4 | 72 hours | 7 days | Per incident |

---

## 6. REPORTING

### 6.1 Report Schedule

| Report | Frequency | Delivery | Recipient |
|--------|-----------|----------|-----------|
| Daily Operations Summary | Daily | By 09:00 | IT Operations |
| Weekly Status Report | Weekly | Friday 17:00 | IT Director |
| Monthly SLA Report | Monthly | 5th business day | CIO, IT Director |
| Quarterly Business Review | Quarterly | 15th of month | Executive Team |
| Annual Review | Annually | January 31 | C-Suite |

### 6.2 Report Contents

**Monthly SLA Report shall include:**
- Executive summary
- SLA compliance scorecard (all metrics)
- Trend analysis (3-month rolling)
- Incident summary and root causes
- Change summary
- Capacity projections
- Service credits calculation (if applicable)
- Improvement recommendations

---

## 7. SERVICE CREDITS

### 7.1 Availability Service Credits

| Availability Level | Service Credit | Cap |
|--------------------|----------------|-----|
| 99.7% - 99.89% | 5% of monthly fee | |
| 99.5% - 99.69% | 10% of monthly fee | |
| 99.0% - 99.49% | 15% of monthly fee | |
| 98.0% - 98.99% | 20% of monthly fee | |
| Below 98.0% | 30% of monthly fee | |
| **Maximum Monthly Credit** | | **40%** |

### 7.2 Response/Resolution Time Credits

| SLA Miss | Service Credit |
|----------|----------------|
| Response time missed (P1) | $5,000 per incident |
| Response time missed (P2) | $2,500 per incident |
| Resolution time missed (P1) | $10,000 per incident |
| Resolution time missed (P2) | $5,000 per incident |

### 7.3 Chronic Failure

If any Critical SLA is missed for **3 consecutive months**, Client may:
- Terminate the affected service without penalty
- Require remediation plan within 10 business days
- Invoke performance improvement clause

---

## 8. GOVERNANCE

### 8.1 Service Review Meetings

| Meeting | Frequency | Attendees |
|---------|-----------|-----------|
| Operational Review | Weekly | Operations teams |
| Service Review | Monthly | Service managers |
| Executive Review | Quarterly | Directors/VPs |
| Strategic Review | Annually | C-level executives |

### 8.2 Escalation Matrix

| Level | Provider | Client | Timeframe |
|-------|----------|--------|-----------|
| 1 | Service Desk | IT Support | Immediate |
| 2 | Team Lead | IT Manager | 2 hours |
| 3 | Service Manager | IT Director | 4 hours |
| 4 | Delivery Director | VP of IT | 8 hours |
| 5 | VP Client Services | CIO | 24 hours |
| 6 | CEO | CEO | 48 hours |

---

## 9. CONTINUOUS IMPROVEMENT

### 9.1 Improvement Targets

Provider commits to the following annual improvements:

| Metric | Year 1 Baseline | Year 2 Target | Year 3 Target |
|--------|-----------------|---------------|---------------|
| Overall Availability | 99.9% | 99.95% | 99.97% |
| First Call Resolution | 70% | 75% | 80% |
| CSAT Score | 4.3 | 4.5 | 4.7 |
| MTTR (P1) | 3 hours | 2 hours | 1.5 hours |

### 9.2 Innovation Initiatives

Provider shall propose at least **2 innovation initiatives** per year aimed at:
- Improving service quality
- Reducing costs
- Enhancing user experience
- Leveraging emerging technologies

---

## 10. SLA REVIEW AND MODIFICATION

### 10.1 Annual Review

This SLA shall be reviewed annually, with amendments agreed upon by both Parties. Review shall consider:
- Business requirement changes
- Technology evolution
- Industry benchmarks
- Historical performance

### 10.2 Ad-Hoc Review

Either Party may request an SLA review due to:
- Significant scope changes
- Material business changes
- Regulatory requirements
- Technology changes

---

## APPENDIX A: SLA REFERENCE CODES

| Code | Category | Description |
|------|----------|-------------|
| 12.x | Application Availability | Core business application uptime |
| 2.1.x | Network Infrastructure | Network and connectivity |
| 3.x.x | Cloud Services | AWS/Azure/K8s metrics |
| 4.x.x | Incident Management | Response and resolution times |
| 5.x.x | Operational Metrics | Service desk, change, capacity |
| 6.x.x | Security Metrics | Security monitoring and response |

---

## SIGNATURES

**TechServices Global Inc.**

Signature: _________________________
Name: Michael Johnson
Title: VP of Service Delivery
Date: December 28, 2023

**Acme Corporation**

Signature: _________________________
Name: Robert Chen
Title: VP of Information Technology
Date: December 29, 2023

---

*End of Service Level Agreement*

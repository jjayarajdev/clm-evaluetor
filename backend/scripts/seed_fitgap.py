#!/usr/bin/env python3
"""
Seed script for fit-gap features: service portfolio, organization officers,
org hierarchy, contract documents, KPI approvals, and relationship status history.

Run with: python -m scripts.seed_fitgap
"""

import asyncio
import random
import sys
from datetime import datetime, timedelta, date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4, UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text, update, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings

# ── Constants ─────────────────────────────────────────────────────────
ACME_TENANT = UUID("10000000-0000-0000-0000-000000000001")
TECHSTART_TENANT = UUID("10000000-0000-0000-0000-000000000002")


async def seed_fitgap():
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # ── Lookup existing data ──────────────────────────────────────
        print("Looking up existing data...")

        # Organizations
        orgs = {}
        rows = await db.execute(text("SELECT id, name, tenant_id FROM organizations"))
        for r in rows:
            orgs[r.name] = {"id": r.id, "tenant_id": r.tenant_id}
        print(f"  Found {len(orgs)} organizations")

        # Relationships
        rels = {}
        rows = await db.execute(text("""
            SELECT br.id, o1.name as org_a, o2.name as org_b, br.tenant_id, br.relationship_type
            FROM business_relationships br
            JOIN organizations o1 ON br.org_a_id = o1.id
            JOIN organizations o2 ON br.org_b_id = o2.id
        """))
        for r in rows:
            rels[f"{r.org_a}|{r.org_b}"] = {"id": r.id, "tenant_id": r.tenant_id, "type": r.relationship_type}
        print(f"  Found {len(rels)} relationships")

        # KPIs
        kpis = []
        rows = await db.execute(text("SELECT id, name, relationship_id FROM kpis"))
        for r in rows:
            kpis.append({"id": r.id, "name": r.name, "rel_id": r.relationship_id})
        print(f"  Found {len(kpis)} KPIs")

        # Key contracts (first instance of each, Acme tenant)
        contracts = {}
        rows = await db.execute(text("""
            SELECT DISTINCT ON (filename) id, filename, contract_type, counterparty, tenant_id
            FROM contracts
            WHERE tenant_id = :tid
            ORDER BY filename, id
        """), {"tid": str(ACME_TENANT)})
        for r in rows:
            contracts[r.filename] = {"id": r.id, "type": r.contract_type, "party": r.counterparty, "tenant_id": r.tenant_id}
        print(f"  Found {len(contracts)} Acme contracts")

        # Admin user
        admin_row = await db.execute(text(
            "SELECT id FROM users WHERE username='admin' AND tenant_id = :tid"
        ), {"tid": str(ACME_TENANT)})
        admin_user_id = admin_row.scalar()
        print(f"  Admin user: {admin_user_id}")

        # ── Clean existing fit-gap seed data ──────────────────────────
        print("\nCleaning existing fit-gap seed data...")
        await db.execute(text("DELETE FROM document_sections"))
        await db.execute(text("DELETE FROM document_signatures"))
        await db.execute(text("DELETE FROM contract_documents"))
        await db.execute(text("DELETE FROM relationship_status_history"))
        await db.execute(text("DELETE FROM relationship_services"))
        await db.execute(text("DELETE FROM service_portfolios"))
        await db.execute(text("DELETE FROM organization_officers"))
        await db.commit()
        print("  Cleaned.")

        # ══════════════════════════════════════════════════════════════
        # 1. ORGANIZATION HIERARCHY (update parent_organization_id)
        # ══════════════════════════════════════════════════════════════
        print("\n1. Setting up organization hierarchy...")

        # Acme Corp is the holding company; TechStart and CloudServices are subsidiaries
        if "Acme Corporation" in orgs and "TechStart Inc" in orgs:
            await db.execute(text("""
                UPDATE organizations SET parent_organization_id = :parent, organization_level = 'holding'
                WHERE id = :id
            """), {"parent": None, "id": str(orgs["Acme Corporation"]["id"])})

            await db.execute(text("""
                UPDATE organizations SET parent_organization_id = :parent, organization_level = 'subsidiary'
                WHERE id = :id
            """), {"parent": str(orgs["Acme Corporation"]["id"]), "id": str(orgs["TechStart Inc"]["id"])})

            await db.execute(text("""
                UPDATE organizations SET parent_organization_id = :parent, organization_level = 'division'
                WHERE id = :id
            """), {"parent": str(orgs["Acme Corporation"]["id"]), "id": str(orgs["CloudServices Pro"]["id"])})

            # GlobalSupply and Strategic Partners are independent
            for name in ["GlobalSupply International", "Strategic Partners LLC"]:
                if name in orgs:
                    await db.execute(text("""
                        UPDATE organizations SET organization_level = 'holding'
                        WHERE id = :id
                    """), {"id": str(orgs[name]["id"])})

            # Our Company is the internal holding
            if "Our Company" in orgs:
                await db.execute(text("""
                    UPDATE organizations SET organization_level = 'holding'
                    WHERE id = :id
                """), {"id": str(orgs["Our Company"]["id"])})

            await db.commit()
            print("  Acme Corp → TechStart Inc (subsidiary), CloudServices Pro (division)")

        # ══════════════════════════════════════════════════════════════
        # 2. ORGANIZATION OFFICERS
        # ══════════════════════════════════════════════════════════════
        print("\n2. Creating organization officers...")
        officer_count = 0

        officer_data = {
            "Our Company": [
                ("Sarah Mitchell", "VP of Vendor Relations", "sarah.mitchell@ourcompany.com", "+1-415-555-0101", "Executive Management", "relationship_owner", "internal", True),
                ("David Chen", "Service Delivery Director", "david.chen@ourcompany.com", "+1-415-555-0102", "Service Delivery", "service_delivery_manager", "internal", False),
                ("Lisa Park", "Procurement Manager", "lisa.park@ourcompany.com", "+1-415-555-0103", "Procurement", "commercial_manager", "internal", False),
                ("James Rodriguez", "CTO", "james.rodriguez@ourcompany.com", "+1-415-555-0104", "Technology", "executive_sponsor", "internal", True),
            ],
            "Acme Corporation": [
                ("Robert Hayes", "Chief Operating Officer", "robert.hayes@acmecorp.com", "+1-313-555-0201", "Operations", "executive_sponsor", "external", True),
                ("Jennifer Wu", "Account Director", "jennifer.wu@acmecorp.com", "+1-313-555-0202", "Account Management", "account_manager", "external", False),
                ("Michael Torres", "Technical Program Manager", "michael.torres@acmecorp.com", "+1-313-555-0203", "Engineering", "technical_lead", "external", False),
                ("Emily Carter", "Compliance Director", "emily.carter@acmecorp.com", "+1-313-555-0204", "Legal & Compliance", "compliance_officer", "external", False),
            ],
            "TechStart Inc": [
                ("Alex Kim", "CEO", "alex.kim@techstart.io", "+1-512-555-0301", "Executive", "executive_sponsor", "external", True),
                ("Priya Sharma", "Head of Engineering", "priya.sharma@techstart.io", "+1-512-555-0302", "Engineering", "technical_lead", "external", False),
            ],
            "GlobalSupply International": [
                ("Hans Mueller", "Managing Director EMEA", "hans.mueller@globalsupply.com", "+49-69-555-0401", "Executive", "executive_sponsor", "external", True),
                ("Maria Santos", "Operations Manager", "maria.santos@globalsupply.com", "+49-69-555-0402", "Operations", "operations_lead", "external", False),
                ("Thomas Wright", "Account Manager", "thomas.wright@globalsupply.com", "+49-69-555-0403", "Commercial", "account_manager", "external", False),
            ],
            "CloudServices Pro": [
                ("Kevin O'Brien", "VP Customer Success", "kevin.obrien@cloudservicespro.com", "+1-206-555-0501", "Customer Success", "service_delivery_manager", "external", True),
                ("Aisha Johnson", "Technical Architect", "aisha.johnson@cloudservicespro.com", "+1-206-555-0502", "Engineering", "technical_lead", "external", False),
            ],
            "Strategic Partners LLC": [
                ("Diana Foster", "Managing Partner", "diana.foster@strategicpartners.com", "+1-212-555-0601", "Leadership", "executive_sponsor", "external", True),
                ("Ryan Cooper", "Senior Consultant", "ryan.cooper@strategicpartners.com", "+1-212-555-0602", "Consulting", "service_delivery_manager", "external", False),
            ],
        }

        for org_name, officers in officer_data.items():
            if org_name not in orgs:
                continue
            org = orgs[org_name]
            for name, title, email, phone, dept, role, side, is_primary in officers:
                await db.execute(text("""
                    INSERT INTO organization_officers (id, tenant_id, organization_id, name, title, email, phone, department, governance_role, side, is_primary, is_active)
                    VALUES (:id, :tid, :oid, :name, :title, :email, :phone, :dept, :role, :side, :primary, true)
                """), {
                    "id": str(uuid4()), "tid": str(org["tenant_id"]), "oid": str(org["id"]),
                    "name": name, "title": title, "email": email, "phone": phone,
                    "dept": dept, "role": role, "side": side, "primary": is_primary,
                })
                officer_count += 1

        await db.commit()
        print(f"  Created {officer_count} officers across {len(officer_data)} organizations")

        # ══════════════════════════════════════════════════════════════
        # 3. SERVICE PORTFOLIO
        # ══════════════════════════════════════════════════════════════
        print("\n3. Creating service portfolio...")
        service_ids = {}

        services = [
            # Our Company's services
            ("Our Company", "ITO-001", "IT Outsourcing", "it_services", "active",
             "End-to-end IT infrastructure management including cloud, network, and security operations"),
            ("Our Company", "CON-001", "Strategic Advisory", "consulting", "active",
             "Business strategy and digital transformation consulting"),
            ("Our Company", "PRO-001", "Procurement Services", "procurement", "active",
             "Managed procurement and vendor lifecycle management"),

            # Acme Corp's services
            ("Acme Corporation", "ACM-MFG-001", "Manufacturing Operations", "manufacturing", "active",
             "Precision manufacturing and assembly services for industrial components"),
            ("Acme Corporation", "ACM-LOG-001", "Supply Chain Management", "logistics", "active",
             "End-to-end supply chain visibility and logistics coordination"),

            # GlobalSupply services
            ("GlobalSupply International", "GS-LOG-001", "Global Freight", "logistics", "active",
             "International freight forwarding and customs brokerage"),
            ("GlobalSupply International", "GS-LOG-002", "Warehousing", "logistics", "active",
             "Temperature-controlled warehousing and distribution"),

            # CloudServices Pro services
            ("CloudServices Pro", "CS-IT-001", "Cloud Infrastructure", "it_services", "active",
             "AWS/Azure managed cloud hosting with 99.95% uptime SLA"),
            ("CloudServices Pro", "CS-IT-002", "DevOps Platform", "it_services", "active",
             "CI/CD pipeline management, container orchestration, and monitoring"),

            # TechStart services
            ("TechStart Inc", "TS-IT-001", "SaaS Platform", "it_services", "active",
             "Cloud-native SaaS application development and maintenance"),

            # Strategic Partners
            ("Strategic Partners LLC", "SP-CON-001", "Implementation Consulting", "consulting", "active",
             "System integration and change management consulting"),
            ("Strategic Partners LLC", "SP-FIN-001", "Financial Advisory", "financial", "planned",
             "M&A due diligence and financial modeling services"),
        ]

        for org_name, code, name, stype, status, desc in services:
            if org_name not in orgs:
                continue
            org = orgs[org_name]
            sid = uuid4()
            service_ids[code] = sid
            await db.execute(text("""
                INSERT INTO service_portfolios (id, tenant_id, organization_id, name, code, description, service_type, status)
                VALUES (:id, :tid, :oid, :name, :code, :desc, :stype, :status)
            """), {
                "id": str(sid), "tid": str(org["tenant_id"]), "oid": str(org["id"]),
                "name": name, "code": code, "desc": desc, "stype": stype, "status": status,
            })

        await db.commit()
        print(f"  Created {len(services)} services")

        # Link services to relationships
        print("  Linking services to relationships...")
        rel_service_links = [
            ("Our Company|Acme Corporation", "ITO-001", "IT infrastructure management for Acme manufacturing plants"),
            ("Our Company|Acme Corporation", "CON-001", "Digital transformation strategy for Acme operations"),
            ("Our Company|GlobalSupply International", "PRO-001", "Procurement coordination for GlobalSupply contracts"),
            ("Our Company|CloudServices Pro", "ITO-001", "Cloud infrastructure oversight and governance"),
            ("Our Company|Strategic Partners LLC", "CON-001", "Joint consulting engagements for enterprise clients"),
        ]

        link_count = 0
        for rel_key, svc_code, scope in rel_service_links:
            if rel_key in rels and svc_code in service_ids:
                await db.execute(text("""
                    INSERT INTO relationship_services (id, relationship_id, service_portfolio_id, scope, is_active, start_date)
                    VALUES (:id, :rid, :sid, :scope, true, :start)
                """), {
                    "id": str(uuid4()),
                    "rid": str(rels[rel_key]["id"]),
                    "sid": str(service_ids[svc_code]),
                    "scope": scope,
                    "start": datetime(2024, 1, 1),
                })
                link_count += 1
        await db.commit()
        print(f"  Linked {link_count} services to relationships")

        # ══════════════════════════════════════════════════════════════
        # 4. CONTRACT DOCUMENTS + SIGNATURES + SECTIONS
        # ══════════════════════════════════════════════════════════════
        print("\n4. Creating contract documents, signatures, and sections...")
        doc_count = 0
        sig_count = 0
        sec_count = 0

        # MSA_CareerSource_Executed.pdf - fully executed MSA
        cs_contract = contracts.get("MSA_CareerSource_Executed.pdf")
        if cs_contract:
            cid = cs_contract["id"]
            tid = cs_contract["tenant_id"]

            # Main agreement
            main_doc_id = uuid4()
            await db.execute(text("""
                INSERT INTO contract_documents (id, tenant_id, contract_id, document_type, title, description, language, version, is_active)
                VALUES (:id, :tid, :cid, 'main_agreement', :title, :desc, 'en', '2.0', true)
            """), {"id": str(main_doc_id), "tid": str(tid), "cid": str(cid),
                   "title": "Master Services Agreement - CareerSource",
                   "desc": "Executed MSA covering IT managed services with SLA framework"})
            doc_count += 1

            # Signatures for main agreement
            for signer_name, signer_title, signer_org, sig_type, sig_status, signed_date in [
                ("Robert Hayes", "COO", "CareerSource", "wet_ink", "signed", datetime(2024, 3, 15)),
                ("Sarah Mitchell", "VP Vendor Relations", "Our Company", "wet_ink", "signed", datetime(2024, 3, 14)),
                ("Emily Carter", "General Counsel", "CareerSource", "digital", "signed", datetime(2024, 3, 15)),
            ]:
                await db.execute(text("""
                    INSERT INTO document_signatures (id, document_id, signer_name, signer_title, signer_organization, signature_type, signature_status, signed_date)
                    VALUES (:id, :did, :name, :title, :org, :type, :status, :signed)
                """), {"id": str(uuid4()), "did": str(main_doc_id), "name": signer_name,
                       "title": signer_title, "org": signer_org, "type": sig_type,
                       "status": sig_status, "signed": signed_date})
                sig_count += 1

            # Sections for main agreement
            sections = [
                ("1", "Definitions and Interpretation", 1, 3),
                ("2", "Scope of Services", 4, 8),
                ("3", "Service Level Agreements", 9, 15),
                ("4", "Pricing and Payment Terms", 16, 19),
                ("5", "Term and Termination", 20, 22),
                ("6", "Confidentiality", 23, 25),
                ("7", "Limitation of Liability", 26, 27),
                ("8", "Dispute Resolution", 28, 29),
                ("9", "General Provisions", 30, 32),
            ]
            for num, title, ps, pe in sections:
                await db.execute(text("""
                    INSERT INTO document_sections (id, document_id, section_number, title, page_start, page_end, order_index)
                    VALUES (:id, :did, :num, :title, :ps, :pe, :oi)
                """), {"id": str(uuid4()), "did": str(main_doc_id), "num": num,
                       "title": title, "ps": ps, "pe": pe, "oi": int(num)})
                sec_count += 1

            # SLA Schedule document
            sla_doc_id = uuid4()
            await db.execute(text("""
                INSERT INTO contract_documents (id, tenant_id, contract_id, document_type, title, description, language, version, is_active)
                VALUES (:id, :tid, :cid, 'schedule', :title, :desc, 'en', '2.0', true)
            """), {"id": str(sla_doc_id), "tid": str(tid), "cid": str(cid),
                   "title": "Schedule A - Service Level Definitions",
                   "desc": "Detailed SLA metrics, targets, and penalty structure"})
            doc_count += 1

            for num, title, ps, pe in [
                ("A.1", "Priority 1 - Critical Incidents", 1, 2),
                ("A.2", "Priority 2 - High Impact", 3, 4),
                ("A.3", "Priority 3 - Medium Impact", 5, 5),
                ("A.4", "Service Credits & Penalties", 6, 8),
                ("A.5", "Measurement & Reporting", 9, 10),
            ]:
                await db.execute(text("""
                    INSERT INTO document_sections (id, document_id, section_number, title, page_start, page_end, order_index)
                    VALUES (:id, :did, :num, :title, :ps, :pe, :oi)
                """), {"id": str(uuid4()), "did": str(sla_doc_id), "num": num,
                       "title": title, "ps": ps, "pe": pe, "oi": sec_count})
                sec_count += 1

            # Amendment document (pending signatures)
            amend_doc_id = uuid4()
            await db.execute(text("""
                INSERT INTO contract_documents (id, tenant_id, contract_id, document_type, title, description, language, version, is_active)
                VALUES (:id, :tid, :cid, 'amendment', :title, :desc, 'en', '1.0', true)
            """), {"id": str(amend_doc_id), "tid": str(tid), "cid": str(cid),
                   "title": "Amendment 1 - Extended Scope",
                   "desc": "Adds cloud migration services to the existing MSA scope"})
            doc_count += 1

            for signer_name, signer_title, signer_org, sig_status in [
                ("Robert Hayes", "COO", "CareerSource", "pending"),
                ("Sarah Mitchell", "VP Vendor Relations", "Our Company", "signed"),
            ]:
                await db.execute(text("""
                    INSERT INTO document_signatures (id, document_id, signer_name, signer_title, signer_organization, signature_type, signature_status)
                    VALUES (:id, :did, :name, :title, :org, 'digital', :status)
                """), {"id": str(uuid4()), "did": str(amend_doc_id), "name": signer_name,
                       "title": signer_title, "org": signer_org, "status": sig_status})
                sig_count += 1

        # SOW_Acme_IT_Services.pdf
        sow_contract = contracts.get("SOW_Acme_IT_Services.pdf")
        if sow_contract:
            cid = sow_contract["id"]
            tid = sow_contract["tenant_id"]

            sow_doc_id = uuid4()
            await db.execute(text("""
                INSERT INTO contract_documents (id, tenant_id, contract_id, document_type, title, description, language, version, is_active)
                VALUES (:id, :tid, :cid, 'statement_of_work', :title, :desc, 'en', '1.0', true)
            """), {"id": str(sow_doc_id), "tid": str(tid), "cid": str(cid),
                   "title": "SOW - IT Managed Services",
                   "desc": "Statement of Work for infrastructure management and helpdesk services"})
            doc_count += 1

            for signer_name, signer_title, signer_org in [
                ("Jennifer Wu", "Account Director", "Acme Corporation"),
                ("David Chen", "Service Delivery Director", "Our Company"),
            ]:
                await db.execute(text("""
                    INSERT INTO document_signatures (id, document_id, signer_name, signer_title, signer_organization, signature_type, signature_status, signed_date)
                    VALUES (:id, :did, :name, :title, :org, 'electronic', 'signed', :signed)
                """), {"id": str(uuid4()), "did": str(sow_doc_id), "name": signer_name,
                       "title": signer_title, "org": signer_org,
                       "signed": datetime(2024, 4, 1)})
                sig_count += 1

            for num, title, ps, pe in [
                ("1", "Service Description", 1, 4),
                ("2", "Service Levels & KPIs", 5, 10),
                ("3", "Resource Requirements", 11, 13),
                ("4", "Transition Plan", 14, 16),
                ("5", "Governance & Reporting", 17, 19),
                ("6", "Pricing Schedule", 20, 22),
            ]:
                await db.execute(text("""
                    INSERT INTO document_sections (id, document_id, section_number, title, page_start, page_end, order_index)
                    VALUES (:id, :did, :num, :title, :ps, :pe, :oi)
                """), {"id": str(uuid4()), "did": str(sow_doc_id), "num": num,
                       "title": title, "ps": ps, "pe": pe, "oi": int(num)})
                sec_count += 1

            # Exhibit for pricing
            exhibit_id = uuid4()
            await db.execute(text("""
                INSERT INTO contract_documents (id, tenant_id, contract_id, document_type, title, description, language, version, is_active)
                VALUES (:id, :tid, :cid, 'exhibit', :title, :desc, 'en', '1.0', true)
            """), {"id": str(exhibit_id), "tid": str(tid), "cid": str(cid),
                   "title": "Exhibit B - Rate Card",
                   "desc": "Detailed pricing for all service tiers and resource types"})
            doc_count += 1

        # Vendor_Agreement_GlobalSupply.pdf
        vendor_contract = contracts.get("Vendor_Agreement_GlobalSupply.pdf")
        if vendor_contract:
            cid = vendor_contract["id"]
            tid = vendor_contract["tenant_id"]

            vendor_doc_id = uuid4()
            await db.execute(text("""
                INSERT INTO contract_documents (id, tenant_id, contract_id, document_type, title, description, language, version, is_active)
                VALUES (:id, :tid, :cid, 'main_agreement', :title, :desc, 'en', '1.0', true)
            """), {"id": str(vendor_doc_id), "tid": str(tid), "cid": str(cid),
                   "title": "Vendor Framework Agreement - GlobalSupply",
                   "desc": "Framework agreement for logistics and supply chain services"})
            doc_count += 1

            for signer_name, signer_title, signer_org in [
                ("Hans Mueller", "Managing Director EMEA", "GlobalSupply International"),
                ("Lisa Park", "Procurement Manager", "Our Company"),
                ("James Rodriguez", "CTO", "Our Company"),
            ]:
                await db.execute(text("""
                    INSERT INTO document_signatures (id, document_id, signer_name, signer_title, signer_organization, signature_type, signature_status, signed_date)
                    VALUES (:id, :did, :name, :title, :org, 'digital', 'signed', :signed)
                """), {"id": str(uuid4()), "did": str(vendor_doc_id), "name": signer_name,
                       "title": signer_title, "org": signer_org,
                       "signed": datetime(2024, 2, 10)})
                sig_count += 1

            for num, title, ps, pe in [
                ("1", "Parties and Recitals", 1, 2),
                ("2", "Services and Deliverables", 3, 7),
                ("3", "Performance Standards", 8, 11),
                ("4", "Commercial Terms", 12, 15),
                ("5", "Insurance and Indemnification", 16, 18),
                ("6", "Governing Law", 19, 20),
            ]:
                await db.execute(text("""
                    INSERT INTO document_sections (id, document_id, section_number, title, page_start, page_end, order_index)
                    VALUES (:id, :did, :num, :title, :ps, :pe, :oi)
                """), {"id": str(uuid4()), "did": str(vendor_doc_id), "num": num,
                       "title": title, "ps": ps, "pe": pe, "oi": int(num)})
                sec_count += 1

            # NDA appendix
            nda_doc_id = uuid4()
            await db.execute(text("""
                INSERT INTO contract_documents (id, tenant_id, contract_id, document_type, title, description, language, version, is_active)
                VALUES (:id, :tid, :cid, 'appendix', :title, :desc, 'en', '1.0', true)
            """), {"id": str(tid), "tid": str(tid), "cid": str(cid),
                   "title": "Appendix C - Confidentiality Terms",
                   "desc": "Mutual NDA provisions for information exchange"})
            doc_count += 1

        await db.commit()
        print(f"  Created {doc_count} documents, {sig_count} signatures, {sec_count} sections")

        # ══════════════════════════════════════════════════════════════
        # 5. KPI APPROVAL WORKFLOW (update existing perception scores)
        # ══════════════════════════════════════════════════════════════
        print("\n5. Setting up KPI approval workflow...")

        # Get all perception scores
        scores = await db.execute(text("""
            SELECT id, kpi_id, period, is_internal, approval_status
            FROM perception_scores
            ORDER BY period, kpi_id
        """))
        all_scores = scores.fetchall()
        print(f"  Found {len(all_scores)} perception scores")

        approved = 0
        rejected = 0
        pending = 0

        for score in all_scores:
            period = score.period
            # Older periods: approved; recent: mix of approved/pending/rejected
            if period in ("2024-Q1", "2024-Q2"):
                # All approved
                await db.execute(text("""
                    UPDATE perception_scores SET approval_status = 'approved',
                        approved_by = :uid, approved_at = :at,
                        approval_comments = 'Approved as part of quarterly review cycle'
                    WHERE id = :id
                """), {"id": str(score.id), "uid": str(admin_user_id),
                       "at": datetime(2024, 4 if period == "2024-Q1" else 7, 15)})
                approved += 1
            elif period == "2024-Q3":
                # Mostly approved, 2 rejected
                r = random.random()
                if r < 0.85:
                    await db.execute(text("""
                        UPDATE perception_scores SET approval_status = 'approved',
                            approved_by = :uid, approved_at = :at,
                            approval_comments = 'Score validated against operational data'
                        WHERE id = :id
                    """), {"id": str(score.id), "uid": str(admin_user_id),
                           "at": datetime(2024, 10, 10)})
                    approved += 1
                else:
                    await db.execute(text("""
                        UPDATE perception_scores SET approval_status = 'rejected',
                            approved_by = :uid, approved_at = :at,
                            approval_comments = 'Score inconsistent with service desk metrics. Please resubmit with supporting data.'
                        WHERE id = :id
                    """), {"id": str(score.id), "uid": str(admin_user_id),
                           "at": datetime(2024, 10, 12)})
                    rejected += 1
            else:
                # Q4 - pending approval (leave as-is)
                pending += 1

        await db.commit()
        print(f"  Approved: {approved}, Rejected: {rejected}, Pending: {pending}")

        # ══════════════════════════════════════════════════════════════
        # 6. RELATIONSHIP STATUS HISTORY
        # ══════════════════════════════════════════════════════════════
        print("\n6. Creating relationship status history...")
        history_count = 0

        # Status progression for each relationship over 4 quarters
        history_data = {
            "Our Company|Acme Corporation": [
                ("2024-Q1", "good", None, 78.0, "Initial relationship assessment"),
                ("2024-Q2", "good", "good", 80.5, "Steady performance, minor delivery improvement"),
                ("2024-Q3", "excellent", "good", 88.0, "Strong Q3 — all SLAs met, positive feedback from stakeholders"),
                ("2024-Q4", "good", "excellent", 83.0, "Slight dip due to Q4 staffing changes, still performing well"),
            ],
            "Our Company|TechStart Inc": [
                ("2024-Q1", "acceptable", None, 65.0, "New relationship, establishing baseline"),
                ("2024-Q2", "good", "acceptable", 72.0, "Improvement after onboarding phase"),
                ("2024-Q3", "good", "good", 77.0, "Consistent delivery, communication improving"),
                ("2024-Q4", "good", "good", 77.5, "Stable performance maintained"),
            ],
            "Our Company|GlobalSupply International": [
                ("2024-Q1", "excellent", None, 92.0, "Long-standing relationship, consistently high performance"),
                ("2024-Q2", "excellent", "excellent", 94.0, "Best-in-class logistics performance"),
                ("2024-Q3", "good", "excellent", 85.0, "Q3 supply chain disruptions impacted delivery timelines"),
                ("2024-Q4", "excellent", "good", 94.0, "Recovery to normal levels after supply chain stabilization"),
            ],
            "Our Company|CloudServices Pro": [
                ("2024-Q1", "good", None, 82.0, "Reliable cloud services, occasional latency issues"),
                ("2024-Q2", "excellent", "good", 90.0, "Infrastructure upgrades resolved previous issues"),
                ("2024-Q3", "excellent", "excellent", 91.0, "99.98% uptime achieved"),
                ("2024-Q4", "excellent", "excellent", 90.5, "Consistent excellence in service delivery"),
            ],
            "Our Company|Strategic Partners LLC": [
                ("2024-Q1", "acceptable", None, 68.0, "Project ramp-up phase, some resource alignment issues"),
                ("2024-Q2", "concerning", "acceptable", 58.0, "Missed deliverables on transformation project"),
                ("2024-Q3", "acceptable", "concerning", 70.0, "Recovery plan implemented, situation improving"),
                ("2024-Q4", "good", "acceptable", 75.0, "Turnaround successful, new project manager assigned"),
            ],
        }

        for rel_key, entries in history_data.items():
            if rel_key not in rels:
                continue
            rel = rels[rel_key]
            for period, status, prev_status, score, notes in entries:
                q = int(period.split("-Q")[1])
                recorded = datetime(2024, q * 3, 28)
                await db.execute(text("""
                    INSERT INTO relationship_status_history
                        (id, tenant_id, relationship_id, status, previous_status, overall_score, period, recorded_date, recorded_by, notes, trigger)
                    VALUES (:id, :tid, :rid, :status, :prev, :score, :period, :recorded, :uid, :notes, 'kpi_evaluation_cycle')
                """), {
                    "id": str(uuid4()), "tid": str(rel["tenant_id"]), "rid": str(rel["id"]),
                    "status": status, "prev": prev_status, "score": score, "period": period,
                    "recorded": recorded, "uid": str(admin_user_id), "notes": notes,
                })
                history_count += 1

        await db.commit()
        print(f"  Created {history_count} history entries across {len(history_data)} relationships")

        # ── Summary ───────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("Fit-gap seed data complete!")
        print(f"  Organization hierarchy: set for 6 orgs")
        print(f"  Organization officers: {officer_count}")
        print(f"  Service portfolio: {len(services)} services, {link_count} relationship links")
        print(f"  Contract documents: {doc_count} docs, {sig_count} signatures, {sec_count} sections")
        print(f"  KPI approvals: {approved} approved, {rejected} rejected, {pending} pending")
        print(f"  Relationship history: {history_count} entries")
        print("=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_fitgap())

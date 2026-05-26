import asyncio
from sqlalchemy import text
from app.database import engine, Base
import app.models.tenant, app.models.user, app.models.contract, app.models.clause, app.models.obligation
import app.models.sla, app.models.knowledge_graph, app.models.industry_profile, app.models.business_unit
import app.models.organization, app.models.relationship, app.models.processing_job, app.models.taxonomy_suggestion
import app.models.alert, app.models.approval, app.models.audit, app.models.chat_session, app.models.compliance_gap
import app.models.compliance_rule, app.models.contract_comment, app.models.contract_document, app.models.contract_link
import app.models.contract_share, app.models.definition, app.models.event, app.models.exhibit, app.models.external_access
import app.models.external_user, app.models.extraction_quality, app.models.financial, app.models.improvement, app.models.industry
import app.models.integration, app.models.key_date, app.models.kpi, app.models.master_data, app.models.metric_snapshot
import app.models.notification_rule, app.models.notification, app.models.organization_officer, app.models.party, app.models.preamble
import app.models.process_step, app.models.project_task, app.models.regulatory_obligation, app.models.relationship_history
import app.models.service_portfolio, app.models.sla_alert, app.models.snow_sla_mapping, app.models.suggested_link, app.models.survey, app.models.workflow

async def init():
    async with engine.begin() as conn:
        # Nuclear drop
        await conn.execute(text('DROP SCHEMA IF EXISTS public CASCADE'))
        await conn.execute(text('CREATE SCHEMA public'))
        await conn.execute(text('GRANT ALL ON SCHEMA public TO postgres'))
        await conn.execute(text('GRANT ALL ON SCHEMA public TO public'))
        
        # Helper to create enum if not exists
        async def create_enum(c, name, values):
            vals_str = ', '.join([f"'{v}'" for v in values])
            sql = f"""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{name}') THEN 
                    CREATE TYPE {name} AS ENUM ({vals_str}); 
                END IF; 
            END $$;
            """
            await c.execute(text(sql))

        # Create all known enums (fresh)
        await create_enum(conn, 'role', ['super_admin', 'admin', 'bu_head', 'legal', 'procurement', 'viewer'])

        await create_enum(conn, 'tenantplan', ['starter', 'professional', 'enterprise', 'strategic'])
        await create_enum(conn, 'contractstatus', ['pending', 'processing', 'completed', 'failed'])
        await create_enum(conn, 'risklevel', ['low', 'medium', 'high', 'critical'])
        await create_enum(conn, 'clausetype', ['indemnification', 'limitation_of_liability', 'termination', 'confidentiality', 'intellectual_property', 'payment_terms', 'warranty', 'force_majeure', 'non_compete', 'non_solicitation', 'data_protection', 'dispute_resolution', 'assignment', 'notice', 'governing_law', 'sla', 'auto_renewal', 'other'])
        await create_enum(conn, 'processingjobstatus', ['queued', 'processing', 'completed', 'failed', 'retrying', 'stuck'])
        await create_enum(conn, 'kgentitytype', ['party', 'clause', 'obligation', 'term', 'date', 'amount', 'jurisdiction', 'sla_metric'])
        await create_enum(conn, 'kgrelationshiptype', ['has_party', 'has_obligation', 'benefits_from', 'references', 'limited_by', 'defined_as', 'triggered_by', 'governed_by', 'amends', 'expires_on', 'same_as'])
        await create_enum(conn, 'surveyfrequency', ['one_time', 'monthly', 'quarterly', 'semi_annual', 'annual'])
        await create_enum(conn, 'surveystatus', ['draft', 'scheduled', 'sent', 'in_progress', 'completed', 'expired', 'cancelled'])
        await create_enum(conn, 'questiontype', ['rating', 'rating_5', 'multiple_choice', 'single_choice', 'text', 'text_long', 'yes_no', 'nps'])
        await create_enum(conn, 'organizationtype', ['customer', 'vendor', 'partner', 'internal'])
        await create_enum(conn, 'relationshiptype', ['customer', 'supplier', 'partner', 'joint_venture', 'reseller', 'distributor'])
        await create_enum(conn, 'relationshipstatus', ['prospecting', 'active', 'at_risk', 'on_hold', 'terminated'])
        await create_enum(conn, 'governancetier', ['operational', 'tactical', 'strategic', 'executive'])
        await create_enum(conn, 'slametrictype', ['uptime', 'latency', 'response_time', 'resolution_time', 'availability', 'quality', 'throughput', 'other'])
        await create_enum(conn, 'executionstatus', ['pending', 'running', 'success', 'failed', 'cancelled'])
        await create_enum(conn, 'approvalstatus', ['pending', 'approved', 'rejected', 'requested'])
        await create_enum(conn, 'eventtype', ['contract_upload', 'contract_process', 'contract_view', 'contract_delete', 'query_execute', 'agent_invoke', 'settings_update', 'login', 'logout', 'login_failed', 'user_create', 'user_update', 'user_delete'])
        await create_enum(conn, 'eventseverity', ['info', 'warning', 'critical'])
        await create_enum(conn, 'integrationsystem', ['servicenow', 'salesforce', 'sap', 'workday', 'jira', 'other'])
        await create_enum(conn, 'integrationstatus', ['healthy', 'degraded', 'unhealthy', 'unknown'])
        await create_enum(conn, 'improvementsource', ['perception_gap', 'sla_breach', 'review_meeting', 'customer_feedback', 'internal_audit', 'manual', 'contract_risk'])
        
        # New Enums from previous failure
        await create_enum(conn, 'organizationlevel', ['group', 'division', 'department', 'team', 'unit'])
        await create_enum(conn, 'organizationsize', ['startup', 'smb', 'mid_market', 'enterprise', 'global'])
        await create_enum(conn, 'officer_side', ['internal', 'external'])
        await create_enum(conn, 'documenttype', ['main_contract', 'amendment', 'exhibit', 'sow', 'sla', 'policy', 'other'])
        await create_enum(conn, 'signaturetype', ['digital', 'wet', 'none'])
        await create_enum(conn, 'signaturestatus', ['pending', 'signed', 'rejected', 'expired'])
        await create_enum(conn, 'performancestatus', ['excellent', 'good', 'acceptable', 'concerning', 'poor', 'critical'])
        await create_enum(conn, 'scoreapprovalstatus', ['draft', 'pending_approval', 'approved', 'rejected'])
        await create_enum(conn, 'alertcategory', ['sla_breach', 'sla_warning', 'sla_improvement', 'milestone_delayed', 'milestone_at_risk', 'fx_threshold', 'service_credit', 'contract_expiry', 'obligation_due'])
        await create_enum(conn, 'alertstatus', ['active', 'acknowledged', 'in_progress', 'resolved', 'dismissed', 'escalated'])
        await create_enum(conn, 'alertpriority', ['low', 'medium', 'high', 'critical'])
        await create_enum(conn, 'teamrole', ['relationship_manager', 'account_manager', 'executive_sponsor', 'technical_lead', 'operations_lead', 'finance_lead', 'member'])
        await create_enum(conn, 'kpimeasurementtype', ['percentage', 'number', 'currency', 'time_hours', 'time_days', 'rating', 'boolean'])
        await create_enum(conn, 'kpicategory', ['service_delivery', 'quality', 'timeliness', 'communication', 'innovation', 'cost_efficiency', 'compliance', 'satisfaction', 'other'])
        await create_enum(conn, 'gapseverity', ['minor', 'moderate', 'significant', 'critical'])
        await create_enum(conn, 'improvementpriority', ['low', 'medium', 'high', 'critical'])
        await create_enum(conn, 'improvementstatus', ['open', 'in_progress', 'blocked', 'completed', 'cancelled'])
        await create_enum(conn, 'actionstatus', ['todo', 'in_progress', 'completed', 'blocked', 'cancelled'])
        await create_enum(conn, 'tokentype', ['perception_scoring', 'survey_response', 'document_view', 'multi_purpose'])
        await create_enum(conn, 'suggestionstatus', ['pending', 'approved', 'rejected', 'expired'])
        await create_enum(conn, 'industry', ['it_services', 'manufacturing', 'healthcare', 'financial_services', 'retail', 'energy', 'telecom', 'other'])
        await create_enum(conn, 'compliancedocumenttype', ['certification', 'audit_report', 'policy', 'insurance', 'other'])
        await create_enum(conn, 'compliancegapseverity', ['low', 'medium', 'high', 'critical'])
        await create_enum(conn, 'compliancegapstatus', ['open', 'remediated', 'risk_accepted', 'false_positive'])
        await create_enum(conn, 'regulationtype', ['privacy', 'security', 'financial', 'labor', 'environmental', 'other'])
        await create_enum(conn, 'regulatoryobligationcategory', ['data_protection', 'security_controls', 'reporting', 'audit_rights', 'other'])
        await create_enum(conn, 'ruleeventtype', ['contract_expiry', 'renewal_notice', 'obligation_due', 'sla_breach', 'risk_detected'])
        await create_enum(conn, 'penaltytype', ['service_credit', 'monetary', 'termination', 'other'])
        await create_enum(conn, 'liabilitycaptype', ['fixed', 'percentage', 'uncapped', 'other'])
        await create_enum(conn, 'linktype', ['parent', 'child', 'amendment', 'referenced', 'replaces', 'supersedes'])
        await create_enum(conn, 'obligationowner', ['internal', 'external', 'joint'])
        await create_enum(conn, 'obligationcategory', ['service_delivery', 'financial', 'legal', 'compliance', 'reporting', 'other'])
        await create_enum(conn, 'obligationfrequency', ['one_time', 'recurring', 'ongoing'])
        await create_enum(conn, 'ragstatus', ['red', 'amber', 'green', 'na'])
        await create_enum(conn, 'feetype', ['fixed', 'recurring', 'usage_based', 'other'])
        await create_enum(conn, 'paymentterms', ['net_30', 'net_60', 'net_90', 'prepaid', 'other'])
        await create_enum(conn, 'slaunit', ['percentage', 'hours', 'days', 'number', 'other'])
        await create_enum(conn, 'slaseverity', ['critical', 'high', 'medium', 'low'])
        await create_enum(conn, 'breachseverity', ['minor', 'moderate', 'major', 'critical'])
        await create_enum(conn, 'exhibittype', ['schedule', 'exhibit', 'appendix', 'annexure', 'attachment', 'pricing', 'sow', 'other'])
        await create_enum(conn, 'servicetype', ['saas', 'professional_services', 'managed_services', 'hardware', 'other'])
        await create_enum(conn, 'servicestatus', ['active', 'retired', 'planned', 'other'])
        await create_enum(conn, 'governance_role_type', ['executive', 'strategic', 'tactical', 'operational'])
        await create_enum(conn, 'steptype', ['submission', 'review', 'testing', 'approval', 'delivery', 'certification', 'payment', 'reporting', 'renewal', 'other'])
        await create_enum(conn, 'stepstatus', ['pending', 'in_progress', 'completed', 'blocked'])
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(init())

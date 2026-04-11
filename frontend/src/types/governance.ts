// ============================================================================
// Relationship Governance Types
// ============================================================================

// Organization
export type OrgType = 'customer' | 'vendor' | 'partner' | 'internal'
export type OrgSize = 'startup' | 'smb' | 'mid_market' | 'enterprise' | 'global'

export interface Organization {
  id: string
  tenant_id: string
  name: string
  code: string
  org_type: OrgType
  industry: string | null
  size: OrgSize | null
  region: string | null
  country: string | null
  website: string | null
  address: string | null
  primary_contact_name: string | null
  primary_contact_email: string | null
  primary_contact_phone: string | null
  relationship_owner_id: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface OrganizationCreate {
  name: string
  code: string
  org_type: OrgType
  industry?: string
  size?: OrgSize
  region?: string
  country?: string
  website?: string
  address?: string
  primary_contact_name?: string
  primary_contact_email?: string
  primary_contact_phone?: string
  relationship_owner_id?: string
}

export interface OrganizationUpdate {
  name?: string
  org_type?: OrgType
  industry?: string
  size?: OrgSize
  region?: string
  country?: string
  website?: string
  address?: string
  primary_contact_name?: string
  primary_contact_email?: string
  primary_contact_phone?: string
  relationship_owner_id?: string
  is_active?: boolean
}

// Business Relationship
export type RelationshipType = 'customer' | 'supplier' | 'partner' | 'joint_venture' | 'reseller' | 'distributor'
export type RelationshipStatus = 'prospecting' | 'active' | 'at_risk' | 'on_hold' | 'terminated'
export type GovernanceTier = 'operational' | 'tactical' | 'strategic' | 'executive'
export type TeamRole = 'relationship_manager' | 'account_manager' | 'executive_sponsor' | 'technical_lead' | 'operations_lead' | 'finance_lead' | 'member'

export interface BusinessRelationship {
  id: string
  tenant_id: string
  org_a_id: string
  org_b_id: string
  org_a?: Organization
  org_b?: Organization
  name?: string
  relationship_type: RelationshipType
  status: RelationshipStatus
  governance_tier: GovernanceTier
  health_score: number
  start_date: string | null
  end_date: string | null
  description: string | null
  strategic_objectives: string | null
  annual_value: number | null
  currency: string | null
  contract_count?: number
  kpi_count?: number
  created_at: string
  updated_at: string
  team?: RelationshipTeamMember[]
}

export interface HealthScoreFactor {
  label: string
  score: number
  weight: number
  detail: string
}

export interface HealthScoreResponse {
  relationship_id: string
  health_score: number
  breakdown: {
    compliance_score: number | null
    sla_score: number | null
    perception_score: number | null
    improvement_score: number | null
    overall_score: number
    calculated_at: string
  }
  factors: Record<string, HealthScoreFactor | number> | null
}

export interface RelationshipCreate {
  org_a_id: string
  org_b_id: string
  relationship_type: RelationshipType
  governance_tier?: GovernanceTier
  start_date?: string
  description?: string
  strategic_objectives?: string
  annual_value?: number
  currency?: string
}

export interface RelationshipUpdate {
  relationship_type?: RelationshipType
  status?: RelationshipStatus
  governance_tier?: GovernanceTier
  description?: string
  strategic_objectives?: string
  annual_value?: number
  currency?: string
}

export interface RelationshipTeamMember {
  id: string
  relationship_id: string
  user_id: string
  user?: { id: string; username: string; full_name?: string; email: string; role: string }
  role: TeamRole
  responsibilities: string | null
  is_primary_contact: boolean
  receives_alerts: boolean
  assigned_at: string
}

export interface TeamMemberCreate {
  user_id: string
  role: TeamRole
  responsibilities?: string
  is_primary_contact?: boolean
  receives_alerts?: boolean
}

// KPI & Perception
export type KPICategory = 'service_delivery' | 'quality' | 'timeliness' | 'communication' | 'innovation' | 'cost_efficiency' | 'compliance' | 'satisfaction' | 'other'
export type MeasurementType = 'percentage' | 'number' | 'currency' | 'time_hours' | 'time_days' | 'rating' | 'boolean'
export type KPIFrequency = 'weekly' | 'monthly' | 'quarterly' | 'annual'
export type GapSeverity = 'critical' | 'significant' | 'moderate' | 'minor' | 'aligned'

export interface KPI {
  id: string
  tenant_id: string
  relationship_id: string
  name: string
  description: string | null
  category: KPICategory
  measurement_type: MeasurementType
  target_value: number | null
  current_value: number | null
  amber_threshold: number | null
  red_threshold: number | null
  weight: number
  frequency: KPIFrequency
  is_perception_based: boolean
  is_active: boolean
  created_at: string
  updated_at: string
  latest_internal_score?: number | null
  latest_external_score?: number | null
  latest_gap?: PerceptionGap | null
}

export interface KPICreate {
  relationship_id: string
  name: string
  description?: string
  category: KPICategory
  measurement_type?: MeasurementType
  target_value?: number
  amber_threshold?: number
  red_threshold?: number
  weight?: number
  frequency?: KPIFrequency
  is_perception_based?: boolean
}

export interface KPIUpdate {
  name?: string
  description?: string
  category?: KPICategory
  target_value?: number
  amber_threshold?: number
  red_threshold?: number
  weight?: number
  frequency?: KPIFrequency
  is_perception_based?: boolean
  is_active?: boolean
}

export interface PerceptionScore {
  id: string
  kpi_id: string
  perspective: 'internal' | 'external'
  score: number
  comments: string | null
  scored_by: string | null
  scorer_role: string | null
  period: string | null
  assessment_date: string
  created_at: string
}

export interface PerceptionScoreCreate {
  perspective: 'internal' | 'external'
  score: number
  comments?: string
  period?: string
}

export interface PerceptionGap {
  id: string
  kpi_id: string
  internal_score_avg: number
  external_score_avg: number
  gap_value: number
  severity: GapSeverity
  requires_action: boolean
  period: string | null
  calculated_at: string
  analysis_notes: string | null
}

export interface GapSummary {
  relationship_id: string
  total_kpis: number
  kpis_with_gaps: number
  critical_gaps: number
  significant_gaps: number
  moderate_gaps: number
  minor_gaps: number
  aligned: number
  avg_gap: number
  gaps: Array<{
    kpi_id: string
    kpi_name: string
    category: KPICategory
    gap: PerceptionGap
  }>
}

// Improvements
export type ImprovementPriority = 'low' | 'medium' | 'high' | 'critical'
export type ImprovementStatus = 'open' | 'in_progress' | 'blocked' | 'completed' | 'cancelled'
export type ImprovementSource = 'perception_gap' | 'sla_breach' | 'review_meeting' | 'customer_feedback' | 'internal_audit' | 'manual'
export type ActionStatus = 'todo' | 'in_progress' | 'completed' | 'blocked' | 'cancelled'

export interface ImprovementPoint {
  id: string
  tenant_id: string
  relationship_id: string
  kpi_id: string | null
  title: string
  description: string | null
  priority: ImprovementPriority
  status: ImprovementStatus
  source: ImprovementSource
  owner_id: string | null
  owner?: { id: string; username: string; full_name?: string }
  assigned_org_id: string | null
  target_date: string | null
  completed_date: string | null
  target_outcome: string | null
  actual_outcome: string | null
  impact_score: number | null
  progress: number
  created_at: string
  updated_at: string
  actions?: ImprovementAction[]
}

export interface ImprovementCreate {
  relationship_id: string
  kpi_id?: string
  title: string
  description?: string
  priority?: ImprovementPriority
  source?: ImprovementSource
  owner_id?: string
  target_date?: string
  target_outcome?: string
}

export interface ImprovementAction {
  id: string
  improvement_id: string
  title: string
  description: string | null
  status: ActionStatus
  owner_id: string | null
  due_date: string | null
  completed_date: string | null
  sequence: number
  blocker_reason: string | null
  created_at: string
}

export interface ImprovementActionCreate {
  title: string
  description?: string
  owner_id?: string
  due_date?: string
  sequence?: number
}

// Surveys
export type SurveyType = 'satisfaction' | 'performance' | 'relationship_health' | 'custom'
export type QuestionType = 'rating' | 'rating_5' | 'nps' | 'single_choice' | 'multiple_choice' | 'text' | 'text_long' | 'yes_no'
export type SurveyInstanceStatus = 'draft' | 'scheduled' | 'sent' | 'in_progress' | 'completed' | 'expired' | 'cancelled'

export interface SurveyTemplate {
  id: string
  tenant_id: string
  name: string
  description: string | null
  survey_type: SurveyType
  is_active: boolean
  is_anonymous: boolean
  frequency: string | null
  intro_text: string | null
  closing_text: string | null
  version: number
  created_at: string
  updated_at: string
  questions?: SurveyQuestion[]
  question_count?: number
}

export interface SurveyTemplateCreate {
  name: string
  description?: string
  survey_type?: SurveyType
  is_anonymous?: boolean
  frequency?: string
  intro_text?: string
  closing_text?: string
}

export interface SurveyQuestion {
  id: string
  template_id: string
  question_text: string
  question_type: QuestionType
  options: string[] | null
  display_order: number
  is_required: boolean
  category: string | null
  kpi_id: string | null
  rating_labels: Record<string, string> | null
}

export interface SurveyQuestionCreate {
  question_text: string
  question_type: QuestionType
  options?: string[]
  display_order?: number
  is_required?: boolean
  category?: string
  kpi_id?: string
  rating_labels?: Record<string, string>
}

export interface SurveyInstance {
  id: string
  template_id: string
  relationship_id: string
  title: string
  status: SurveyInstanceStatus
  period: string | null
  scheduled_send_date: string | null
  due_date: string | null
  target_respondents: number
  actual_respondents: number
  response_rate: number | null
  sent_at: string | null
  completed_at: string | null
  notes: string | null
  created_at: string
  updated_at: string
  template?: SurveyTemplate
}

export interface SurveyInstanceCreate {
  template_id: string
  relationship_id: string
  title: string
  period?: string
  due_date?: string
  target_respondents?: number
  notes?: string
}

export interface SurveyResponse {
  id: string
  instance_id: string
  respondent_name: string | null
  respondent_email: string | null
  respondent_org: string | null
  is_anonymous: boolean
  answers: Record<string, unknown>
  completion_time_seconds: number | null
  submitted_at: string
}

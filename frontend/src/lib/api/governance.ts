import { client } from './client'

// ============================================================================
// Relationship Governance: Organizations
// ============================================================================

export async function getOrganizations(params?: {
  org_type?: string
  search?: string
  active_only?: boolean
}): Promise<import('@/types/governance').Organization[]> {
  const response = await client.get('/organizations', { params })
  return response.data.items ?? response.data
}

export async function getOrganization(id: string): Promise<import('@/types/governance').Organization> {
  const response = await client.get(`/organizations/${id}`)
  return response.data
}

export async function createOrganization(data: import('@/types/governance').OrganizationCreate): Promise<import('@/types/governance').Organization> {
  const response = await client.post('/organizations', data)
  return response.data
}

export async function updateOrganization(id: string, data: import('@/types/governance').OrganizationUpdate): Promise<import('@/types/governance').Organization> {
  const response = await client.put(`/organizations/${id}`, data)
  return response.data
}

export async function deleteOrganization(id: string): Promise<void> {
  await client.delete(`/organizations/${id}`)
}

// ============================================================================
// Relationship Governance: Organization Hierarchy & Officers
// ============================================================================

export async function getOrganizationTree(): Promise<import('@/types/fitgap').OrganizationTreeNode[]> {
  const response = await client.get('/organizations/tree')
  return response.data
}

export async function getOrganizationSubsidiaries(orgId: string): Promise<import('@/types/governance').Organization[]> {
  const response = await client.get(`/organizations/${orgId}/subsidiaries`)
  return response.data
}

export async function getOrganizationHierarchy(orgId: string): Promise<import('@/types/fitgap').OrganizationHierarchy> {
  const response = await client.get(`/organizations/${orgId}/hierarchy`)
  return response.data
}

export async function getOrganizationOfficers(orgId: string, params?: {
  page?: number
  page_size?: number
  role?: string
  side?: string
  active_only?: boolean
}): Promise<{ items: import('@/types/fitgap').OrganizationOfficer[]; total: number }> {
  const response = await client.get(`/organizations/${orgId}/officers`, { params })
  return response.data
}

export async function createOfficer(orgId: string, data: import('@/types/fitgap').OfficerCreate): Promise<import('@/types/fitgap').OrganizationOfficer> {
  const response = await client.post(`/organizations/${orgId}/officers`, data)
  return response.data
}

export async function updateOfficer(orgId: string, officerId: string, data: import('@/types/fitgap').OfficerUpdate): Promise<import('@/types/fitgap').OrganizationOfficer> {
  const response = await client.put(`/organizations/${orgId}/officers/${officerId}`, data)
  return response.data
}

export async function deleteOfficer(orgId: string, officerId: string): Promise<void> {
  await client.delete(`/organizations/${orgId}/officers/${officerId}`)
}

// ============================================================================
// Relationship Governance: Relationships
// ============================================================================

export async function getRelationships(params?: {
  status?: string
  relationship_type?: string
}): Promise<import('@/types/governance').BusinessRelationship[]> {
  const response = await client.get('/relationships', { params })
  return response.data.items ?? response.data
}

export async function getRelationship(id: string): Promise<import('@/types/governance').BusinessRelationship> {
  const response = await client.get(`/relationships/${id}`)
  return response.data
}

export async function createRelationship(data: import('@/types/governance').RelationshipCreate): Promise<import('@/types/governance').BusinessRelationship> {
  const response = await client.post('/relationships', data)
  return response.data
}

export async function updateRelationship(id: string, data: import('@/types/governance').RelationshipUpdate): Promise<import('@/types/governance').BusinessRelationship> {
  const response = await client.put(`/relationships/${id}`, data)
  return response.data
}

export async function getRelationshipTeam(id: string): Promise<import('@/types/governance').RelationshipTeamMember[]> {
  const response = await client.get(`/relationships/${id}/team`)
  return response.data.items ?? response.data
}

export async function addTeamMember(relationshipId: string, data: import('@/types/governance').TeamMemberCreate): Promise<import('@/types/governance').RelationshipTeamMember> {
  const response = await client.post(`/relationships/${relationshipId}/team`, data)
  return response.data
}

export async function removeTeamMember(relationshipId: string, memberId: string): Promise<void> {
  await client.delete(`/relationships/${relationshipId}/team/${memberId}`)
}

export async function getRelationshipHealth(id: string): Promise<import('@/types/governance').HealthScoreResponse> {
  const response = await client.get(`/relationships/${id}/health`)
  return response.data
}

// ============================================================================
// Relationship Governance: KPIs & Perception
// ============================================================================

export async function getKPIs(params?: {
  relationship_id?: string
  category?: string
  active_only?: boolean
}): Promise<import('@/types/governance').KPI[]> {
  const response = await client.get('/kpis', { params })
  return response.data.items ?? response.data
}

export async function getKPI(id: string): Promise<import('@/types/governance').KPI> {
  const response = await client.get(`/kpis/${id}`)
  return response.data
}

export async function createKPI(data: import('@/types/governance').KPICreate): Promise<import('@/types/governance').KPI> {
  const response = await client.post('/kpis', data)
  return response.data
}

export async function updateKPI(id: string, data: import('@/types/governance').KPIUpdate): Promise<import('@/types/governance').KPI> {
  const response = await client.put(`/kpis/${id}`, data)
  return response.data
}

export async function deleteKPI(id: string): Promise<void> {
  await client.delete(`/kpis/${id}`)
}

export async function getPerceptionScores(kpiId: string): Promise<import('@/types/governance').PerceptionScore[]> {
  const response = await client.get(`/kpis/${kpiId}/scores`)
  return response.data
}

export async function submitPerceptionScore(kpiId: string, data: import('@/types/governance').PerceptionScoreCreate): Promise<import('@/types/governance').PerceptionScore> {
  const response = await client.post(`/kpis/${kpiId}/scores`, data)
  return response.data
}

export async function getPerceptionGaps(kpiId: string): Promise<import('@/types/governance').PerceptionGap[]> {
  const response = await client.get(`/kpis/${kpiId}/gaps`)
  return response.data
}

export async function getRelationshipGapSummary(relationshipId: string, period?: string): Promise<import('@/types/governance').GapSummary> {
  const response = await client.get(`/kpis/relationship/${relationshipId}/summary`, {
    params: period ? { period } : undefined
  })
  return response.data
}

// ============================================================================
// KPI Approval Workflow
// ============================================================================

export async function getPendingApprovals(filters?: { approval_status?: string; relationship_id?: string }): Promise<import('@/types/fitgap').PendingApproval[]> {
  const response = await client.get('/kpis/pending-approvals', { params: filters })
  return response.data
}

export async function approveScore(kpiId: string, scoreId: string, data?: { comments?: string }): Promise<unknown> {
  const response = await client.post(`/kpis/${kpiId}/scores/${scoreId}/approve`, data || {})
  return response.data
}

export async function rejectScore(kpiId: string, scoreId: string, data?: { comments?: string }): Promise<unknown> {
  const response = await client.post(`/kpis/${kpiId}/scores/${scoreId}/reject`, data || {})
  return response.data
}

export async function updateScore(kpiId: string, scoreId: string, data: { score?: number; comments?: string }): Promise<unknown> {
  const response = await client.put(`/kpis/${kpiId}/scores/${scoreId}`, data)
  return response.data
}

export async function deleteScore(kpiId: string, scoreId: string): Promise<void> {
  await client.delete(`/kpis/${kpiId}/scores/${scoreId}`)
}

// ============================================================================
// Relationship Governance: Improvements
// ============================================================================

export async function getImprovements(params?: {
  relationship_id?: string
  status?: string
  priority?: string
}): Promise<import('@/types/governance').ImprovementPoint[]> {
  const response = await client.get('/improvements', { params })
  return response.data.items ?? response.data
}

export async function getImprovement(id: string): Promise<import('@/types/governance').ImprovementPoint> {
  const response = await client.get(`/improvements/${id}`)
  return response.data
}

export async function createImprovement(data: import('@/types/governance').ImprovementCreate): Promise<import('@/types/governance').ImprovementPoint> {
  const response = await client.post('/improvements', data)
  return response.data
}

export async function updateImprovement(id: string, data: Partial<import('@/types/governance').ImprovementCreate> & { status?: string }): Promise<import('@/types/governance').ImprovementPoint> {
  const response = await client.put(`/improvements/${id}`, data)
  return response.data
}

export async function deleteImprovement(id: string): Promise<void> {
  await client.delete(`/improvements/${id}`)
}

export async function generateImprovementsFromGaps(relationshipId: string, minSeverity?: string): Promise<import('@/types/governance').ImprovementPoint[]> {
  const response = await client.post('/improvements/generate-from-gaps', {
    relationship_id: relationshipId,
    min_severity: minSeverity || 'significant',
  })
  return response.data
}

export async function getImprovementActions(improvementId: string): Promise<import('@/types/governance').ImprovementAction[]> {
  const response = await client.get(`/improvements/${improvementId}/actions`)
  return response.data
}

export async function createImprovementAction(improvementId: string, data: import('@/types/governance').ImprovementActionCreate): Promise<import('@/types/governance').ImprovementAction> {
  const response = await client.post(`/improvements/${improvementId}/actions`, data)
  return response.data
}

// ============================================================================
// Relationship Governance: Surveys
// ============================================================================

export async function getSurveyTemplates(): Promise<import('@/types/governance').SurveyTemplate[]> {
  const response = await client.get('/surveys/templates')
  return response.data.items ?? response.data
}

export async function getSurveyTemplate(id: string): Promise<import('@/types/governance').SurveyTemplate> {
  const response = await client.get(`/surveys/templates/${id}`)
  return response.data
}

export async function createSurveyTemplate(data: import('@/types/governance').SurveyTemplateCreate): Promise<import('@/types/governance').SurveyTemplate> {
  const response = await client.post('/surveys/templates', data)
  return response.data
}

export async function addSurveyQuestion(templateId: string, data: import('@/types/governance').SurveyQuestionCreate): Promise<import('@/types/governance').SurveyQuestion> {
  const response = await client.post(`/surveys/templates/${templateId}/questions`, data)
  return response.data
}

export async function getSurveyInstances(params?: {
  relationship_id?: string
  status?: string
}): Promise<import('@/types/governance').SurveyInstance[]> {
  const response = await client.get('/surveys/instances', { params })
  return response.data.items ?? response.data
}

export async function createSurveyInstance(data: import('@/types/governance').SurveyInstanceCreate): Promise<import('@/types/governance').SurveyInstance> {
  const response = await client.post('/surveys/instances', data)
  return response.data
}

export async function sendSurvey(instanceId: string): Promise<import('@/types/governance').SurveyInstance> {
  const response = await client.post(`/surveys/instances/${instanceId}/send`)
  return response.data
}

export async function getSurveyResponses(instanceId: string): Promise<import('@/types/governance').SurveyResponse[]> {
  const response = await client.get(`/surveys/instances/${instanceId}/responses`)
  return response.data
}

export async function generateSurveyToken(instanceId: string): Promise<{ token: string; url: string }> {
  const response = await client.post(`/surveys/instances/${instanceId}/generate-token`)
  return response.data
}

// ============================================================================
// Relationship Performance History
// ============================================================================

export async function getRelationshipHistory(relId: string, params?: {
  page?: number
  page_size?: number
}): Promise<{ items: import('@/types/fitgap').RelationshipHistoryEntry[]; total: number }> {
  const response = await client.get(`/relationships/${relId}/history`, { params })
  return response.data
}

export async function recordRelationshipStatus(relId: string, data: import('@/types/fitgap').RelationshipHistoryCreate): Promise<import('@/types/fitgap').RelationshipHistoryEntry> {
  const response = await client.post(`/relationships/${relId}/history`, data)
  return response.data
}

export async function getPerformanceTrend(relId: string, params?: {
  limit?: number
}): Promise<import('@/types/fitgap').PerformanceTrendResponse> {
  const response = await client.get(`/relationships/${relId}/performance-trend`, { params })
  return response.data
}

// ============================================================================
// Service Portfolio
// ============================================================================

export async function getServicePortfolios(params?: {
  page?: number
  page_size?: number
  search?: string
  org_id?: string
  service_type?: string
  service_status?: string
}): Promise<import('@/types/fitgap').ServicePortfolioListResponse> {
  const response = await client.get('/service-portfolio', { params })
  return response.data
}

export async function getServicePortfolio(id: string): Promise<import('@/types/fitgap').ServicePortfolio> {
  const response = await client.get(`/service-portfolio/${id}`)
  return response.data
}

export async function createServicePortfolio(data: import('@/types/fitgap').ServicePortfolioCreate): Promise<import('@/types/fitgap').ServicePortfolio> {
  const response = await client.post('/service-portfolio', data)
  return response.data
}

export async function updateServicePortfolio(id: string, data: import('@/types/fitgap').ServicePortfolioUpdate): Promise<import('@/types/fitgap').ServicePortfolio> {
  const response = await client.put(`/service-portfolio/${id}`, data)
  return response.data
}

export async function deleteServicePortfolio(id: string): Promise<void> {
  await client.delete(`/service-portfolio/${id}`)
}

export async function getServicesByOrganization(orgId: string): Promise<import('@/types/fitgap').ServicePortfolioListResponse> {
  const response = await client.get(`/service-portfolio/organization/${orgId}`)
  return response.data
}

export async function getServiceRelationships(serviceId: string): Promise<import('@/types/fitgap').RelationshipService[]> {
  const response = await client.get(`/service-portfolio/${serviceId}/relationships`)
  return response.data
}

export async function linkServiceToRelationship(serviceId: string, data: import('@/types/fitgap').RelationshipServiceCreate): Promise<import('@/types/fitgap').RelationshipService> {
  const response = await client.post(`/service-portfolio/${serviceId}/relationships`, data)
  return response.data
}

export async function unlinkServiceFromRelationship(serviceId: string, linkId: string): Promise<void> {
  await client.delete(`/service-portfolio/${serviceId}/relationships/${linkId}`)
}

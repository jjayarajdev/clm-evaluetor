import { client } from './client'
import type {
  QueryRequest,
  QueryResponse,
  ChatSession,
  ChatSessionDetail,
  ChatMessageOut,
} from '@/types'
import type {
  SnowConfig,
  SnowConfigCreate,
  SnowConnectionTest,
  SnowSyncResult,
  SnowSLAMapping,
  SnowAdminOverview,
  SnowIntegrationLog,
} from '@/types/snow-integration'

// ============================================================================
// Query endpoints
// ============================================================================

export async function query(request: QueryRequest): Promise<QueryResponse> {
  const response = await client.post<QueryResponse>('/query', request)
  return response.data
}

export async function getSuggestedQuestions(contractId?: string): Promise<{ questions: string[] }> {
  const response = await client.get('/query/suggestions', {
    params: { contract_id: contractId },
  })
  return response.data
}

// ============================================================================
// Chat session endpoints
// ============================================================================

export async function getChatSessions(): Promise<ChatSession[]> {
  const response = await client.get<ChatSession[]>('/chat/sessions')
  return response.data
}

export async function createChatSession(title?: string, contractId?: string): Promise<ChatSessionDetail> {
  const response = await client.post<ChatSessionDetail>('/chat/sessions', {
    title: title || 'New Chat',
    contract_id: contractId || null,
  })
  return response.data
}

export async function getChatSession(sessionId: string): Promise<ChatSessionDetail> {
  const response = await client.get<ChatSessionDetail>(`/chat/sessions/${sessionId}`)
  return response.data
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  await client.delete(`/chat/sessions/${sessionId}`)
}

export async function updateChatSessionTitle(sessionId: string, title: string): Promise<ChatSession> {
  const response = await client.patch<ChatSession>(`/chat/sessions/${sessionId}`, { title })
  return response.data
}

export async function addChatMessage(sessionId: string, message: {
  role: string
  content: string
  sources?: unknown[]
  follow_ups?: string[]
  visualizations?: unknown[]
}): Promise<ChatMessageOut> {
  const response = await client.post<ChatMessageOut>(
    `/chat/sessions/${sessionId}/messages`,
    message,
  )
  return response.data
}

export async function queryAnalyze(contractId: string, analysisType = 'full'): Promise<Record<string, unknown>> {
  const response = await client.post('/query/analyze', null, {
    params: { contract_id: contractId, analysis_type: analysisType },
  })
  return response.data
}

// ============================================================================
// ServiceNow Integration
// ============================================================================

export async function getSnowConfig(): Promise<SnowConfig | null> {
  const response = await client.get('/integrations/servicenow/config')
  return response.data
}

export async function saveSnowConfig(data: SnowConfigCreate): Promise<SnowConfig> {
  const response = await client.post('/integrations/servicenow/config', data)
  return response.data
}

export async function testSnowConnection(): Promise<SnowConnectionTest> {
  const response = await client.post('/integrations/servicenow/config/test')
  return response.data
}

export async function triggerSnowSync(): Promise<SnowSyncResult> {
  const response = await client.post('/integrations/servicenow/sync')
  return response.data
}

export async function getSnowMappings(): Promise<SnowSLAMapping[]> {
  const response = await client.get('/integrations/servicenow/mappings')
  return response.data
}

export async function updateSnowMapping(mappingId: string, data: { platform_sla_id?: string | null; mapping_status: string }): Promise<SnowSLAMapping> {
  const response = await client.put(`/integrations/servicenow/mappings/${mappingId}`, data)
  return response.data
}

export async function getSnowAdminOverview(): Promise<SnowAdminOverview[]> {
  const response = await client.get('/integrations/servicenow/admin/overview')
  return response.data
}

export async function getSnowIntegrationLogs(limit?: number): Promise<SnowIntegrationLog[]> {
  const response = await client.get('/integrations/servicenow/admin/logs', { params: { limit } })
  return response.data
}

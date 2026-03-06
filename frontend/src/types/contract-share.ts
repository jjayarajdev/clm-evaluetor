// Contract Share types

export interface ContractShareCreate {
  external_user_id: string
  can_download?: boolean
  can_comment?: boolean
  expires_in_days?: number
  message?: string
}

export interface ContractShareResponse {
  id: string
  contract_id: string
  external_user_id: string
  shared_by_id: string
  can_download: boolean
  can_comment: boolean
  expires_at?: string
  message?: string
  access_count: number
  last_access_at?: string
  is_revoked: boolean
  revoked_at?: string
  created_at: string
  updated_at: string
}

export interface ExternalUserSummary {
  id: string
  email: string
  full_name?: string
  company_name?: string
}

export interface ContractShareWithUser extends ContractShareResponse {
  external_user: ExternalUserSummary
}

export interface ContractShareListResponse {
  items: ContractShareWithUser[]
  total: number
}

export interface ShareInviteResponse {
  share: ContractShareResponse
  access_url: string
  token: string
}

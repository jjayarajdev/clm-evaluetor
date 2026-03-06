// Business Unit types

export interface BusinessUnit {
  id: string
  tenant_id: string
  name: string
  code: string
  description?: string
  parent_id?: string
  head_user_id?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface BusinessUnitTree {
  id: string
  name: string
  code: string
  description?: string
  is_active: boolean
  head_user_id?: string
  children: BusinessUnitTree[]
}

export interface BusinessUnitCreate {
  name: string
  code: string
  description?: string
  parent_id?: string
  head_user_id?: string
}

export interface BusinessUnitUpdate {
  name?: string
  code?: string
  description?: string
  parent_id?: string
  head_user_id?: string
  is_active?: boolean
}

export interface BusinessUnitListResponse {
  items: BusinessUnit[]
  total: number
  page: number
  page_size: number
  pages: number
}

// Business Unit types

export interface BusinessUnit {
  id: string
  tenant_id: string
  name: string
  code: string
  description?: string
  parent_id?: string
  head_user_id?: string
  industry_profile_id?: string
  effective_profile_name?: string
  is_active: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config_overrides?: Record<string, any> | null
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
  industry_profile_id?: string
  effective_profile_name?: string
  children: BusinessUnitTree[]
}

export interface BusinessUnitCreate {
  name: string
  code: string
  description?: string | null
  parent_id?: string | null
  head_user_id?: string | null
  industry_profile_id?: string | null
}

export interface BusinessUnitUpdate {
  name?: string
  code?: string
  // null = explicitly clear (undefined keys are dropped by axios and the
  // backend's exclude_unset treats them as "no change")
  description?: string | null
  parent_id?: string | null
  head_user_id?: string | null
  industry_profile_id?: string | null
  is_active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config_overrides?: Record<string, any>
}

export interface BusinessUnitListResponse {
  items: BusinessUnit[]
  total: number
  page: number
  page_size: number
  pages: number
}

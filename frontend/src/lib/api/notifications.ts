import { client } from './client'

export interface NotificationItem {
  id: string
  type: 'obligation' | 'renewal' | 'sla'
  severity: 'high' | 'medium' | 'low'
  label: string
  title: string
  subtitle: string
  contract_id: string
  link: string
  date: string
}

export interface NotificationFeed {
  count: number
  items: NotificationItem[]
}

/** Actionable notifications for the header bell (overdue obligations, expiring
 * contracts, active SLA alerts) — scoped to the current user's tenant. */
export async function getNotificationFeed(): Promise<NotificationFeed> {
  const response = await client.get<NotificationFeed>('/notifications/feed')
  return response.data
}

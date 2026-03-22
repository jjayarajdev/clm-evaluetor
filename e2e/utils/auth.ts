import { Page, expect, APIRequestContext } from '@playwright/test'
import { testUsers, pages, endpoints } from '../fixtures/test-data'

/**
 * Authentication utilities for E2E tests
 */

export type UserType = keyof typeof testUsers

/**
 * Login via UI
 */
export async function loginViaUI(page: Page, userType: UserType = 'admin') {
  const user = testUsers[userType]

  await page.goto(pages.login)
  await page.waitForLoadState('domcontentloaded')

  // Fill login form
  await page.fill('input[name="username"], input[type="text"]', user.username)
  await page.fill('input[name="password"], input[type="password"]', user.password)

  // Click login button and wait for navigation
  await Promise.all([
    page.waitForURL('**/dashboard', { timeout: 30000 }),
    page.click('button[type="submit"]'),
  ])

  // Wait for page to load
  await page.waitForLoadState('domcontentloaded')
}

/**
 * Login via API and store token
 */
export async function loginViaAPI(
  request: APIRequestContext,
  userType: UserType = 'admin'
): Promise<string> {
  const user = testUsers[userType]

  const response = await request.post(endpoints.auth.login, {
    data: {
      username: user.username,
      password: user.password,
    },
  })

  expect(response.ok()).toBeTruthy()

  const data = await response.json()
  return data.access_token
}

/**
 * Get authenticated API request context
 */
export async function getAuthenticatedContext(
  request: APIRequestContext,
  userType: UserType = 'admin'
) {
  const token = await loginViaAPI(request, userType)

  return {
    token,
    headers: {
      Authorization: `Bearer ${token}`,
    },
  }
}

/**
 * Logout via UI
 */
export async function logoutViaUI(page: Page) {
  // Click user menu
  await page.click('[data-testid="user-menu"], button:has-text("Logout")')

  // Click logout option
  await page.click('text=Logout, text=Sign out')

  // Wait for redirect to login
  await page.waitForURL('**/login')
}

/**
 * Check if user is logged in
 */
export async function isLoggedIn(page: Page): Promise<boolean> {
  try {
    await page.waitForSelector('text=Dashboard', { timeout: 2000 })
    return true
  } catch {
    return false
  }
}

/**
 * Get current user info from API
 */
export async function getCurrentUser(request: APIRequestContext, token: string) {
  const response = await request.get(endpoints.auth.me, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })

  if (response.ok()) {
    return await response.json()
  }
  return null
}

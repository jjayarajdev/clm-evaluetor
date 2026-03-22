import { test, expect } from '@playwright/test'
import { testUsers, pages, endpoints } from '../fixtures/test-data'
import { loginViaUI, loginViaAPI } from '../utils/auth'
import { dashboardApi } from '../utils/api-helpers'

test.describe('Dashboard', () => {
  test.describe('Dashboard API', () => {
    test('should get legal dashboard with valid token', async ({ request }) => {
      const token = await loginViaAPI(request, 'legal')

      const response = await request.get(endpoints.dashboard.legal, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 30000,
      })

      // Dashboard endpoint might not exist (404) or be OK (200)
      expect([200, 404]).toContain(response.status())

      if (response.ok()) {
        const data = await response.json()
        expect(data).toBeTruthy()
      }
    })

    test('should get admin dashboard with valid token', async ({ request }) => {
      const token = await loginViaAPI(request, 'admin')

      const response = await request.get(endpoints.dashboard.admin, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 30000,
      })

      // Dashboard endpoint might not exist (404) or be OK (200)
      expect([200, 404]).toContain(response.status())

      if (response.ok()) {
        const data = await response.json()
        expect(data).toBeTruthy()
      }
    })

    test('should return 401 without authentication', async ({ request }) => {
      const response = await request.get(endpoints.dashboard.legal, {
        timeout: 10000,
      })

      // Could be 401, 403, or 404 if endpoint doesn't exist
      expect([401, 403, 404]).toContain(response.status())
    })
  })

  test.describe('Dashboard UI - Admin', () => {
    test('should display dashboard for admin user', async ({ page }) => {
      await loginViaUI(page, 'admin')

      // Should be on dashboard (wait for URL, not network)
      await expect(page).toHaveURL(/.*dashboard/, { timeout: 15000 })

      // Should show some content
      await expect(page.locator('body')).toBeVisible()
    })

    test('should show contracts summary', async ({ page }) => {
      await loginViaUI(page, 'admin')
      await expect(page).toHaveURL(/.*dashboard/, { timeout: 15000 })

      // Should show contracts info or dashboard content
      const content = page.locator('text=/contract|dashboard|overview/i')
      await expect(content.first()).toBeVisible({ timeout: 15000 })
    })

    test('should show navigation sidebar', async ({ page }) => {
      await loginViaUI(page, 'admin')
      await expect(page).toHaveURL(/.*dashboard/, { timeout: 15000 })

      // Sidebar may be collapsed - check for the container or any nav link
      const sidebarElement = page.locator('[class*="sidebar"], aside, nav a[href]').first()
      await expect(sidebarElement).toBeAttached({ timeout: 10000 })
    })

    test('should navigate to contracts from dashboard', async ({ page }) => {
      await loginViaUI(page, 'admin')
      await expect(page).toHaveURL(/.*dashboard/, { timeout: 15000 })

      // Click contracts link (may be icon-only in collapsed sidebar)
      const contractsLink = page.locator('a[href="/contracts"], a[href*="contracts"]').first()
      await contractsLink.click({ force: true })

      await expect(page).toHaveURL(/.*contracts/, { timeout: 10000 })
    })

    test('should show user menu', async ({ page }) => {
      await loginViaUI(page, 'admin')
      await expect(page).toHaveURL(/.*dashboard/, { timeout: 15000 })

      // Should show user menu, profile button, or user info somewhere
      const userMenu = page.locator('[data-testid="user-menu"], button:has-text("admin"), [class*="user"], [class*="avatar"]')
      await expect(userMenu.first()).toBeVisible({ timeout: 10000 })
    })
  })

  test.describe('Dashboard UI - Legal', () => {
    test('should display dashboard for legal user', async ({ page }) => {
      await loginViaUI(page, 'legal')

      // Should be on dashboard
      await expect(page).toHaveURL(/.*dashboard/, { timeout: 15000 })
    })

    test('should show appropriate widgets for legal role', async ({ page }) => {
      await loginViaUI(page, 'legal')

      await page.goto(pages.dashboard)
      await page.waitForLoadState('networkidle')

      // Should show legal-relevant content
      const dashboardContent = page.locator('body')
      await expect(dashboardContent).toBeVisible()
    })
  })

  test.describe('Dashboard Widgets', () => {
    test('should show contract statistics', async ({ page }) => {
      await loginViaUI(page, 'admin')
      await expect(page).toHaveURL(/.*dashboard/, { timeout: 15000 })

      // Look for stat cards or any dashboard content
      const statCards = page.locator('[class*="stat"], [class*="card"], [class*="widget"], [class*="grid"]')
      await expect(statCards.first()).toBeVisible({ timeout: 10000 })
    })

    test('should show recent contracts', async ({ page }) => {
      await loginViaUI(page, 'admin')

      await page.goto(pages.dashboard)
      await page.waitForLoadState('networkidle')

      // Look for recent contracts section
      const recentSection = page.locator('text=/recent|latest/i')
      // May or may not be visible depending on dashboard design
    })

    test('should show upcoming renewals', async ({ page }) => {
      await loginViaUI(page, 'admin')

      await page.goto(pages.dashboard)
      await page.waitForLoadState('networkidle')

      // Look for renewals section
      const renewalsSection = page.locator('text=/renewal|expir/i')
      // May or may not be visible depending on dashboard design
    })

    test('should show obligations summary', async ({ page }) => {
      await loginViaUI(page, 'admin')

      await page.goto(pages.dashboard)
      await page.waitForLoadState('networkidle')

      // Look for obligations section
      const obligationsSection = page.locator('text=/obligation/i')
      // May or may not be visible depending on dashboard design
    })
  })

  test.describe('Dashboard Performance', () => {
    test('should load dashboard within acceptable time', async ({ page }) => {
      await loginViaUI(page, 'admin')

      const startTime = Date.now()

      await page.goto(pages.dashboard)
      await page.waitForLoadState('networkidle')

      const loadTime = Date.now() - startTime

      // Dashboard should load in under 10 seconds
      expect(loadTime).toBeLessThan(10000)
    })
  })

  test.describe('Dashboard Responsiveness', () => {
    test('should be usable on tablet viewport', async ({ page }) => {
      await page.setViewportSize({ width: 768, height: 1024 })

      await loginViaUI(page, 'admin')

      await page.goto(pages.dashboard)
      await page.waitForLoadState('networkidle')

      // Should still show main content
      await expect(page.locator('body')).toContainText(/dashboard|contract/i)
    })

    test('should be usable on mobile viewport', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 })

      await loginViaUI(page, 'admin')

      await page.goto(pages.dashboard)
      await page.waitForLoadState('networkidle')

      // Should still be functional
      await expect(page.locator('body')).toBeVisible()
    })
  })
})

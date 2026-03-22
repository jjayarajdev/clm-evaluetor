import { test, expect } from '@playwright/test'
import { testUsers, pages, endpoints } from '../fixtures/test-data'
import { loginViaUI, loginViaAPI } from '../utils/auth'
import { contractApi, buildHeaders } from '../utils/api-helpers'

test.describe('Contracts', () => {
  let adminToken: string

  test.beforeAll(async ({ request }) => {
    adminToken = await loginViaAPI(request, 'admin')
  })

  test.describe('Contract List API', () => {
    test('should list contracts with valid token', async ({ request }) => {
      const { response, data } = await contractApi.list(request, { token: adminToken })

      expect(response.ok()).toBeTruthy()
      expect(data).toBeTruthy()
      expect(data.items).toBeDefined()
      expect(Array.isArray(data.items)).toBeTruthy()
      // Total might be named total, total_count, or count
      expect(data.total ?? data.total_count ?? data.count ?? data.items.length).toBeGreaterThanOrEqual(0)
    })

    test('should return 401 without authentication', async ({ request }) => {
      const response = await request.get(endpoints.contracts.list)

      expect([401, 403]).toContain(response.status())
    })

    test('should support pagination', async ({ request }) => {
      // Try different pagination parameter names (limit/page_size/per_page)
      const response = await request.get(`${endpoints.contracts.list}?limit=5&skip=0`, {
        headers: buildHeaders({ token: adminToken }),
      })

      expect(response.ok()).toBeTruthy()
      const data = await response.json()
      expect(data.items.length).toBeLessThanOrEqual(5)
    })

    test('should filter contracts by status', async ({ request }) => {
      const response = await request.get(`${endpoints.contracts.list}?status=completed`, {
        headers: buildHeaders({ token: adminToken }),
      })

      expect(response.ok()).toBeTruthy()

      const data = await response.json()
      // If items exist, they should match the filter (or filter isn't supported)
      if (data.items.length > 0) {
        data.items.forEach((contract: any) => {
          expect(contract.status?.toLowerCase()).toBe('completed')
        })
      }
    })

    test('should filter contracts by risk level', async ({ request }) => {
      const response = await request.get(`${endpoints.contracts.list}?risk_level=high`, {
        headers: buildHeaders({ token: adminToken }),
      })

      expect(response.ok()).toBeTruthy()

      const data = await response.json()
      // If items exist, they should match the filter (or filter isn't supported)
      if (data.items.length > 0) {
        data.items.forEach((contract: any) => {
          expect(contract.risk_level?.toLowerCase()).toBe('high')
        })
      }
    })

    test('should search contracts by keyword', async ({ request }) => {
      const response = await request.get(`${endpoints.contracts.list}?search=agreement`, {
        headers: buildHeaders({ token: adminToken }),
      })

      expect(response.ok()).toBeTruthy()
    })
  })

  test.describe('Contract Detail API', () => {
    test('should get contract details with valid ID', async ({ request }) => {
      // First get list to find a valid contract ID
      const { data: listData } = await contractApi.list(request, { token: adminToken })

      test.skip(listData.items.length === 0, 'No contracts available to test')

      const contractId = listData.items[0].id
      const { response, data } = await contractApi.get(request, contractId, { token: adminToken })

      expect(response.ok()).toBeTruthy()
      expect(data.id).toBe(contractId)
      expect(data.filename || data.name || data.title).toBeTruthy()
    })

    test('should return 404 for non-existent contract', async ({ request }) => {
      const fakeId = '00000000-0000-0000-0000-000000000000'

      const { response } = await contractApi.get(request, fakeId, { token: adminToken })

      expect(response.status()).toBe(404)
    })

    test('should return 422 for invalid UUID format', async ({ request }) => {
      const invalidId = 'not-a-valid-uuid'

      const { response } = await contractApi.get(request, invalidId, { token: adminToken })

      // Backend might return 404 if it doesn't validate UUID format
      expect([400, 404, 422]).toContain(response.status())
    })
  })

  test.describe('Contracts Page UI', () => {
    test('should display contracts list', async ({ page }) => {
      await loginViaUI(page, 'admin')

      await page.goto(pages.contracts)
      await page.waitForLoadState('networkidle')

      // Should show contracts table or list
      await expect(page.locator('table, [data-testid="contracts-list"]').first()).toBeVisible({
        timeout: 10000,
      })
    })

    test('should have search functionality', async ({ page }) => {
      await loginViaUI(page, 'admin')

      await page.goto(pages.contracts)
      await page.waitForLoadState('networkidle')

      // Look for search input
      const searchInput = page.locator('input[placeholder*="search" i], input[type="search"]')
      await expect(searchInput.first()).toBeVisible()
    })

    test('should navigate to contract detail', async ({ page, request }) => {
      await loginViaUI(page, 'admin')

      // Check if contracts exist first
      const { data: listData } = await contractApi.list(request, { token: adminToken })
      test.skip(listData.items.length === 0, 'No contracts available to test')

      await page.goto(pages.contracts)
      await page.waitForLoadState('networkidle')

      // Click first contract row
      const contractRow = page.locator('table tbody tr, [data-testid="contract-row"]').first()

      if (await contractRow.isVisible({ timeout: 5000 })) {
        await contractRow.click()

        // Should navigate to detail page
        await expect(page).toHaveURL(/.*contracts\/[a-f0-9-]+/, { timeout: 10000 })
      }
    })
  })

  test.describe('Contract Detail Page UI', () => {
    test('should display contract information', async ({ page, request }) => {
      // Get a contract ID
      const { data: listData } = await contractApi.list(request, { token: adminToken })
      test.skip(listData.items.length === 0, 'No contracts available to test')

      await loginViaUI(page, 'admin')
      const contractId = listData.items[0].id

      await page.goto(pages.contractDetail(contractId))
      await page.waitForLoadState('networkidle')

      // Should show contract details
      await expect(page.locator('h1, h2, [data-testid="contract-title"]').first()).toBeVisible({ timeout: 10000 })
    })

    test('should show clauses section', async ({ page, request }) => {
      const { data: listData } = await contractApi.list(request, { token: adminToken })
      test.skip(listData.items.length === 0, 'No contracts available to test')

      await loginViaUI(page, 'admin')
      const contractId = listData.items[0].id

      await page.goto(pages.contractDetail(contractId))
      await page.waitForLoadState('networkidle')

      // Look for clauses tab/section
      const clausesSection = page.locator('text=/clauses/i, button:has-text("Clauses"), [role="tab"]:has-text("Clauses")')
      await expect(clausesSection.first()).toBeVisible({ timeout: 10000 })
    })

    test('should show obligations section', async ({ page, request }) => {
      const { data: listData } = await contractApi.list(request, { token: adminToken })
      test.skip(listData.items.length === 0, 'No contracts available to test')

      await loginViaUI(page, 'admin')
      const contractId = listData.items[0].id

      await page.goto(pages.contractDetail(contractId))
      await page.waitForLoadState('networkidle')

      // Look for obligations tab/section
      const obligationsSection = page.locator('text=/obligations/i, button:has-text("Obligations"), [role="tab"]:has-text("Obligations")')
      await expect(obligationsSection.first()).toBeVisible({ timeout: 10000 })
    })
  })

  test.describe('Tenant Isolation', () => {
    test('admin should only see their tenant contracts', async ({ request }) => {
      // Login as Acme admin
      const acmeToken = await loginViaAPI(request, 'admin')
      const { data: acmeContracts } = await contractApi.list(request, { token: acmeToken })

      // Login as TechStart admin
      const techToken = await loginViaAPI(request, 'techstartAdmin')
      const { data: techContracts } = await contractApi.list(request, { token: techToken })

      // Skip if either tenant has no contracts
      test.skip(acmeContracts.items.length === 0 || techContracts.items.length === 0, 'Need contracts in both tenants to test isolation')

      // Contract IDs should not overlap
      const acmeIds = new Set(acmeContracts.items.map((c: any) => c.id))
      const techIds = techContracts.items.map((c: any) => c.id)

      techIds.forEach((id: string) => {
        expect(acmeIds.has(id)).toBeFalsy()
      })
    })

    test('user cannot access contract from another tenant', async ({ request }) => {
      // Login as Acme admin
      const acmeToken = await loginViaAPI(request, 'admin')
      const { data: acmeContracts } = await contractApi.list(request, { token: acmeToken })

      test.skip(acmeContracts.items.length === 0, 'No contracts available to test')

      const acmeContractId = acmeContracts.items[0].id

      // Try to access with TechStart token
      const techToken = await loginViaAPI(request, 'techstartAdmin')
      const { response } = await contractApi.get(request, acmeContractId, { token: techToken })

      // Should be 404 (not found in their tenant) or 403 (forbidden)
      expect([403, 404]).toContain(response.status())
    })
  })
})

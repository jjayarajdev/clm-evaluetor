import { test, expect } from '@playwright/test'
import { testUsers, pages, businessUnits } from '../fixtures/test-data'
import { loginViaUI, loginViaAPI } from '../utils/auth'
import { businessUnitApi } from '../utils/api-helpers'

test.describe('Business Units', () => {
  let adminToken: string
  let createdBuId: string | null = null

  test.beforeAll(async ({ request }) => {
    adminToken = await loginViaAPI(request, 'admin')
  })

  test.afterAll(async ({ request }) => {
    // Clean up created business unit
    if (createdBuId) {
      await businessUnitApi.delete(request, createdBuId, { token: adminToken })
    }
  })

  test.describe('Business Unit API', () => {
    test('should list business units with valid token', async ({ request }) => {
      const { response, data } = await businessUnitApi.list(request, { token: adminToken })

      expect(response.ok()).toBeTruthy()
      expect(data).toBeTruthy()
      expect(data.items).toBeDefined()
      expect(Array.isArray(data.items)).toBeTruthy()
    })

    test('should return 401 without authentication', async ({ request }) => {
      const { response } = await businessUnitApi.list(request)

      expect([401, 403]).toContain(response.status())
    })

    test('should create business unit', async ({ request }) => {
      const uniqueCode = `TEST${Date.now()}`

      const { response, data } = await businessUnitApi.create(
        request,
        {
          name: 'Test Business Unit',
          code: uniqueCode,
          description: 'Created by E2E test',
        },
        { token: adminToken }
      )

      expect(response.ok()).toBeTruthy()
      expect(data.name).toBe('Test Business Unit')
      expect(data.code).toBe(uniqueCode)
      expect(data.id).toBeTruthy()

      createdBuId = data.id
    })

    test('should get business unit by ID', async ({ request }) => {
      // First get list to find a valid BU ID
      const { data: listData } = await businessUnitApi.list(request, { token: adminToken })

      test.skip(!listData?.items?.length, 'No business units available to test')

      const buId = listData.items[0].id
      const { response, data } = await businessUnitApi.get(request, buId, { token: adminToken })

      expect(response.ok()).toBeTruthy()
      expect(data.id).toBe(buId)
      expect(data.name).toBeTruthy()
      expect(data.code).toBeTruthy()
    })

    test('should update business unit', async ({ request }) => {
      // Create a BU to update
      const uniqueCode = `UPD${Date.now()}`

      const { data: createData } = await businessUnitApi.create(
        request,
        {
          name: 'BU To Update',
          code: uniqueCode,
        },
        { token: adminToken }
      )

      const buId = createData.id

      // Update it
      const { response, data } = await businessUnitApi.update(
        request,
        buId,
        {
          name: 'Updated BU Name',
          description: 'Updated description',
        },
        { token: adminToken }
      )

      expect(response.ok()).toBeTruthy()
      expect(data.name).toBe('Updated BU Name')

      // Clean up
      await businessUnitApi.delete(request, buId, { token: adminToken })
    })

    test('should delete/deactivate business unit', async ({ request }) => {
      // Create a BU to delete
      const uniqueCode = `DEL${Date.now()}`

      const { data: createData } = await businessUnitApi.create(
        request,
        {
          name: 'BU To Delete',
          code: uniqueCode,
        },
        { token: adminToken }
      )

      const buId = createData.id

      // Delete it
      const { response } = await businessUnitApi.delete(request, buId, { token: adminToken })

      expect(response.ok()).toBeTruthy()
    })

    test('should return 404 for non-existent business unit', async ({ request }) => {
      const fakeId = '00000000-0000-0000-0000-000000000000'

      const { response } = await businessUnitApi.get(request, fakeId, { token: adminToken })

      expect(response.status()).toBe(404)
    })

    test('should prevent duplicate codes', async ({ request }) => {
      const uniqueCode = `DUP${Date.now()}`

      // Create first BU
      const { data: firstBu } = await businessUnitApi.create(
        request,
        {
          name: 'First BU',
          code: uniqueCode,
        },
        { token: adminToken }
      )

      // Try to create with same code
      const { response } = await businessUnitApi.create(
        request,
        {
          name: 'Second BU',
          code: uniqueCode,
        },
        { token: adminToken }
      )

      expect([400, 409, 422]).toContain(response.status())

      // Clean up
      await businessUnitApi.delete(request, firstBu.id, { token: adminToken })
    })
  })

  test.describe('Business Units Page UI', () => {
    test('should display business units list', async ({ page }) => {
      await loginViaUI(page, 'admin')

      await page.goto(pages.admin.businessUnits)
      await page.waitForLoadState('networkidle')

      // Should show business units page
      await expect(page.locator('text=/business unit/i').first()).toBeVisible({ timeout: 10000 })
    })

    test('should open create modal', async ({ page }) => {
      await loginViaUI(page, 'admin')

      await page.goto(pages.admin.businessUnits)
      await page.waitForLoadState('networkidle')

      // Click add button
      const addButton = page.locator('button:has-text("Add"), button:has-text("Create")')
      await addButton.first().click()

      // Should show modal
      await expect(page.locator('[role="dialog"], .modal')).toBeVisible({ timeout: 5000 })
    })

    test('should validate required fields on create', async ({ page }) => {
      await loginViaUI(page, 'admin')

      await page.goto(pages.admin.businessUnits)
      await page.waitForLoadState('networkidle')

      // Click add button
      const addButton = page.locator('button:has-text("Add"), button:has-text("Create")')
      await addButton.first().click()

      // Try to submit empty form
      const submitButton = page.locator('button[type="submit"], button:has-text("Save")')
      await submitButton.click()

      // Should show validation errors or stay on form
      await expect(page.locator('[role="dialog"], .modal')).toBeVisible()
    })
  })

  test.describe('Super Admin Access', () => {
    test('super admin should be able to view business units of any tenant', async ({ request }) => {
      const superAdminToken = await loginViaAPI(request, 'superAdmin')

      // Get list of tenants
      const tenantsResponse = await request.get('/api/tenants', {
        headers: {
          Authorization: `Bearer ${superAdminToken}`,
        },
      })

      if (tenantsResponse.ok()) {
        const tenantsData = await tenantsResponse.json()

        if (tenantsData.items && tenantsData.items.length > 0) {
          const tenantId = tenantsData.items[0].id

          // Get BUs for that tenant
          const { response } = await businessUnitApi.list(request, {
            token: superAdminToken,
            tenantId,
          })

          expect(response.ok()).toBeTruthy()
        }
      }
    })
  })
})

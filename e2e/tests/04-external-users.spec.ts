import { test, expect } from '@playwright/test'
import { testUsers, pages, externalUsers } from '../fixtures/test-data'
import { loginViaUI, loginViaAPI } from '../utils/auth'
import { externalUserApi } from '../utils/api-helpers'

test.describe('External Users', () => {
  let adminToken: string
  let createdUserId: string | null = null

  test.beforeAll(async ({ request }) => {
    adminToken = await loginViaAPI(request, 'admin')
  })

  test.afterAll(async ({ request }) => {
    // Clean up created external user
    if (createdUserId) {
      await externalUserApi.delete(request, createdUserId, { token: adminToken })
    }
  })

  test.describe('External User API', () => {
    test('should list external users with valid token', async ({ request }) => {
      const { response, data } = await externalUserApi.list(request, { token: adminToken })

      expect(response.ok()).toBeTruthy()
      expect(data).toBeTruthy()
      expect(data.items).toBeDefined()
      expect(Array.isArray(data.items)).toBeTruthy()
    })

    test('should return 401 without authentication', async ({ request }) => {
      const { response } = await externalUserApi.list(request)

      expect([401, 403]).toContain(response.status())
    })

    test('should create external user', async ({ request }) => {
      const uniqueEmail = `test${Date.now()}@external.com`

      const { response, data } = await externalUserApi.create(
        request,
        {
          email: uniqueEmail,
          full_name: 'Test External User',
          company_name: 'Test Company',
          title: 'Contract Manager',
          phone: '+1-555-0100',
        },
        { token: adminToken }
      )

      expect(response.ok()).toBeTruthy()
      expect(data.email).toBe(uniqueEmail)
      expect(data.full_name).toBe('Test External User')
      expect(data.company_name).toBe('Test Company')
      expect(data.id).toBeTruthy()

      createdUserId = data.id
    })

    test('should get external user by ID', async ({ request }) => {
      const { data: listData } = await externalUserApi.list(request, { token: adminToken })

      if (listData.items.length > 0) {
        const userId = listData.items[0].id

        const { response, data } = await externalUserApi.get(request, userId, { token: adminToken })

        expect(response.ok()).toBeTruthy()
        expect(data.id).toBe(userId)
        expect(data.email).toBeTruthy()
      }
    })

    test('should update external user', async ({ request }) => {
      // Create user to update
      const uniqueEmail = `update${Date.now()}@external.com`

      const { data: createData } = await externalUserApi.create(
        request,
        {
          email: uniqueEmail,
          full_name: 'User To Update',
        },
        { token: adminToken }
      )

      const userId = createData.id

      // Update it
      const { response, data } = await externalUserApi.update(
        request,
        userId,
        {
          full_name: 'Updated Name',
          company_name: 'Updated Company',
        },
        { token: adminToken }
      )

      expect(response.ok()).toBeTruthy()
      expect(data.full_name).toBe('Updated Name')
      expect(data.company_name).toBe('Updated Company')

      // Clean up
      await externalUserApi.delete(request, userId, { token: adminToken })
    })

    test('should update external user email', async ({ request }) => {
      // Create user
      const originalEmail = `original${Date.now()}@external.com`
      const newEmail = `new${Date.now()}@external.com`

      const { data: createData } = await externalUserApi.create(
        request,
        {
          email: originalEmail,
          full_name: 'Email Update Test',
        },
        { token: adminToken }
      )

      const userId = createData.id

      // Update email
      const { response, data } = await externalUserApi.update(
        request,
        userId,
        {
          email: newEmail,
        },
        { token: adminToken }
      )

      expect(response.ok()).toBeTruthy()
      expect(data.email).toBe(newEmail)

      // Clean up
      await externalUserApi.delete(request, userId, { token: adminToken })
    })

    test('should delete/deactivate external user', async ({ request }) => {
      const uniqueEmail = `delete${Date.now()}@external.com`

      const { data: createData } = await externalUserApi.create(
        request,
        {
          email: uniqueEmail,
          full_name: 'User To Delete',
        },
        { token: adminToken }
      )

      const userId = createData.id

      const { response } = await externalUserApi.delete(request, userId, { token: adminToken })

      expect(response.ok()).toBeTruthy()
    })

    test('should return 404 for non-existent external user', async ({ request }) => {
      const fakeId = '00000000-0000-0000-0000-000000000000'

      const { response } = await externalUserApi.get(request, fakeId, { token: adminToken })

      expect(response.status()).toBe(404)
    })

    test('should validate email format', async ({ request }) => {
      const { response } = await externalUserApi.create(
        request,
        {
          email: 'not-a-valid-email',
          full_name: 'Test User',
        },
        { token: adminToken }
      )

      expect([400, 422]).toContain(response.status())
    })

    test('should prevent duplicate emails', async ({ request }) => {
      const uniqueEmail = `dup${Date.now()}@external.com`

      // Create first user
      const { data: firstUser } = await externalUserApi.create(
        request,
        {
          email: uniqueEmail,
          full_name: 'First User',
        },
        { token: adminToken }
      )

      // Try to create with same email
      const { response } = await externalUserApi.create(
        request,
        {
          email: uniqueEmail,
          full_name: 'Second User',
        },
        { token: adminToken }
      )

      expect([400, 409, 422]).toContain(response.status())

      // Clean up
      await externalUserApi.delete(request, firstUser.id, { token: adminToken })
    })
  })

  test.describe('External Users Page UI', () => {
    test('should display external users list', async ({ page }) => {
      await loginViaUI(page, 'admin')

      await page.goto(pages.admin.externalUsers)
      await page.waitForLoadState('networkidle')

      // Should show external users page
      await expect(page.locator('text=/external user/i').first()).toBeVisible({ timeout: 10000 })
    })

    test('should open create modal', async ({ page }) => {
      await loginViaUI(page, 'admin')

      await page.goto(pages.admin.externalUsers)
      await page.waitForLoadState('networkidle')

      // Click add button
      const addButton = page.locator('button:has-text("Add"), button:has-text("Create")')
      await addButton.first().click()

      // Should show modal
      await expect(page.locator('[role="dialog"], .modal, form')).toBeVisible({ timeout: 5000 })
    })

    test('should search external users', async ({ page }) => {
      await loginViaUI(page, 'admin')

      await page.goto(pages.admin.externalUsers)
      await page.waitForLoadState('networkidle')

      // Find search input
      const searchInput = page.locator('input[placeholder*="search" i], input[type="search"]')

      if (await searchInput.first().isVisible()) {
        await searchInput.first().fill('test')

        // Wait for search to apply
        await page.waitForTimeout(500)
      }
    })

    test('should show edit modal when clicking edit button', async ({ page }) => {
      await loginViaUI(page, 'admin')

      await page.goto(pages.admin.externalUsers)
      await page.waitForLoadState('networkidle')

      // Find edit button
      const editButton = page.locator('button[title="Edit"], button:has-text("Edit")').first()

      if (await editButton.isVisible()) {
        await editButton.click()

        // Should show modal with form
        await expect(page.locator('[role="dialog"], .modal, form')).toBeVisible({ timeout: 5000 })
      }
    })
  })

  test.describe('External User Access Validation', () => {
    test('should require email when creating', async ({ request }) => {
      const { response } = await externalUserApi.create(
        request,
        {
          full_name: 'No Email User',
        } as any,
        { token: adminToken }
      )

      expect([400, 422]).toContain(response.status())
    })
  })
})

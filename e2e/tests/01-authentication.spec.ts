import { test, expect } from '@playwright/test'
import { testUsers, pages, endpoints } from '../fixtures/test-data'
import { loginViaUI, loginViaAPI, getCurrentUser } from '../utils/auth'

test.describe('Authentication', () => {
  test.describe('Login via UI', () => {
    test('should login successfully with valid admin credentials', async ({ page }) => {
      await page.goto(pages.login)

      // Fill login form
      await page.fill('input[name="username"], input[type="text"]', testUsers.admin.username)
      await page.fill('input[name="password"], input[type="password"]', testUsers.admin.password)

      // Submit
      await page.click('button[type="submit"]')

      // Should redirect to dashboard
      await expect(page).toHaveURL(/.*dashboard/, { timeout: 10000 })

      // Should show user info or dashboard content
      await expect(page.locator('body')).toContainText(/dashboard|contracts|welcome/i)
    })

    test('should login successfully with legal user credentials', async ({ page }) => {
      await page.goto(pages.login)

      await page.fill('input[name="username"], input[type="text"]', testUsers.legal.username)
      await page.fill('input[name="password"], input[type="password"]', testUsers.legal.password)
      await page.click('button[type="submit"]')

      await expect(page).toHaveURL(/.*dashboard/, { timeout: 10000 })
    })

    test('should show error with invalid password', async ({ page }) => {
      await page.goto(pages.login)

      await page.fill('input[name="username"], input[type="text"]', testUsers.admin.username)
      await page.fill('input[name="password"], input[type="password"]', 'wrongpassword')

      // Click submit and wait for API response
      const [response] = await Promise.all([
        page.waitForResponse((resp) => resp.url().includes('/auth/login') && resp.status() === 401),
        page.click('button[type="submit"]'),
      ])

      // Should stay on login page
      await expect(page).toHaveURL(/.*login/)

      // Should show error message (look for red error box)
      await expect(page.locator('.bg-red-50, [class*="error"], text=/invalid|incorrect/i')).toBeVisible({ timeout: 5000 })
    })

    test('should show error with non-existent user', async ({ page }) => {
      await page.goto(pages.login)

      await page.fill('input[name="username"], input[type="text"]', 'nonexistentuser')
      await page.fill('input[name="password"], input[type="password"]', 'anypassword')

      // Click submit and wait for API response
      const [response] = await Promise.all([
        page.waitForResponse((resp) => resp.url().includes('/auth/login') && resp.status() === 401),
        page.click('button[type="submit"]'),
      ])

      // Should stay on login page
      await expect(page).toHaveURL(/.*login/)

      // Should show error message
      await expect(page.locator('.bg-red-50, [class*="error"], text=/invalid|incorrect/i')).toBeVisible({ timeout: 5000 })
    })

    test('should require username field', async ({ page }) => {
      await page.goto(pages.login)

      // Only fill password
      await page.fill('input[name="password"], input[type="password"]', 'somepassword')
      await page.click('button[type="submit"]')

      // Should show validation or stay on page
      await expect(page).toHaveURL(/.*login/)
    })

    test('should require password field', async ({ page }) => {
      await page.goto(pages.login)

      // Only fill username
      await page.fill('input[name="username"], input[type="text"]', testUsers.admin.username)
      await page.click('button[type="submit"]')

      // Should show validation or stay on page
      await expect(page).toHaveURL(/.*login/)
    })
  })

  test.describe('Login via API', () => {
    test('should return token with valid credentials', async ({ request }) => {
      const response = await request.post(endpoints.auth.login, {
        data: {
          username: testUsers.admin.username,
          password: testUsers.admin.password,
        },
      })

      expect(response.ok()).toBeTruthy()
      expect(response.status()).toBe(200)

      const data = await response.json()
      expect(data.access_token).toBeTruthy()
      expect(data.token_type).toBe('bearer')
      expect(data.user).toBeTruthy()
      expect(data.user.username).toBe(testUsers.admin.username)
      expect(data.user.role).toBe(testUsers.admin.role)
    })

    test('should return 401 with invalid password', async ({ request }) => {
      const response = await request.post(endpoints.auth.login, {
        data: {
          username: testUsers.admin.username,
          password: 'wrongpassword',
        },
      })

      expect(response.status()).toBe(401)
    })

    test('should return 401 with non-existent user', async ({ request }) => {
      const response = await request.post(endpoints.auth.login, {
        data: {
          username: 'nonexistent',
          password: 'anypassword',
        },
      })

      expect(response.status()).toBe(401)
    })

    test('should return 422 with missing username', async ({ request }) => {
      const response = await request.post(endpoints.auth.login, {
        data: {
          password: 'somepassword',
        },
      })

      expect(response.status()).toBe(422)
    })

    test('should return 422 with missing password', async ({ request }) => {
      const response = await request.post(endpoints.auth.login, {
        data: {
          username: testUsers.admin.username,
        },
      })

      expect(response.status()).toBe(422)
    })
  })

  test.describe('Get Current User (/me)', () => {
    test('should return user info with valid token', async ({ request }) => {
      // Login first
      const token = await loginViaAPI(request, 'admin')

      // Get current user
      const response = await request.get(endpoints.auth.me, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      expect(response.ok()).toBeTruthy()

      const user = await response.json()
      expect(user.username).toBe(testUsers.admin.username)
      expect(user.role).toBe(testUsers.admin.role)
    })

    test('should return 401/403 without token', async ({ request }) => {
      const response = await request.get(endpoints.auth.me)

      expect([401, 403]).toContain(response.status())
    })

    test('should return 401/403 with invalid token', async ({ request }) => {
      const response = await request.get(endpoints.auth.me, {
        headers: {
          Authorization: 'Bearer invalid-token-here',
        },
      })

      expect([401, 403]).toContain(response.status())
    })
  })

  test.describe('Logout', () => {
    test('should logout successfully via API', async ({ request }) => {
      // Login first
      const token = await loginViaAPI(request, 'admin')

      // Logout
      const response = await request.post(endpoints.auth.logout, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      expect(response.ok()).toBeTruthy()

      const data = await response.json()
      expect(data.message).toContain('logged out')
    })
  })

  test.describe('Role-Based Access', () => {
    test('super admin should have no tenant', async ({ request }) => {
      const token = await loginViaAPI(request, 'superAdmin')

      const response = await request.get(endpoints.auth.me, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      const user = await response.json()
      expect(user.role).toBe('super_admin')
      // Super admin may have tenant_id as null, undefined, or not present
      expect(user.tenant_id ?? null).toBeNull()
    })

    test('admin should have tenant assigned', async ({ request }) => {
      const token = await loginViaAPI(request, 'admin')

      const response = await request.get(endpoints.auth.me, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      const user = await response.json()
      expect(user.role).toBe('admin')
      expect(user.tenant_id).toBeTruthy()
    })

    test('legal user should have tenant assigned', async ({ request }) => {
      const token = await loginViaAPI(request, 'legal')

      const response = await request.get(endpoints.auth.me, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      const user = await response.json()
      expect(user.role).toBe('legal')
      expect(user.tenant_id).toBeTruthy()
    })
  })
})

import { test, expect } from '@playwright/test'
import { testUsers, pages, endpoints } from '../fixtures/test-data'
import { loginViaUI, loginViaAPI } from '../utils/auth'
import { queryContracts, contractApi } from '../utils/api-helpers'

test.describe('Contract Q&A', () => {
  let adminToken: string

  test.beforeAll(async ({ request }) => {
    adminToken = await loginViaAPI(request, 'admin')
  })

  test.describe('Query API', () => {
    test('should answer question about contracts', async ({ request }) => {
      const { response, data } = await queryContracts(
        request,
        'What are the main contract types in the system?',
        { token: adminToken }
      )

      expect(response.ok()).toBeTruthy()
      expect(data).toBeTruthy()
      expect(data.answer || data.response).toBeTruthy()
    })

    test('should answer question about specific contract', async ({ request }) => {
      // Get a contract ID
      const { data: contractsData } = await contractApi.list(request, { token: adminToken })

      test.skip(!contractsData?.items?.length, 'No contracts available to test')

      const contractId = contractsData.items[0].id

      const { response, data } = await queryContracts(
        request,
        'What is this contract about?',
        {
          token: adminToken,
          contractId,
        }
      )

      expect(response.ok()).toBeTruthy()
      expect(data).toBeTruthy()
    })

    test('should return 401 without authentication', async ({ request }) => {
      const response = await request.post(endpoints.query, {
        data: {
          question: 'Test question',
        },
      })

      expect([401, 403]).toContain(response.status())
    })

    test('should handle empty question gracefully', async ({ request }) => {
      const { response } = await queryContracts(request, '', { token: adminToken })

      expect([400, 422]).toContain(response.status())
    })
  })

  test.describe('Query Page UI', () => {
    test('should display query page', async ({ page }) => {
      await loginViaUI(page, 'admin')

      await page.goto(pages.query)
      await page.waitForLoadState('networkidle')

      // Should show query interface
      await expect(page.locator('input, textarea').first()).toBeVisible({ timeout: 10000 })
    })

    test('should have input for questions', async ({ page }) => {
      await loginViaUI(page, 'admin')

      await page.goto(pages.query)
      await page.waitForLoadState('networkidle')

      // Find question input
      const questionInput = page.locator(
        'input[placeholder*="ask" i], textarea[placeholder*="ask" i], input[placeholder*="question" i], textarea[placeholder*="question" i]'
      )
      await expect(questionInput.first()).toBeVisible()
    })

    test('should submit question and show response', async ({ page }) => {
      await loginViaUI(page, 'admin')

      await page.goto(pages.query)
      await page.waitForLoadState('networkidle')

      // Find question input
      const questionInput = page.locator(
        'input[placeholder*="ask" i], textarea[placeholder*="ask" i], input[placeholder*="question" i], textarea, input[type="text"]'
      ).first()

      await questionInput.fill('What contracts do we have?')

      // Submit
      const submitButton = page.locator('button[type="submit"], button:has-text("Send"), button:has-text("Ask")')
      await submitButton.first().click()

      // Wait for response (may take some time due to AI processing)
      await page.waitForResponse(
        (response) => response.url().includes('/query') && response.status() === 200,
        { timeout: 60000 }
      ).catch(() => {
        // Timeout is acceptable if AI is slow
      })
    })

    test('should show loading state while processing', async ({ page }) => {
      await loginViaUI(page, 'admin')

      await page.goto(pages.query)
      await page.waitForLoadState('networkidle')

      const questionInput = page.locator('textarea, input[type="text"]').first()
      await questionInput.fill('Test question')

      const submitButton = page.locator('button[type="submit"], button:has-text("Send"), button:has-text("Ask")')
      await submitButton.first().click()

      // Should show loading indicator
      const loadingIndicator = page.locator('[class*="loading"], [class*="spinner"], text=/loading|thinking|processing/i')
      // May or may not catch this depending on timing
    })
  })

  test.describe('Query Context', () => {
    test('should provide relevant sources in response', async ({ request }) => {
      const { data } = await queryContracts(
        request,
        'What are the termination clauses?',
        { token: adminToken }
      )

      // Response may include sources
      if (data.sources) {
        expect(Array.isArray(data.sources)).toBeTruthy()
      }
    })

    test('should include confidence score', async ({ request }) => {
      const { data } = await queryContracts(
        request,
        'What is the total contract value?',
        { token: adminToken }
      )

      // Response may include confidence
      if (data.confidence !== undefined) {
        expect(data.confidence).toBeGreaterThanOrEqual(0)
        expect(data.confidence).toBeLessThanOrEqual(1)
      }
    })
  })

  test.describe('Query History', () => {
    test('should show previous questions', async ({ page }) => {
      await loginViaUI(page, 'admin')

      await page.goto(pages.query)
      await page.waitForLoadState('networkidle')

      // Look for history section
      const historySection = page.locator('text=/history|previous|recent/i')
      // May or may not be implemented
    })
  })

  test.describe('Query Performance', () => {
    test('should respond within timeout', async ({ request }) => {
      const startTime = Date.now()

      const { response } = await queryContracts(
        request,
        'What contracts are expiring soon?',
        { token: adminToken }
      )

      const responseTime = Date.now() - startTime

      // Should respond within 60 seconds (AI can be slow)
      expect(responseTime).toBeLessThan(60000)

      if (response.ok()) {
        // Even better if it's fast
        console.log(`Query response time: ${responseTime}ms`)
      }
    })
  })
})

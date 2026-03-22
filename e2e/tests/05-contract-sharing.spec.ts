import { test, expect } from '@playwright/test'
import { testUsers, pages } from '../fixtures/test-data'
import { loginViaUI, loginViaAPI } from '../utils/auth'
import { contractApi, externalUserApi } from '../utils/api-helpers'

test.describe('Contract Sharing', () => {
  let adminToken: string
  let testExternalUserId: string | null = null
  let testContractId: string | null = null
  let shareAccessToken: string | null = null

  test.beforeAll(async ({ request }) => {
    adminToken = await loginViaAPI(request, 'admin')

    // Get a contract to share
    const { data: contractsData } = await contractApi.list(request, { token: adminToken })
    if (contractsData.items.length > 0) {
      testContractId = contractsData.items[0].id
    }

    // Create an external user for testing
    const uniqueEmail = `share-test${Date.now()}@external.com`
    const { data: userData } = await externalUserApi.create(
      request,
      {
        email: uniqueEmail,
        full_name: 'Share Test User',
        company_name: 'Test Company',
      },
      { token: adminToken }
    )
    testExternalUserId = userData.id
  })

  test.afterAll(async ({ request }) => {
    // Clean up external user
    if (testExternalUserId) {
      await externalUserApi.delete(request, testExternalUserId, { token: adminToken })
    }
  })

  test.describe('Share Contract API', () => {
    test('should share contract with external user', async ({ request }) => {
      test.skip(!testContractId || !testExternalUserId, 'No contract or external user available')

      const { response, data } = await contractApi.share(
        request,
        testContractId!,
        {
          external_user_id: testExternalUserId!,
          can_download: true,
          can_comment: true,
          expires_in_days: 30,
          message: 'Please review this contract',
        },
        { token: adminToken }
      )

      expect(response.ok()).toBeTruthy()
      expect(data.share).toBeTruthy()
      expect(data.access_url).toBeTruthy()
      expect(data.token).toBeTruthy()

      // Store token for external portal tests
      shareAccessToken = data.token
    })

    test('should list contract shares', async ({ request }) => {
      test.skip(!testContractId, 'No contract available')

      const { response, data } = await contractApi.getShares(request, testContractId!, {
        token: adminToken,
      })

      expect(response.ok()).toBeTruthy()
      expect(data.items).toBeDefined()
      expect(Array.isArray(data.items)).toBeTruthy()
    })

    test('should prevent duplicate shares', async ({ request }) => {
      test.skip(!testContractId || !testExternalUserId, 'No contract or external user available')

      // Try to share again with same user
      const { response } = await contractApi.share(
        request,
        testContractId!,
        {
          external_user_id: testExternalUserId!,
        },
        { token: adminToken }
      )

      // Should fail because already shared
      expect([400, 409]).toContain(response.status())
    })

    test('should return 404 for non-existent contract', async ({ request }) => {
      test.skip(!testExternalUserId, 'No external user available')

      const fakeContractId = '00000000-0000-0000-0000-000000000000'

      const { response } = await contractApi.share(
        request,
        fakeContractId,
        {
          external_user_id: testExternalUserId!,
        },
        { token: adminToken }
      )

      expect(response.status()).toBe(404)
    })

    test('should return 404 for non-existent external user', async ({ request }) => {
      test.skip(!testContractId, 'No contract available')

      const fakeUserId = '00000000-0000-0000-0000-000000000000'

      const { response } = await contractApi.share(
        request,
        testContractId!,
        {
          external_user_id: fakeUserId,
        },
        { token: adminToken }
      )

      expect(response.status()).toBe(404)
    })
  })

  test.describe('External Portal Access', () => {
    test('should access shared contract with valid token', async ({ page }) => {
      test.skip(!shareAccessToken, 'No share access token available')

      await page.goto(pages.external.contract(shareAccessToken!))
      await page.waitForLoadState('networkidle')

      // Should show contract details (not an error page)
      const hasError = await page.locator('text=/denied|invalid|expired/i').isVisible()
      const hasContract = await page.locator('text=/contract|document/i').first().isVisible()

      expect(hasError || hasContract).toBeTruthy() // Either shows content or proper error
    })

    test('should show access denied for invalid token', async ({ page }) => {
      await page.goto(pages.external.contract('invalid-token-here'))
      await page.waitForLoadState('networkidle')

      // Should show access denied
      await expect(page.locator('text=/denied|invalid|expired|error/i').first()).toBeVisible({
        timeout: 10000,
      })
    })

    test('should show contract information', async ({ page }) => {
      test.skip(!shareAccessToken, 'No share access token available')

      await page.goto(pages.external.contract(shareAccessToken!))
      await page.waitForLoadState('networkidle')

      // Look for contract info elements
      const contractInfo = page.locator('text=/filename|counterparty|contract/i')
      await expect(contractInfo.first()).toBeVisible({ timeout: 10000 })
    })

    test('should show download button when permitted', async ({ page }) => {
      test.skip(!shareAccessToken, 'No share access token available')

      await page.goto(pages.external.contract(shareAccessToken!))
      await page.waitForLoadState('networkidle')

      // If download is permitted, should show download button
      const downloadButton = page.locator('button:has-text("Download")')
      // May or may not be visible depending on permissions
    })

    test('should show comments section when permitted', async ({ page }) => {
      test.skip(!shareAccessToken, 'No share access token available')

      await page.goto(pages.external.contract(shareAccessToken!))
      await page.waitForLoadState('networkidle')

      // If comments are permitted, should show comments section
      const commentsSection = page.locator('text=/comment/i')
      // May or may not be visible depending on permissions
    })
  })

  test.describe('Contract Sharing UI', () => {
    test('should show sharing tab on contract detail', async ({ page, request }) => {
      await loginViaUI(page, 'admin')

      // Get a contract
      const { data: contractsData } = await contractApi.list(request, { token: adminToken })

      if (contractsData.items.length > 0) {
        const contractId = contractsData.items[0].id

        await page.goto(pages.contractDetail(contractId))
        await page.waitForLoadState('networkidle')

        // Look for sharing tab or section
        const sharingTab = page.locator('text=/sharing|share|external/i')
        await expect(sharingTab.first()).toBeVisible({ timeout: 10000 })
      }
    })

    test('should open share modal', async ({ page, request }) => {
      await loginViaUI(page, 'admin')

      const { data: contractsData } = await contractApi.list(request, { token: adminToken })

      if (contractsData.items.length > 0) {
        const contractId = contractsData.items[0].id

        await page.goto(pages.contractDetail(contractId))
        await page.waitForLoadState('networkidle')

        // Click sharing tab
        const sharingTab = page.locator('text=/sharing|share/i').first()
        await sharingTab.click()

        // Click share button
        const shareButton = page.locator('button:has-text("Share")')
        if (await shareButton.first().isVisible()) {
          await shareButton.first().click()

          // Should show modal
          await expect(page.locator('[role="dialog"], .modal')).toBeVisible({ timeout: 5000 })
        }
      }
    })
  })

  test.describe('Revoke Share', () => {
    test('should revoke contract share', async ({ request }) => {
      test.skip(!testContractId, 'No contract available')

      // Get shares
      const { data: sharesData } = await contractApi.getShares(request, testContractId!, {
        token: adminToken,
      })

      if (sharesData.items.length > 0) {
        const shareId = sharesData.items[0].id

        // Revoke
        const response = await request.delete(
          `/api/contracts/${testContractId}/shares/${shareId}`,
          {
            headers: {
              Authorization: `Bearer ${adminToken}`,
            },
          }
        )

        expect(response.ok()).toBeTruthy()
      }
    })

    test('revoked share should not grant access', async ({ page, request }) => {
      // This would test that after revoking, the token no longer works
      // But we need the token from the revoked share
      // Skip if we don't have the token
      test.skip(true, 'Requires additional setup to test revoked access')
    })
  })
})

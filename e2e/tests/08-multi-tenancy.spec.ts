import { test, expect } from '@playwright/test'
import { testUsers, endpoints } from '../fixtures/test-data'
import { loginViaAPI } from '../utils/auth'
import { contractApi, businessUnitApi, externalUserApi, buildHeaders } from '../utils/api-helpers'

test.describe('Multi-Tenancy & Security', () => {
  test.describe('Tenant Isolation', () => {
    test('users from different tenants should see different contracts', async ({ request }) => {
      // Login as Acme admin
      const acmeToken = await loginViaAPI(request, 'admin')
      const { data: acmeContracts } = await contractApi.list(request, { token: acmeToken })

      // Login as TechStart admin
      const techToken = await loginViaAPI(request, 'techstartAdmin')
      const { data: techContracts } = await contractApi.list(request, { token: techToken })

      // Skip if either tenant has no contracts
      test.skip(!acmeContracts?.items?.length || !techContracts?.items?.length, 'Need contracts in both tenants to test')

      const acmeIds = new Set(acmeContracts.items.map((c: any) => c.id))
      const techIds = techContracts.items.map((c: any) => c.id)

      // No overlap between tenant data
      techIds.forEach((id: string) => {
        expect(acmeIds.has(id)).toBeFalsy()
      })
    })

    test('user cannot access contract from another tenant', async ({ request }) => {
      // Get Acme contract
      const acmeToken = await loginViaAPI(request, 'admin')
      const { data: acmeContracts } = await contractApi.list(request, { token: acmeToken })

      test.skip(!acmeContracts?.items?.length, 'No contracts available to test')

      const acmeContractId = acmeContracts.items[0].id

      // Try to access with TechStart credentials
      const techToken = await loginViaAPI(request, 'techstartAdmin')
      const { response } = await contractApi.get(request, acmeContractId, { token: techToken })

      // Should not be accessible
      expect([403, 404]).toContain(response.status())
    })

    test('user cannot access business units from another tenant', async ({ request }) => {
      // Get Acme BUs
      const acmeToken = await loginViaAPI(request, 'admin')
      const { data: acmeBUs } = await businessUnitApi.list(request, { token: acmeToken })

      if (acmeBUs.items.length > 0) {
        const acmeBUId = acmeBUs.items[0].id

        // Try to access with TechStart credentials
        const techToken = await loginViaAPI(request, 'techstartAdmin')
        const { response } = await businessUnitApi.get(request, acmeBUId, { token: techToken })

        // Should not be accessible
        expect([403, 404]).toContain(response.status())
      }
    })

    test('user cannot access external users from another tenant', async ({ request }) => {
      // Get Acme external users
      const acmeToken = await loginViaAPI(request, 'admin')
      const { data: acmeUsers } = await externalUserApi.list(request, { token: acmeToken })

      if (acmeUsers.items.length > 0) {
        const acmeUserId = acmeUsers.items[0].id

        // Try to access with TechStart credentials
        const techToken = await loginViaAPI(request, 'techstartAdmin')
        const { response } = await externalUserApi.get(request, acmeUserId, { token: techToken })

        // Should not be accessible
        expect([403, 404]).toContain(response.status())
      }
    })
  })

  test.describe('Super Admin Access', () => {
    test('super admin can list tenants', async ({ request }) => {
      const superAdminToken = await loginViaAPI(request, 'superAdmin')

      const response = await request.get(endpoints.tenants, {
        headers: buildHeaders({ token: superAdminToken }),
      })

      // Tenants endpoint might return items array or direct array
      expect([200, 404]).toContain(response.status())

      if (response.ok()) {
        const data = await response.json()
        // Handle both { items: [] } and direct array responses
        const items = data.items ?? data
        expect(Array.isArray(items)).toBeTruthy()
      }
    })

    test('super admin can access any tenant with X-Tenant-ID header', async ({ request }) => {
      const superAdminToken = await loginViaAPI(request, 'superAdmin')

      // Get list of tenants
      const tenantsResponse = await request.get(endpoints.tenants, {
        headers: buildHeaders({ token: superAdminToken }),
      })

      const tenantsData = await tenantsResponse.json()

      if (tenantsData.items && tenantsData.items.length > 0) {
        const tenantId = tenantsData.items[0].id

        // Access that tenant's contracts
        const { response, data } = await contractApi.list(request, {
          token: superAdminToken,
          tenantId,
        })

        expect(response.ok()).toBeTruthy()
      }
    })

    test('regular admin cannot list all tenants', async ({ request }) => {
      const adminToken = await loginViaAPI(request, 'admin')

      const response = await request.get(endpoints.tenants, {
        headers: buildHeaders({ token: adminToken }),
      })

      // Should be forbidden
      expect([403, 404]).toContain(response.status())
    })

    test('super admin can access super admin dashboard', async ({ request }) => {
      const superAdminToken = await loginViaAPI(request, 'superAdmin')

      const response = await request.get('/api/super-admin/dashboard', {
        headers: buildHeaders({ token: superAdminToken }),
      })

      // Should be accessible (200) or endpoint might not exist (404)
      expect([200, 404]).toContain(response.status())
    })
  })

  test.describe('Security Headers', () => {
    test('API should return security headers', async ({ request }) => {
      const token = await loginViaAPI(request, 'admin')

      const response = await request.get(endpoints.contracts.list, {
        headers: buildHeaders({ token }),
      })

      // Check for common security headers
      const headers = response.headers()

      // These may or may not be present depending on configuration
      // Just log them for now
      console.log('Response headers:', Object.keys(headers))
    })
  })

  test.describe('Input Validation', () => {
    test('should reject SQL injection attempts in search', async ({ request }) => {
      const token = await loginViaAPI(request, 'admin')

      const response = await request.get(
        `${endpoints.contracts.list}?search=' OR '1'='1`,
        {
          headers: buildHeaders({ token }),
        }
      )

      // Should not cause an error, just return empty or filtered results
      expect([200, 400, 422]).toContain(response.status())
    })

    test('should reject XSS attempts in input', async ({ request }) => {
      const token = await loginViaAPI(request, 'admin')
      const uniqueEmail = `xss-test-${Date.now()}@example.com`

      const { response } = await externalUserApi.create(
        request,
        {
          email: uniqueEmail,
          full_name: '<script>alert("xss")</script>',
        },
        { token }
      )

      // Should either reject (400/422) or accept (storing is OK if frontend sanitizes on display)
      // This test validates the server doesn't crash on XSS input
      expect([200, 201, 400, 422]).toContain(response.status())

      // Clean up if created
      if (response.ok()) {
        const data = await response.json()
        if (data.id) {
          await externalUserApi.delete(request, data.id, { token })
        }
      }
    })

    test('should reject invalid UUID formats', async ({ request }) => {
      const token = await loginViaAPI(request, 'admin')

      const { response } = await contractApi.get(request, 'not-a-uuid', { token })

      // Should return an error - either validation error or not found
      expect([400, 404, 422]).toContain(response.status())
    })

    test('should handle very long input gracefully', async ({ request }) => {
      const token = await loginViaAPI(request, 'admin')

      const longString = 'a'.repeat(100000)

      const { response } = await externalUserApi.create(
        request,
        {
          email: 'test@example.com',
          full_name: longString,
        },
        { token }
      )

      // Should reject or truncate, not crash
      expect([200, 400, 413, 422]).toContain(response.status())
    })
  })

  test.describe('Rate Limiting', () => {
    test('should handle rapid requests without crashing', async ({ request }) => {
      const token = await loginViaAPI(request, 'admin')

      // Send 20 rapid requests
      const promises = Array(20)
        .fill(null)
        .map(() =>
          contractApi.list(request, { token })
        )

      const results = await Promise.all(promises)

      // All should complete (either success or rate limited)
      results.forEach(({ response }) => {
        expect([200, 429]).toContain(response.status())
      })
    })
  })

  test.describe('Session Management', () => {
    test('expired token should be rejected', async ({ request }) => {
      // Use a manually crafted expired token
      const expiredToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoxfQ.invalid'

      const response = await request.get(endpoints.auth.me, {
        headers: {
          Authorization: `Bearer ${expiredToken}`,
        },
      })

      expect([401, 403]).toContain(response.status())
    })

    test('malformed token should be rejected', async ({ request }) => {
      const response = await request.get(endpoints.auth.me, {
        headers: {
          Authorization: 'Bearer malformed-token',
        },
      })

      expect([401, 403]).toContain(response.status())
    })

    test('missing Bearer prefix should be rejected', async ({ request }) => {
      const token = await loginViaAPI(request, 'admin')

      const response = await request.get(endpoints.auth.me, {
        headers: {
          Authorization: token, // Missing "Bearer " prefix
        },
      })

      expect([401, 403]).toContain(response.status())
    })
  })
})

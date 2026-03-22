# Evaluetor Dashboard - API Integration Guide

## Overview

The Evaluetor dashboard is fully integrated with the Evaluetor API. This guide explains how to set up and use the API integration.

## Configuration

### 1. Environment Variables

Create a `.env.local` file in the project root:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

Replace `http://localhost:8000/api` with your actual API endpoint.

### 2. API Client Setup

The `lib/api-client.ts` file contains all API methods. Before making requests, set the authentication token:

```typescript
import { APIClient } from '@/lib/api-client'

// After login or getting the token from your auth system
APIClient.setToken('your_jwt_token_here')
```

## Integration Points

### Dashboard (Dashboard, SLA Tracking, Vendor Scoring)

**File:** `components/sla-dashboard.tsx`

Fetches:
- `GET /api/sla/compliance/summary` - Overall SLA compliance metrics
- `GET /api/sla/breaches/active` - Currently active SLA breaches
- `GET /api/sla/` - List all SLAs with filters

**Displays:**
- Overall compliance percentage
- Total SLAs (active/inactive)
- Breach count by severity (critical, high, medium, low)
- Penalty exposure
- Compliance rates by metric type

### Vendor Scoring

**File:** `components/vendor-scoring.tsx`

Fetches:
- `GET /api/vendors` - List vendors with pagination
- Optional: `GET /api/vendors/{vendorId}/scoring` - Individual vendor scores
- Optional: `GET /api/vendors/{vendorId}/scorecard` - Vendor scorecards

**Displays:**
- Top vendors ranked by overall score
- Vendor performance trends (up/down)
- Sub-metrics breakdown (quality, delivery, cost, risk)
- Five-star rating system
- Scoring criteria reference

### Contracts Overview

**File:** `components/contract-overview.tsx`

Fetches:
- `GET /api/contracts` - List contracts with filters

**Displays:**
- Total active contracts
- Compliance score
- At-risk contract count

## Authentication Flow

1. **Login**: `POST /api/auth/login`
   ```json
   {
     "username": "string",
     "password": "string"
   }
   ```

2. Response includes JWT token:
   ```json
   {
     "access_token": "string",
     "token_type": "bearer",
     "expires_in": 3600,
     "user": { "id": "...", "username": "...", "email": "...", "role": "..." }
   }
   ```

3. Set token in APIClient:
   ```typescript
   APIClient.setToken(access_token)
   ```

## Using the API Client

### Simple Example - Get SLA Compliance

```typescript
import { useApi } from '@/hooks/use-api'
import { APIClient } from '@/lib/api-client'

export function MyComponent() {
  const { data, loading, error } = useApi(
    () => APIClient.getSLACompliance(),
    []
  )

  if (loading) return <div>Loading...</div>
  if (error) return <div>Error: {error.message}</div>

  return <div>Compliance: {data?.overall_compliance_rate}%</div>
}
```

### Fetching with Filters

```typescript
const { data: vendors } = useApi(
  () =>
    APIClient.getVendors({
      page: 1,
      page_size: 20,
      search: 'vendor name',
    }),
  []
)
```

## API Methods Available

### SLA Methods

- `getSLACompliance(contractId?)` - Get SLA compliance summary
- `getActiveSLABreaches()` - Get active breach list
- `getContractSLAs(contractId, includeInactive?)` - Get SLAs for a contract
- `getAllSLAs(filters?)` - List all SLAs with filters
- `createSLA(contractId, slaData)` - Create new SLA
- `logSLAPerformance(contractId, slaId, performanceData)` - Log measurement

### Vendor Methods

- `getVendors(filters?)` - List vendors with pagination
- `getVendor(vendorId)` - Get single vendor
- `getVendorScoring(vendorId)` - Get vendor scores
- `getVendorScorecard(vendorId)` - Get vendor scorecard
- `getAllVendorScores(filters?)` - Get all vendor scores

### Contract Methods

- `getContracts(filters?)` - List contracts with filtering
- `getContract(contractId)` - Get single contract

### Auth Methods

- `login(username, password)` - User login
- `getCurrentUser()` - Get current user info
- `logout()` - Logout user

## Error Handling

The API client throws errors on non-200 responses:

```typescript
try {
  const data = await APIClient.getSLACompliance()
} catch (error) {
  console.error('API Error:', error.message)
  // Handle error appropriately
}
```

## Pagination

Most list endpoints support pagination:

```typescript
const { data } = useApi(
  () =>
    APIClient.getVendors({
      page: 1,
      page_size: 50,
    }),
  []
)

// Response includes:
// {
//   items: [...],
//   total: 100,
//   page: 1,
//   page_size: 50,
//   total_pages: 2
// }
```

## Performance Notes

- The dashboard uses `useApi` hook for automatic data fetching and caching
- Components only re-fetch when dependencies change
- Consider implementing SWR or React Query for production apps
- Set appropriate error boundaries around API-dependent components

## Troubleshooting

### 401 Unauthorized
- Check that token is set: `APIClient.getToken()`
- Token may have expired - try re-logging in
- Verify token format: `Bearer <token>`

### 403 Forbidden
- User role may not have permission for the endpoint
- Check user role: `Admin`, `Legal`, or `Procurement`
- Some endpoints require specific roles

### Network Errors
- Verify API URL in `.env.local`
- Check API server is running
- Check CORS configuration if API is on different domain

## Next Steps

1. Set up authentication in your app
2. Create a login page using `APIClient.login()`
3. Store and manage authentication tokens securely
4. Implement token refresh logic for production
5. Add error boundaries and loading states to components

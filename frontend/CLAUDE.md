# Frontend CLAUDE.md

React + TypeScript SPA with Vite, TanStack Query, and Tailwind CSS.

## Quick Reference

```bash
npm install        # Install deps
npm run dev        # Dev server (Vite, port 3000 or 3002)
npm test           # Run tests
npm run build      # Production build
```

## Code Conventions

### API Client
All backend calls go through `src/lib/api.ts`. The singleton `api` object handles auth tokens and error extraction.

**Paginated responses:** Backend returns `{items: [...], total, page, page_size, pages}`. API methods extract the items array:
```typescript
const response = await this.client.get('/resource')
return response.data.items ?? response.data
```

### Page Pattern
```tsx
export default function ResourcePage() {
  const { data, isLoading } = useQuery({
    queryKey: ['resource'],
    queryFn: () => api.getResources(),
  })

  if (isLoading) return <LoadingSpinner size="lg" />
  return (...)
}
```

### Auth Context
```typescript
const { user, isAdmin, isLegal, isSuperAdmin, login, logout } = useAuth()
```

### Routing
- All authenticated routes are children of `<MainLayout>` in `App.tsx`
- Login page is a standalone route
- Super admin routes: `/super-admin/*`
- Governance routes: `/organizations`, `/relationships`, `/kpis`, `/improvements`, `/surveys`
- Admin routes: `/admin/business-units`, `/admin/scheduler`, etc.

### Sidebar Navigation
Sidebar items are role-filtered arrays in `components/layout/Sidebar.tsx`. Each item has:
```typescript
{ name: 'Label', href: '/path', icon: HeroIcon, roles: ['admin', 'legal'] }
```
Super admin only sees `superAdminNavigation` items — no tenant-level items.

## Styling

- **Framework:** Tailwind CSS
- **Theme:** Personio-inspired European minimal (see `src/styles/personio-theme.ts`)
- **Primary color:** Violet (`violet-500` to `violet-700`)
- **Component classes:** `card`, `btn-primary`, `btn-secondary`, `input`, `label` (defined in `index.css`)
- **Utility:** `cn()` from `src/lib/utils.ts` for conditional classnames

## Key Components

| Component | Purpose |
|-----------|---------|
| `StatCard` | Metric card with icon, trend, mini chart, optional `info` tooltip |
| `WelcomeBanner` | Dashboard greeting with role-specific quick actions |
| `ModernTable` | Sortable, filterable data table |
| `CommandPalette` | ⌘K search overlay |
| `LoadingSpinner` | Consistent loading indicator |

## Key Files

| File | Purpose |
|------|---------|
| `src/App.tsx` | Route definitions |
| `src/lib/api.ts` | API client (all backend calls) |
| `src/contexts/AuthContext.tsx` | Auth state, login/logout |
| `src/contexts/SidebarContext.tsx` | Sidebar collapse state |
| `src/types/index.ts` | Core TypeScript types |
| `src/styles/theme.ts` | Role-based theme config |

## Vite Proxy
Dev server proxies `/api` to `http://localhost:8000` (see `vite.config.ts`).

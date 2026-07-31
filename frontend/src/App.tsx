import { Routes, Route, Navigate } from 'react-router-dom'

// Force unique build hash
if (typeof window !== 'undefined') (window as any).__BUILD = '20260423v3'
import { useAuth } from './contexts/AuthContext'
import { SidebarProvider } from './contexts/SidebarContext'
import { TenantConfigProvider } from './contexts/TenantConfigContext'
import MainLayout from './components/layout/MainLayout'
import LoginPage from './pages/LoginPage'
import ModernDashboardPage from './pages/ModernDashboardPage'
import ContractsPage from './pages/ContractsPage'
import ContractViewPage from './pages/ContractViewPage'
import GroupsPage from './pages/GroupsPage'
import GroupDetailPage from './pages/GroupDetailPage'
import ObligationDetailPage from './pages/ObligationDetailPage'
import SLADetailPage from './pages/SLADetailPage'
import ClauseDetailPage from './pages/ClauseDetailPage'
import UploadPage from './pages/UploadPage'
import QueryPage from './pages/QueryPage'
import UsersPage from './pages/UsersPage'
import SettingsPage from './pages/SettingsPage'
import UsagePage from './pages/UsagePage'
import PostSigningPage from './pages/PostSigningPage'
import MasterDataPage from './pages/admin/MasterDataPage'
import SchedulerPage from './pages/admin/SchedulerPage'
import BusinessUnitsPage from './pages/admin/BusinessUnitsPage'
import ExternalUsersPage from './pages/admin/ExternalUsersPage'
import SnowIntegrationPage from './pages/admin/SnowIntegrationPage'
import SharePointIntegrationPage from './pages/admin/SharePointIntegrationPage'
import ExtractionQualityPage from './pages/admin/ExtractionQualityPage'
import IndustryProfilesPage from './pages/admin/IndustryProfilesPage'
import SSOConfigPage from './pages/admin/SSOConfigPage'
import ExternalContractPage from './pages/ExternalContractPage'
import ExternalGovernancePage from './pages/ExternalGovernancePage'
import RenewalsPage from './pages/RenewalsPage'
import VendorsPage from './pages/VendorsPage'
import ReportsPage from './pages/ReportsPage'
import SuperAdminDashboardPage from './pages/super-admin/SuperAdminDashboardPage'
import TenantManagementPage from './pages/super-admin/TenantManagementPage'
import TenantDetailPage from './pages/super-admin/TenantDetailPage'
import GlobalUsersPage from './pages/super-admin/GlobalUsersPage'
import CustomFieldsPage from './pages/super-admin/CustomFieldsPage'
import SnowAdminPage from './pages/super-admin/SnowAdminPage'
import OrganizationsPage from './pages/governance/OrganizationsPage'
import RelationshipsPage from './pages/governance/RelationshipsPage'
import RelationshipDetailPage from './pages/governance/RelationshipDetailPage'
import SurveysPage from './pages/governance/SurveysPage'
import OrganizationDetailPage from './pages/governance/OrganizationDetailPage'
import KPIApprovalsPage from './pages/governance/KPIApprovalsPage'
import LoadingSpinner from './components/ui/LoadingSpinner'
import { can, defaultLandingFor, type Permission } from '@/lib/rbac'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

// Route-level RBAC: a role without `perm` is redirected to its landing page
// instead of seeing a forbidden page. Enforces what the sidebar only hides.
function RequirePermission({ perm, children }: { perm: Permission; children: React.ReactNode }) {
  const { user } = useAuth()
  if (user && !can(user, perm)) {
    return <Navigate to={defaultLandingFor(user)} replace />
  }
  return <>{children}</>
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/login/sso-callback" element={<LoginPage />} />
      {/* External portal - no auth required */}
      <Route path="/external/contracts/:token" element={<ExternalContractPage />} />
      <Route path="/external/contracts" element={<ExternalContractPage />} />
      <Route path="/external/governance" element={<ExternalGovernancePage />} />

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <TenantConfigProvider>
              <SidebarProvider>
                <MainLayout />
              </SidebarProvider>
            </TenantConfigProvider>
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<ModernDashboardPage />} />
        <Route path="contracts" element={<ContractsPage />} />
        <Route path="contracts/:id" element={<ContractViewPage />} />
        <Route path="groups" element={<GroupsPage />} />
        <Route path="groups/:groupId" element={<GroupDetailPage />} />
        <Route path="obligations/:id" element={<ObligationDetailPage />} />
        <Route path="slas/:id" element={<SLADetailPage />} />
        <Route path="clauses/:id" element={<ClauseDetailPage />} />
        <Route path="post-signing" element={<PostSigningPage />} />
        {/* /compliance is a legacy alias still referenced by dashboard cards, the
            command palette and older nav — point it at the post-signing view. */}
        <Route path="compliance" element={<Navigate to="/post-signing" replace />} />
        <Route path="renewals" element={<RenewalsPage />} />
        <Route path="vendors" element={<VendorsPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="upload" element={<UploadPage />} />
        <Route path="query" element={<QueryPage />} />
        <Route path="users" element={<RequirePermission perm="admin"><UsersPage /></RequirePermission>} />
        <Route path="settings" element={<RequirePermission perm="settings"><SettingsPage /></RequirePermission>} />
        <Route path="usage" element={<RequirePermission perm="usage"><UsagePage /></RequirePermission>} />
        <Route path="admin/master-data" element={<RequirePermission perm="admin"><MasterDataPage /></RequirePermission>} />
        {/* Redirects for old routes */}
        <Route path="admin/sla-config" element={<Navigate to="/admin/master-data" replace />} />
        <Route path="admin/milestone-config" element={<Navigate to="/admin/master-data" replace />} />
        <Route path="admin/scheduler" element={<RequirePermission perm="admin"><SchedulerPage /></RequirePermission>} />
        {/* Governance Routes */}
        <Route path="organizations" element={<OrganizationsPage />} />
        <Route path="organizations/:id" element={<OrganizationDetailPage />} />
        <Route path="relationships" element={<RelationshipsPage />} />
        <Route path="relationships/:id" element={<RelationshipDetailPage />} />
        <Route path="kpi-approvals" element={<RequirePermission perm="kpiApprovals"><KPIApprovalsPage /></RequirePermission>} />
        {/* Redirects for consolidated governance pages */}
        <Route path="kpis" element={<Navigate to="/relationships" replace />} />
        <Route path="service-portfolio" element={<Navigate to="/organizations" replace />} />
        <Route path="improvements" element={<Navigate to="/relationships" replace />} />
        <Route path="surveys" element={<SurveysPage />} />
        <Route path="admin/business-units" element={<RequirePermission perm="admin"><BusinessUnitsPage /></RequirePermission>} />
        <Route path="admin/external-users" element={<RequirePermission perm="admin"><ExternalUsersPage /></RequirePermission>} />
        <Route path="admin/integrations/servicenow" element={<RequirePermission perm="admin"><SnowIntegrationPage /></RequirePermission>} />
        <Route path="admin/integrations/sharepoint" element={<RequirePermission perm="admin"><SharePointIntegrationPage /></RequirePermission>} />
        <Route path="admin/sso" element={<RequirePermission perm="admin"><SSOConfigPage /></RequirePermission>} />
        {/* Shared curation tools: tenant admin + super-admin */}
        <Route path="admin/extraction-quality" element={<RequirePermission perm="extraction.configure"><ExtractionQualityPage /></RequirePermission>} />
        <Route path="admin/industry-profiles" element={<RequirePermission perm="extraction.configure"><IndustryProfilesPage /></RequirePermission>} />
        {/* Super Admin Routes */}
        <Route path="super-admin" element={<RequirePermission perm="superadmin"><SuperAdminDashboardPage /></RequirePermission>} />
        <Route path="super-admin/tenants" element={<RequirePermission perm="superadmin"><TenantManagementPage /></RequirePermission>} />
        <Route path="super-admin/tenants/:id" element={<RequirePermission perm="superadmin"><TenantDetailPage /></RequirePermission>} />
        <Route path="super-admin/users" element={<RequirePermission perm="superadmin"><GlobalUsersPage /></RequirePermission>} />
        <Route path="super-admin/custom-fields" element={<RequirePermission perm="superadmin"><CustomFieldsPage /></RequirePermission>} />
        <Route path="super-admin/integrations" element={<RequirePermission perm="superadmin"><SnowAdminPage /></RequirePermission>} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App

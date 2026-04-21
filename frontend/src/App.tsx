import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'
import { SidebarProvider } from './contexts/SidebarContext'
import MainLayout from './components/layout/MainLayout'
import LoginPage from './pages/LoginPage'
import ModernDashboardPage from './pages/ModernDashboardPage'
import ContractsPage from './pages/ContractsPage'
import ContractViewPage from './pages/ContractViewPage'
import ObligationDetailPage from './pages/ObligationDetailPage'
import ClauseDetailPage from './pages/ClauseDetailPage'
import UploadPage from './pages/UploadPage'
import QueryPage from './pages/QueryPage'
import UsersPage from './pages/UsersPage'
import SettingsPage from './pages/SettingsPage'
import PostSigningPage from './pages/PostSigningPage'
import MasterDataPage from './pages/admin/MasterDataPage'
import SchedulerPage from './pages/admin/SchedulerPage'
import BusinessUnitsPage from './pages/admin/BusinessUnitsPage'
import ExternalUsersPage from './pages/admin/ExternalUsersPage'
import SnowIntegrationPage from './pages/admin/SnowIntegrationPage'
import SharePointIntegrationPage from './pages/admin/SharePointIntegrationPage'
import ExtractionQualityPage from './pages/admin/ExtractionQualityPage'
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
            <SidebarProvider>
              <MainLayout />
            </SidebarProvider>
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<ModernDashboardPage />} />
        <Route path="contracts" element={<ContractsPage />} />
        <Route path="contracts/:id" element={<ContractViewPage />} />
        <Route path="obligations/:id" element={<ObligationDetailPage />} />
        <Route path="clauses/:id" element={<ClauseDetailPage />} />
        <Route path="compliance" element={<PostSigningPage />} />
        <Route path="renewals" element={<RenewalsPage />} />
        <Route path="vendors" element={<VendorsPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="upload" element={<UploadPage />} />
        <Route path="query" element={<QueryPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="admin/master-data" element={<MasterDataPage />} />
        {/* Redirects for old routes */}
        <Route path="admin/sla-config" element={<Navigate to="/admin/master-data" replace />} />
        <Route path="admin/milestone-config" element={<Navigate to="/admin/master-data" replace />} />
        <Route path="admin/scheduler" element={<SchedulerPage />} />
        {/* Governance Routes */}
        <Route path="organizations" element={<OrganizationsPage />} />
        <Route path="organizations/:id" element={<OrganizationDetailPage />} />
        <Route path="relationships" element={<RelationshipsPage />} />
        <Route path="relationships/:id" element={<RelationshipDetailPage />} />
        <Route path="kpi-approvals" element={<KPIApprovalsPage />} />
        {/* Redirects for consolidated governance pages */}
        <Route path="kpis" element={<Navigate to="/relationships" replace />} />
        <Route path="service-portfolio" element={<Navigate to="/organizations" replace />} />
        <Route path="improvements" element={<Navigate to="/relationships" replace />} />
        <Route path="surveys" element={<SurveysPage />} />
        <Route path="admin/business-units" element={<BusinessUnitsPage />} />
        <Route path="admin/external-users" element={<ExternalUsersPage />} />
        <Route path="admin/integrations/servicenow" element={<SnowIntegrationPage />} />
        <Route path="admin/integrations/sharepoint" element={<SharePointIntegrationPage />} />
        <Route path="admin/sso" element={<SSOConfigPage />} />
        <Route path="admin/extraction-quality" element={<ExtractionQualityPage />} />
        {/* Super Admin Routes */}
        <Route path="super-admin" element={<SuperAdminDashboardPage />} />
        <Route path="super-admin/tenants" element={<TenantManagementPage />} />
        <Route path="super-admin/tenants/:id" element={<TenantDetailPage />} />
        <Route path="super-admin/users" element={<GlobalUsersPage />} />
        <Route path="super-admin/custom-fields" element={<CustomFieldsPage />} />
        <Route path="super-admin/integrations" element={<SnowAdminPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App

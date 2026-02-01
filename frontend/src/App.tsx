import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'
import MainLayout from './components/layout/MainLayout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ContractsPage from './pages/ContractsPage'
import ContractViewPage from './pages/ContractViewPage'
import ObligationDetailPage from './pages/ObligationDetailPage'
import ClauseDetailPage from './pages/ClauseDetailPage'
import UploadPage from './pages/UploadPage'
import QueryPage from './pages/QueryPage'
import UsersPage from './pages/UsersPage'
import SettingsPage from './pages/SettingsPage'
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

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="contracts" element={<ContractsPage />} />
        <Route path="contracts/:id" element={<ContractViewPage />} />
        <Route path="obligations/:id" element={<ObligationDetailPage />} />
        <Route path="clauses/:id" element={<ClauseDetailPage />} />
        <Route path="upload" element={<UploadPage />} />
        <Route path="query" element={<QueryPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App

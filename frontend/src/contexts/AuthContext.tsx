import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import { setAppLanguage, type AppLanguage } from '@/i18n'
import type { User, LoginRequest } from '@/types'
import { permissionsForUser, can as canFor, type Permission } from '@/lib/rbac'

function applyUserLanguage(user: User) {
  if (user.preferred_language === 'en' || user.preferred_language === 'fr') {
    setAppLanguage(user.preferred_language as AppLanguage)
  }
}

interface AuthContextType {
  user: User | null
  isLoading: boolean
  login: (credentials: LoginRequest) => Promise<void>
  logout: () => Promise<void>
  // Central RBAC — prefer these over the role booleans below.
  can: (permission: Permission) => boolean
  permissions: Permission[]
  // Legacy role booleans (still used by some call sites; prefer can()).
  isAdmin: boolean
  isLegal: boolean
  isProcurement: boolean
  isSuperAdmin: boolean
  isBuHead: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  useEffect(() => {
    const checkAuth = async () => {
      // Check for SSO callback token in URL
      const params = new URLSearchParams(window.location.search)
      const ssoToken = params.get('token')
      if (ssoToken && window.location.pathname === '/login/sso-callback') {
        api.setToken(ssoToken)
        // Clean up URL
        window.history.replaceState({}, '', '/login/sso-callback')
      }

      const token = api.getToken()
      if (token) {
        try {
          const currentUser = await api.getCurrentUser()
          setUser(currentUser)
          applyUserLanguage(currentUser)
          // If we just got an SSO token, redirect based on role
          if (ssoToken) {
            const dest = currentUser.role === 'super_admin' ? '/super-admin' : '/dashboard'
            navigate(dest)
          }
        } catch {
          api.clearToken()
        }
      }
      setIsLoading(false)
    }

    checkAuth()
  }, [])

  const login = async (credentials: LoginRequest) => {
    queryClient.clear()
    const response = await api.login(credentials)
    setUser(response.user)
    applyUserLanguage(response.user)

    // Redirect based on role
    switch (response.user.role) {
      case 'super_admin':
        navigate('/super-admin')
        break
      case 'admin':
        navigate('/dashboard')
        break
      case 'legal':
        navigate('/dashboard')
        break
      case 'procurement':
        navigate('/dashboard')
        break
      case 'bu_head':
        navigate('/dashboard')
        break
      default:
        navigate('/dashboard')
    }
  }

  const logout = async () => {
    await api.logout()
    queryClient.clear()
    setUser(null)
    navigate('/login')
  }

  const value: AuthContextType = {
    user,
    isLoading,
    login,
    logout,
    can: (permission: Permission) => canFor(user, permission),
    permissions: permissionsForUser(user),
    isAdmin: user?.role === 'admin',
    isLegal: user?.role === 'legal',
    isProcurement: user?.role === 'procurement',
    isSuperAdmin: user?.role === 'super_admin',
    isBuHead: user?.role === 'bu_head',
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// Convenience hook for permission checks: `const { can } = usePermissions()`.
export function usePermissions() {
  const { can, permissions } = useAuth()
  return { can, permissions }
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

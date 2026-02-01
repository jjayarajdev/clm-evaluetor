import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '@/lib/api'
import type { User, LoginRequest } from '@/types'

interface AuthContextType {
  user: User | null
  isLoading: boolean
  login: (credentials: LoginRequest) => Promise<void>
  logout: () => Promise<void>
  isAdmin: boolean
  isLegal: boolean
  isProcurement: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    // Check for existing session
    const checkAuth = async () => {
      const token = api.getToken()
      if (token) {
        try {
          const currentUser = await api.getCurrentUser()
          setUser(currentUser)
        } catch {
          api.clearToken()
        }
      }
      setIsLoading(false)
    }

    checkAuth()
  }, [])

  const login = async (credentials: LoginRequest) => {
    const response = await api.login(credentials)
    setUser(response.user)

    // Redirect based on role
    switch (response.user.role) {
      case 'admin':
        navigate('/dashboard')
        break
      case 'legal':
        navigate('/dashboard')
        break
      case 'procurement':
        navigate('/dashboard')
        break
      default:
        navigate('/dashboard')
    }
  }

  const logout = async () => {
    await api.logout()
    setUser(null)
    navigate('/login')
  }

  const value: AuthContextType = {
    user,
    isLoading,
    login,
    logout,
    isAdmin: user?.role === 'admin',
    isLegal: user?.role === 'legal',
    isProcurement: user?.role === 'procurement',
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

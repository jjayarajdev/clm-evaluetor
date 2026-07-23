import axios, { AxiosError, AxiosInstance } from 'axios'
import type {
  TokenResponse,
  LoginRequest,
  User,
} from '@/types'

// When VITE_API_URL is set (e.g., http://localhost:8000), append /api
// When not set, use /api for Vite proxy
export const API_BASE_URL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : '/api'

let token: string | null = localStorage.getItem('access_token')

export const client: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor to add auth header
client.interceptors.request.use((config) => {
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor for error handling
client.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Don't redirect on login failure — let the login page handle the error
      const url = error.config?.url || ''
      if (!url.includes('/auth/login')) {
        clearToken()
        window.location.href = '/login'
      }
    }
    // Extract API error message for display
    const detail = (error.response?.data as Record<string, string>)?.detail
    if (detail) {
      return Promise.reject(new Error(detail))
    }
    return Promise.reject(error)
  }
)

export function setToken(t: string) {
  token = t
  localStorage.setItem('access_token', t)
}

export function clearToken() {
  token = null
  localStorage.removeItem('access_token')
}

export function getToken() {
  return token
}

// Auth endpoints

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  const response = await client.post<TokenResponse>('/auth/login', {
    username: credentials.username,
    password: credentials.password,
  })
  setToken(response.data.access_token)
  return response.data
}

export async function getCurrentUser(): Promise<User> {
  const response = await client.get<User>('/auth/me')
  return response.data
}

export async function updateMyPreferences(preferred_language: 'en' | 'fr'): Promise<User> {
  const response = await client.patch<User>('/users/me', { preferred_language })
  return response.data
}

export async function logout(): Promise<void> {
  try {
    await client.post('/auth/logout')
  } finally {
    clearToken()
  }
}

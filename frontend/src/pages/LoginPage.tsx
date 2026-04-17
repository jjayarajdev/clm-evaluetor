import { useState, useEffect } from 'react'
import { Navigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { useQuery } from '@tanstack/react-query'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { DocumentTextIcon, ExclamationCircleIcon, ShieldCheckIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/contexts/AuthContext'
import { client } from '@/lib/api/client'
import LoadingSpinner from '@/components/ui/LoadingSpinner'

const loginSchema = z.object({
  username: z.string().min(1, 'Username is required'),
  password: z.string().min(1, 'Password is required'),
})

type LoginForm = z.infer<typeof loginSchema>

interface SSOProvider {
  tenant_slug: string
  tenant_name: string
  provider: string
  enabled: boolean
}

export default function LoginPage() {
  const { user, login } = useAuth()
  const [searchParams] = useSearchParams()
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [ssoLoading, setSsoLoading] = useState<string | null>(null)

  // Fetch available SSO providers (public endpoint, no auth needed)
  const { data: ssoProviders } = useQuery<SSOProvider[]>({
    queryKey: ['sso-providers'],
    queryFn: async () => {
      const r = await client.get('/auth/sso/providers')
      return r.data
    },
    retry: false,
  })

  // Auto-initiate SSO if ?sso=tenant_slug is in URL
  useEffect(() => {
    const ssoSlug = searchParams.get('sso')
    if (ssoSlug && ssoProviders?.some((p) => p.tenant_slug === ssoSlug)) {
      handleSSOLogin(ssoSlug)
    }
  }, [searchParams, ssoProviders])

  const handleSSOLogin = async (tenantSlug: string) => {
    setSsoLoading(tenantSlug)
    setError(null)
    try {
      const r = await client.get(`/auth/sso/init?tenant_slug=${encodeURIComponent(tenantSlug)}`)
      window.location.href = r.data.redirect_url
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'SSO initialization failed'
      setError(msg)
      setSsoLoading(null)
    }
  }

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  })

  // Redirect if already logged in
  if (user) {
    return <Navigate to="/dashboard" replace />
  }

  const onSubmit = async (data: LoginForm) => {
    setError(null)
    setIsSubmitting(true)

    try {
      await login(data)
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Invalid credentials'
      setError(errorMessage)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        {/* Logo and title */}
        <div className="text-center">
          <div className="mx-auto h-16 w-16 rounded-xl bg-primary-600 flex items-center justify-center">
            <DocumentTextIcon className="h-10 w-10 text-white" />
          </div>
          <h2 className="mt-6 text-3xl font-bold text-gray-900">
            Evaluetor
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            Sign in to access your contracts
          </p>
        </div>

        {/* Login form */}
        <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
          {error && (
            <div className="rounded-lg bg-red-50 p-4 flex items-start gap-3">
              <ExclamationCircleIcon className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label htmlFor="username" className="label">
                Username
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                className="input"
                placeholder="Enter your username"
                {...register('username')}
              />
              {errors.username && (
                <p className="mt-1 text-sm text-red-600">{errors.username.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="password" className="label">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                className="input"
                placeholder="Enter your password"
                {...register('password')}
              />
              {errors.password && (
                <p className="mt-1 text-sm text-red-600">{errors.password.message}</p>
              )}
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="btn-primary w-full py-3 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? (
              <div className="flex items-center justify-center gap-2">
                <LoadingSpinner size="sm" className="border-white border-t-transparent" />
                <span>Signing in...</span>
              </div>
            ) : (
              'Sign in'
            )}
          </button>
        </form>

        {/* SSO Login */}
        {ssoProviders && ssoProviders.length > 0 && (
          <>
            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-300" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="bg-gray-50 px-2 text-gray-500">or continue with</span>
              </div>
            </div>

            <div className="space-y-2">
              {ssoProviders.map((p) => (
                <button
                  key={p.tenant_slug}
                  type="button"
                  onClick={() => handleSSOLogin(p.tenant_slug)}
                  disabled={ssoLoading === p.tenant_slug}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors disabled:opacity-50"
                >
                  {ssoLoading === p.tenant_slug ? (
                    <LoadingSpinner size="sm" />
                  ) : (
                    <ShieldCheckIcon className="h-5 w-5 text-violet-500" />
                  )}
                  Sign in with {p.tenant_name} SSO
                </button>
              ))}
            </div>
          </>
        )}

      </div>
    </div>
  )
}

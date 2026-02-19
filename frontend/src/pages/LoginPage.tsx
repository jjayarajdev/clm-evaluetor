import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { DocumentTextIcon, ExclamationCircleIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'

const loginSchema = z.object({
  username: z.string().min(1, 'Username is required'),
  password: z.string().min(1, 'Password is required'),
})

type LoginForm = z.infer<typeof loginSchema>

export default function LoginPage() {
  const { user, login } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

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

        {/* Demo credentials */}
        <div className="mt-6 p-4 bg-blue-50 rounded-lg">
          <p className="text-sm text-blue-800 font-medium mb-3">Demo Credentials:</p>
          <div className="text-xs text-blue-700">
            <table className="w-full">
              <thead>
                <tr className="border-b border-blue-200">
                  <th className="text-left py-1 font-semibold">Tenant</th>
                  <th className="text-left py-1 font-semibold">Username</th>
                  <th className="text-left py-1 font-semibold">Password</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-blue-100">
                <tr>
                  <td className="py-1">Acme Corp</td>
                  <td className="py-1 font-mono">admin</td>
                  <td className="py-1 font-mono">admin123</td>
                </tr>
                <tr>
                  <td className="py-1">Acme Corp</td>
                  <td className="py-1 font-mono">legal</td>
                  <td className="py-1 font-mono">legal123</td>
                </tr>
                <tr>
                  <td className="py-1">TechStart</td>
                  <td className="py-1 font-mono">techstart_admin</td>
                  <td className="py-1 font-mono">admin123</td>
                </tr>
                <tr>
                  <td className="py-1">LegalCo</td>
                  <td className="py-1 font-mono">legalco_admin</td>
                  <td className="py-1 font-mono">admin123</td>
                </tr>
                <tr>
                  <td className="py-1 text-blue-600">(Super Admin)</td>
                  <td className="py-1 font-mono">superadmin</td>
                  <td className="py-1 font-mono">admin123</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

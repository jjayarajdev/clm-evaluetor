/* Login — Direction B restyle. Centered token-styled card on var(--pg):
   wordmark, Field inputs, primary submit, SSO as secondary buttons, error as
   banner-da. Auth flow, SSO auto-init/callback, validation and i18n unchanged. */
import { useState, useEffect, useMemo } from 'react'
import { Navigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { useQuery } from '@tanstack/react-query'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useTranslation } from 'react-i18next'
import { ArrowPathIcon, ExclamationCircleIcon, ShieldCheckIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/contexts/AuthContext'
import { client } from '@/lib/api/client'
import { Button, Field } from '@/components/ui'

type LoginForm = { username: string; password: string }

interface SSOProvider {
  tenant_slug: string
  tenant_name: string
  provider: string
  enabled: boolean
}

export default function LoginPage() {
  const { user, login } = useAuth()
  const { t } = useTranslation()
  const loginSchema = useMemo(
    () =>
      z.object({
        username: z.string().min(1, t('auth.usernameRequired')),
        password: z.string().min(1, t('auth.passwordRequired')),
      }),
    [t]
  )
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
      const msg = err instanceof Error ? err.message : t('auth.ssoFailed')
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
      const errorMessage = err instanceof Error ? err.message : t('auth.invalidCredentials')
      setError(errorMessage)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8"
      style={{ background: 'var(--pg)' }}
    >
      <div className="w-full" style={{ maxWidth: 400 }}>
        {/* Wordmark */}
        <div className="row" style={{ justifyContent: 'center', gap: 9 }}>
          <span
            aria-hidden
            style={{
              width: 26, height: 26, borderRadius: 7, flexShrink: 0,
              background: 'var(--p)', color: 'var(--on-p)',
              display: 'grid', placeItems: 'center',
              fontSize: 14, fontWeight: 700, lineHeight: 1,
            }}
          >
            E
          </span>
          <span style={{ fontSize: 'var(--fs-xl)', fontWeight: 600, letterSpacing: '-.3px' }}>
            Evaluetor
          </span>
        </div>
        <p className="muted text-center" style={{ marginTop: 8, fontSize: 'var(--fs-md)' }}>
          {t('auth.subtitle')}
        </p>

        {/* Login card */}
        <div className="card" style={{ marginTop: 24, padding: 24 }}>
          <form className="col" style={{ gap: 14 }} onSubmit={handleSubmit(onSubmit)}>
            {error && (
              <div className="banner banner-da">
                <ExclamationCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
                <span>{error}</span>
              </div>
            )}

            <Field
              label={t('auth.username')}
              type="text"
              autoComplete="username"
              placeholder={t('auth.usernamePlaceholder')}
              error={errors.username?.message}
              {...register('username')}
            />

            <Field
              label={t('auth.password')}
              type="password"
              autoComplete="current-password"
              placeholder={t('auth.passwordPlaceholder')}
              error={errors.password?.message}
              {...register('password')}
            />

            <Button variant="primary" size="lg" type="submit" disabled={isSubmitting} className="w-full">
              {isSubmitting && (
                <ArrowPathIcon className="spin" style={{ width: 15, height: 15, flexShrink: 0 }} aria-hidden />
              )}
              {isSubmitting ? t('auth.signingIn') : t('auth.signIn')}
            </Button>
          </form>

          {/* SSO Login */}
          {ssoProviders && ssoProviders.length > 0 && (
            <>
              <div className="row" style={{ gap: 10, margin: '18px 0 14px' }}>
                <span className="grow" style={{ height: 1, background: 'var(--b)' }} />
                <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('auth.orContinueWith')}</span>
                <span className="grow" style={{ height: 1, background: 'var(--b)' }} />
              </div>

              <div className="col" style={{ gap: 8 }}>
                {ssoProviders.map((p) => (
                  <Button
                    key={p.tenant_slug}
                    variant="secondary"
                    className="w-full"
                    disabled={ssoLoading === p.tenant_slug}
                    onClick={() => handleSSOLogin(p.tenant_slug)}
                  >
                    {ssoLoading === p.tenant_slug ? (
                      <ArrowPathIcon className="spin" style={{ width: 15, height: 15, flexShrink: 0 }} aria-hidden />
                    ) : (
                      <ShieldCheckIcon style={{ width: 15, height: 15, flexShrink: 0, color: 'var(--p)' }} aria-hidden />
                    )}
                    {t('auth.signInWithSso', { tenant: p.tenant_name })}
                  </Button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

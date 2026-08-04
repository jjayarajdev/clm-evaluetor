import { Menu, Transition } from '@headlessui/react'
import { Fragment } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BellIcon, Bars3Icon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/contexts/AuthContext'
import api from '@/lib/api'
import { cn, formatDate } from '@/lib/utils'
import { IconButton } from '@/components/ui'

interface HeaderProps {
  onMenuClick: () => void
}

/* Longest-prefix route → page-title i18n key. Order does not matter; matching picks
   the longest prefix that applies. */
const ROUTE_TITLES: [string, string][] = [
  ['/dashboard', 'nav.dashboard'],
  ['/contracts', 'nav.contracts'],
  ['/groups', 'nav.groups'],
  ['/obligations', 'nav.postSigning'],
  ['/slas', 'nav.postSigning'],
  ['/clauses', 'nav.contracts'],
  ['/post-signing', 'nav.postSigning'],
  ['/renewals', 'nav.renewals'],
  ['/vendors', 'nav.vendors'],
  ['/reports', 'nav.reports'],
  ['/upload', 'nav.upload'],
  ['/query', 'nav.askAi'],
  ['/usage', 'nav.usage'],
  ['/organizations', 'nav.organizations'],
  ['/relationships', 'nav.relationships'],
  ['/kpi-approvals', 'nav.kpiApprovals'],
  ['/surveys', 'nav.surveys'],
  ['/users', 'nav.users'],
  ['/settings', 'nav.settings'],
  ['/admin/business-units', 'nav.businessUnits'],
  ['/admin/external-users', 'nav.externalUsers'],
  ['/admin/integrations/servicenow', 'nav.servicenow'],
  ['/admin/integrations/sharepoint', 'nav.sharepoint'],
  ['/admin/sso', 'nav.sso'],
  ['/admin/industry-profiles', 'nav.industryProfiles'],
  ['/admin/extraction-quality', 'nav.extractionQuality'],
  ['/admin/master-data', 'nav.masterData'],
  ['/admin/scheduler', 'nav.scheduler'],
  ['/super-admin/tenants', 'nav.tenants'],
  ['/super-admin/users', 'nav.allUsers'],
  ['/super-admin/custom-fields', 'nav.customFields'],
  ['/super-admin/role-permissions', 'nav.rolePermissions'],
  ['/super-admin/integrations', 'nav.integrations'],
  ['/super-admin', 'nav.platformOverview'],
]

function titleKeyFor(pathname: string): string | null {
  let best: string | null = null
  let bestLen = 0
  for (const [prefix, key] of ROUTE_TITLES) {
    if (pathname.startsWith(prefix) && prefix.length > bestLen) {
      best = key
      bestLen = prefix.length
    }
  }
  return best
}

const SEVERITY_COLOR: Record<string, string> = {
  high: 'var(--da)',
  medium: 'var(--wa)',
  low: 'var(--f)',
}

function openPalette() {
  window.dispatchEvent(new CustomEvent('ev:open-palette'))
}

export default function Header({ onMenuClick }: HeaderProps) {
  const { user } = useAuth()
  const { t } = useTranslation()
  const location = useLocation()

  const { data: notif } = useQuery({
    queryKey: ['notifications-feed'],
    queryFn: () => api.getNotificationFeed(),
    enabled: !!user,
    refetchInterval: 60000,
    staleTime: 30000,
  })
  const notifCount = notif?.count ?? 0

  const titleKey = titleKeyFor(location.pathname)
  const title = titleKey ? t(titleKey) : 'Evaluetor'
  const crumb = user?.tenant_name

  return (
    <header
      className="row"
      style={{
        height: 'var(--top-h)', flexShrink: 0, gap: 12, padding: '0 16px',
        background: 'var(--s)', borderBottom: '1px solid var(--b)',
      }}
    >
      <IconButton icon={Bars3Icon} label={t('nav.openSidebar')} onClick={onMenuClick} className="lg:hidden" />

      <h1 className="trunc" style={{ fontSize: 'var(--fs-xl)', fontWeight: 600, letterSpacing: '-.3px' }}>{title}</h1>
      {crumb && (
        <span className="faint trunc hidden sm:block" style={{ fontSize: 'var(--fs-md)' }}>/ {crumb}</span>
      )}
      <span className="grow" />

      {/* ⌘K search — full field on desktop, icon on mobile */}
      <button className="inp hidden lg:flex" onClick={openPalette} style={{ width: 260, cursor: 'pointer', color: 'var(--f)' }}>
        <MagnifyingGlassIcon style={{ width: 15, height: 15, flexShrink: 0 }} aria-hidden />
        <span className="grow" style={{ textAlign: 'left', fontSize: 'var(--fs-md)' }}>
          {t('commandPalette.placeholder', { defaultValue: 'Search or jump to' })}
        </span>
        <span className="kbd mono">⌘K</span>
      </button>
      <IconButton icon={MagnifyingGlassIcon} label={t('common.search', { defaultValue: 'Search' })} onClick={openPalette} className="lg:hidden" />

      {/* Notifications */}
      <Menu as="div" className="relative">
        <Menu.Button as={Fragment}>
          <IconButton icon={BellIcon} label={t('nav.viewNotifications')} />
        </Menu.Button>
        {notifCount > 0 && (
          <span
            className="num"
            style={{
              position: 'absolute', top: -2, right: -2, minWidth: 16, height: 16, padding: '0 4px',
              borderRadius: 'var(--r-full)', background: 'var(--da)', color: '#fff',
              fontSize: 10, fontWeight: 600, display: 'inline-grid', placeItems: 'center', pointerEvents: 'none',
            }}
          >
            {notifCount > 9 ? '9+' : notifCount}
          </span>
        )}
        <Transition
          as={Fragment}
          enter="transition ease-out duration-100"
          enterFrom="transform opacity-0 scale-95"
          enterTo="transform opacity-100 scale-100"
          leave="transition ease-in duration-75"
          leaveFrom="transform opacity-100 scale-100"
          leaveTo="transform opacity-0 scale-95"
        >
          <Menu.Items
            className="menu focus:outline-none flex flex-col"
            style={{ right: 0, top: '100%', width: 384, maxWidth: 'calc(100vw - 2rem)', maxHeight: '70vh', padding: 0 }}
          >
            <div className="row" style={{ padding: '10px 14px', borderBottom: '1px solid var(--b)' }}>
              <p className="grow" style={{ fontSize: 'var(--fs-md)', fontWeight: 600 }}>
                {t('notifFeed.title', { defaultValue: 'Notifications' })}
              </p>
              {notifCount > 0 && (
                <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>
                  {t('notifFeed.count', { defaultValue: '{{count}} needing attention', count: notifCount })}
                </span>
              )}
            </div>
            <div className="scroll" style={{ flex: 1, padding: 5 }}>
              {!notif || notif.items.length === 0 ? (
                <div className="empty" style={{ padding: '28px 16px' }}>
                  <BellIcon style={{ width: 28, height: 28, color: 'var(--b2)' }} aria-hidden />
                  <p>{t('notifFeed.empty', { defaultValue: "You're all caught up" })}</p>
                </div>
              ) : (
                notif.items.map((item) => (
                  <Menu.Item key={item.id}>
                    {({ active }) => (
                      <Link to={item.link} className={cn('mi', active && 'bg-[var(--s2)]')} style={{ height: 'auto', padding: '8px', alignItems: 'flex-start', textDecoration: 'none' }}>
                        <span
                          style={{
                            marginTop: 6, width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                            background: SEVERITY_COLOR[item.severity] || 'var(--f)',
                          }}
                        />
                        <span className="grow" style={{ minWidth: 0 }}>
                          <span className="row" style={{ gap: 8 }}>
                            <span className="tag">{t(`notifFeed.labels.${item.label}`, { defaultValue: item.label })}</span>
                            <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{formatDate(item.date)}</span>
                          </span>
                          <span className="trunc" style={{ display: 'block', fontSize: 'var(--fs-md)', marginTop: 2 }}>{item.title}</span>
                          {item.subtitle && (
                            <span className="trunc faint" style={{ display: 'block', fontSize: 'var(--fs-sm)' }}>{item.subtitle}</span>
                          )}
                        </span>
                      </Link>
                    )}
                  </Menu.Item>
                ))
              )}
            </div>
          </Menu.Items>
        </Transition>
      </Menu>
    </header>
  )
}

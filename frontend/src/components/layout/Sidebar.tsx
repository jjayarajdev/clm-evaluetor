import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  ArrowRightOnRectangleIcon,
  ArrowUpTrayIcon,
  AdjustmentsHorizontalIcon,
  BeakerIcon,
  BuildingLibraryIcon,
  BuildingOffice2Icon,
  ChartBarIcon,
  ChartPieIcon,
  ChatBubbleLeftRightIcon,
  ChevronRightIcon,
  CircleStackIcon,
  ClipboardDocumentCheckIcon,
  ClipboardDocumentListIcon,
  ClockIcon,
  ChartBarSquareIcon,
  CloudArrowUpIcon,
  Cog6ToothIcon,
  DocumentChartBarIcon,
  DocumentTextIcon,
  FolderIcon,
  GlobeAltIcon,
  LanguageIcon,
  LinkIcon,
  MoonIcon,
  ShieldCheckIcon,
  Squares2X2Icon,
  SunIcon,
  SwatchIcon,
  UserCircleIcon,
  UserGroupIcon,
  UsersIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/contexts/AuthContext'
import { useTheme } from '@/contexts/ThemeContext'
import { can, type Permission } from '@/lib/rbac'
import { setAppLanguage, type AppLanguage } from '@/i18n'
import api from '@/lib/api'
import { cn, userDisplayName, userInitials } from '@/lib/utils'
import { Avatar, IconButton, type IconType } from '@/components/ui'

interface SidebarProps {
  open: boolean
  onClose: () => void
}

interface NavItem {
  name: string
  href: string
  icon: IconType
  permission: Permission
}

interface NavGroup {
  label: string
  items: NavItem[]
}

// ── Navigation Structure (Direction B: module-grouped) ────────────
// `name` holds an i18n key, translated at render time via t(item.name).
// Visibility is driven entirely by `permission` via can() — the role→permission
// map lives in src/lib/rbac.ts (single source of truth).

const NAV_SECTIONS: { label: string | null; items: NavItem[] }[] = [
  {
    label: null,
    items: [{ name: 'nav.dashboard', href: '/dashboard', icon: Squares2X2Icon, permission: 'dashboard' }],
  },
  {
    label: 'nav.sectionIntelligence',
    items: [
      { name: 'nav.contracts', href: '/contracts', icon: DocumentTextIcon, permission: 'contracts' },
      { name: 'nav.groups', href: '/groups', icon: FolderIcon, permission: 'groups' },
      { name: 'nav.upload', href: '/upload', icon: ArrowUpTrayIcon, permission: 'upload' },
      { name: 'nav.askAi', href: '/query', icon: ChatBubbleLeftRightIcon, permission: 'askAi' },
      { name: 'nav.reports', href: '/reports', icon: DocumentChartBarIcon, permission: 'reports' },
    ],
  },
  {
    label: 'nav.sectionPostSigning',
    items: [
      { name: 'nav.postSigning', href: '/post-signing', icon: ClipboardDocumentCheckIcon, permission: 'postSigning' },
      { name: 'nav.renewals', href: '/renewals', icon: ClockIcon, permission: 'renewals' },
      { name: 'nav.vendors', href: '/vendors', icon: BuildingOffice2Icon, permission: 'vendors' },
    ],
  },
  {
    label: 'nav.sectionGovernance',
    items: [
      { name: 'nav.organizations', href: '/organizations', icon: BuildingLibraryIcon, permission: 'organizations' },
      { name: 'nav.relationships', href: '/relationships', icon: LinkIcon, permission: 'relationships' },
      { name: 'nav.kpiApprovals', href: '/kpi-approvals', icon: ChartBarIcon, permission: 'kpiApprovals' },
      { name: 'nav.surveys', href: '/surveys', icon: ClipboardDocumentListIcon, permission: 'surveys' },
    ],
  },
]

const usageItem: NavItem = { name: 'nav.usage', href: '/usage', icon: ChartPieIcon, permission: 'usage' }

const adminGroups: NavGroup[] = [
  {
    label: 'nav.usersAccess',
    items: [
      { name: 'nav.users', href: '/users', icon: UsersIcon, permission: 'admin' },
      { name: 'nav.businessUnits', href: '/admin/business-units', icon: BuildingOffice2Icon, permission: 'admin' },
      { name: 'nav.externalUsers', href: '/admin/external-users', icon: UserGroupIcon, permission: 'admin' },
    ],
  },
  {
    label: 'nav.integrations',
    items: [
      { name: 'nav.servicenow', href: '/admin/integrations/servicenow', icon: CloudArrowUpIcon, permission: 'admin' },
      { name: 'nav.sharepoint', href: '/admin/integrations/sharepoint', icon: FolderIcon, permission: 'admin' },
      { name: 'nav.sso', href: '/admin/sso', icon: ShieldCheckIcon, permission: 'admin' },
    ],
  },
  {
    label: 'nav.system',
    items: [
      { name: 'nav.industryProfiles', href: '/admin/industry-profiles', icon: SwatchIcon, permission: 'admin' },
      { name: 'nav.extractionQuality', href: '/admin/extraction-quality', icon: BeakerIcon, permission: 'admin' },
      { name: 'nav.masterData', href: '/admin/master-data', icon: CircleStackIcon, permission: 'admin' },
      { name: 'nav.scheduler', href: '/admin/scheduler', icon: ClockIcon, permission: 'admin' },
      { name: 'nav.settings', href: '/settings', icon: Cog6ToothIcon, permission: 'settings' },
    ],
  },
]

const superAdminNav: NavItem[] = [
  { name: 'nav.platformOverview', href: '/super-admin', icon: GlobeAltIcon, permission: 'superadmin' },
  { name: 'nav.tenants', href: '/super-admin/tenants', icon: BuildingOffice2Icon, permission: 'superadmin' },
  { name: 'nav.allUsers', href: '/super-admin/users', icon: UserGroupIcon, permission: 'superadmin' },
  { name: 'nav.extractionQuality', href: '/admin/extraction-quality', icon: BeakerIcon, permission: 'superadmin' },
  { name: 'nav.industryProfiles', href: '/admin/industry-profiles', icon: SwatchIcon, permission: 'superadmin' },
  { name: 'nav.customFields', href: '/super-admin/custom-fields', icon: AdjustmentsHorizontalIcon, permission: 'superadmin' },
  { name: 'nav.rolePermissions', href: '/super-admin/role-permissions', icon: ShieldCheckIcon, permission: 'superadmin' },
  { name: 'nav.integrations', href: '/super-admin/integrations', icon: CloudArrowUpIcon, permission: 'superadmin' },
  { name: 'nav.fleetUsage', href: '/super-admin/usage', icon: ChartBarSquareIcon, permission: 'superadmin' },
]

const LANGUAGES: { code: AppLanguage; labelKey: string }[] = [
  { code: 'en', labelKey: 'common.english' },
  { code: 'fr', labelKey: 'common.french' },
]

// ── Pieces ────────────────────────────────────────────────────────

function Wordmark() {
  return (
    <div className="row" style={{ gap: 9, padding: '4px 8px' }}>
      <span
        style={{
          width: 26, height: 26, borderRadius: 7, background: 'var(--p)', color: 'var(--on-p)',
          display: 'grid', placeItems: 'center', fontSize: 14, fontWeight: 700, flexShrink: 0,
        }}
      >
        E
      </span>
      <span style={{ fontSize: 'var(--fs-xl)', fontWeight: 600, letterSpacing: '-.4px' }}>Evaluetor</span>
    </div>
  )
}

function NavItemLink({ item, onClose }: { item: NavItem; onClose: () => void }) {
  const { t } = useTranslation()
  const label = t(item.name)
  return (
    <NavLink
      to={item.href}
      onClick={onClose}
      className="row"
      style={({ isActive }) => ({
        gap: 10, width: '100%', height: 34, padding: '0 10px', borderRadius: 'var(--r-sm)',
        background: isActive ? 'var(--p-f)' : undefined,
        color: isActive ? 'var(--p)' : 'var(--m)',
        fontSize: 'var(--fs-md)', fontWeight: isActive ? 600 : 500,
        textDecoration: 'none',
      })}
    >
      <item.icon style={{ width: 16, height: 16, flexShrink: 0 }} aria-hidden />
      <span className="grow trunc">{label}</span>
    </NavLink>
  )
}

/* Admin flyout — one trigger for the deep admin tree, panel opens to the right. */
function AdminFlyout({ allow, onClose }: { allow: (p: Permission) => boolean; onClose: () => void }) {
  const { t } = useTranslation()
  const location = useLocation()
  const [isOpen, setIsOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const [panelPos, setPanelPos] = useState({ bottom: 0, left: 0 })

  const allItems = adminGroups.flatMap((g) => g.items.filter((i) => allow(i.permission)))
  const hasActiveChild = allItems.some((i) => location.pathname.startsWith(i.href))

  useEffect(() => {
    if (!isOpen) return
    const handle = (e: MouseEvent) => {
      const target = e.target as Node
      if (
        triggerRef.current && !triggerRef.current.contains(target) &&
        panelRef.current && !panelRef.current.contains(target)
      ) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [isOpen])

  useEffect(() => setIsOpen(false), [location.pathname])

  useEffect(() => {
    if (isOpen && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect()
      setPanelPos({ bottom: window.innerHeight - rect.bottom, left: rect.right + 8 })
    }
  }, [isOpen])

  if (allItems.length === 0) return null

  return (
    <>
      <button
        ref={triggerRef}
        onClick={() => setIsOpen(!isOpen)}
        className="row"
        style={{
          gap: 10, width: '100%', height: 34, padding: '0 10px', border: 0, borderRadius: 'var(--r-sm)',
          background: isOpen || hasActiveChild ? 'var(--p-f)' : 'transparent',
          color: isOpen || hasActiveChild ? 'var(--p)' : 'var(--m)',
          fontSize: 'var(--fs-md)', fontWeight: isOpen || hasActiveChild ? 600 : 500,
          cursor: 'pointer', textAlign: 'left',
        }}
      >
        <Cog6ToothIcon style={{ width: 16, height: 16, flexShrink: 0 }} aria-hidden />
        <span className="grow trunc">{t('nav.administration')}</span>
        <ChevronRightIcon
          style={{ width: 13, height: 13, flexShrink: 0, transition: 'transform .2s var(--ease)', transform: isOpen ? 'rotate(90deg)' : undefined }}
          aria-hidden
        />
      </button>

      {isOpen &&
        createPortal(
          <div
            ref={panelRef}
            className="menu"
            style={{
              position: 'fixed', bottom: panelPos.bottom, left: panelPos.left, top: 'auto',
              minWidth: 230, maxHeight: '70vh', overflowY: 'auto', zIndex: 95,
            }}
          >
            {adminGroups.map((group, gi) => {
              const items = group.items.filter((i) => allow(i.permission))
              if (items.length === 0) return null
              return (
                <div key={group.label}>
                  {gi > 0 && <div className="msep" />}
                  <div className="sec-t" style={{ padding: '7px 8px 4px' }}>{t(group.label)}</div>
                  {items.map((item) => (
                    <NavLink
                      key={item.name}
                      to={item.href}
                      onClick={() => { setIsOpen(false); onClose() }}
                      className={({ isActive }) => cn('mi', isActive && 'on')}
                      style={({ isActive }) => ({
                        textDecoration: 'none',
                        background: isActive ? 'var(--p-f)' : undefined,
                        color: isActive ? 'var(--p)' : undefined,
                      })}
                    >
                      <item.icon style={{ width: 15, height: 15, flexShrink: 0, color: 'var(--m)' }} aria-hidden />
                      {t(item.name)}
                    </NavLink>
                  ))}
                </div>
              )
            })}
          </div>,
          document.body
        )}
    </>
  )
}

/* Bottom-anchored user card opening an upward menu: profile + sign out. */
function UserMenu({ onClose }: { onClose: () => void }) {
  const { user, logout } = useAuth()
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const key = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', handle)
    document.addEventListener('keydown', key)
    return () => {
      document.removeEventListener('mousedown', handle)
      document.removeEventListener('keydown', key)
    }
  }, [open])

  if (!user) return null
  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        className="row"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        style={{
          gap: 9, width: '100%', padding: '7px 8px', border: '1px solid var(--b)', borderRadius: 'var(--r-md)',
          background: 'var(--s)', cursor: 'pointer', textAlign: 'left',
        }}
      >
        <Avatar name={userDisplayName(user)} initials={userInitials(user)} size={28} />
        <span className="grow" style={{ minWidth: 0 }}>
          <span className="trunc" style={{ display: 'block', fontSize: 'var(--fs-md)', fontWeight: 600 }}>
            {userDisplayName(user)}
          </span>
          <span className="trunc" style={{ display: 'block', fontSize: 'var(--fs-2xs)', color: 'var(--f)' }}>
            {t(`roles.${user.role}`)}{user.tenant_name ? ` · ${user.tenant_name}` : ''}
          </span>
        </span>
      </button>
      {open && (
        <div className="menu" style={{ bottom: '100%', left: 0, right: 0, top: 'auto', marginBottom: 6, minWidth: 0 }}>
          <div
            className="mi"
            role="menuitem"
            onClick={() => { setOpen(false); onClose(); navigate('/settings') }}
          >
            <UserCircleIcon style={{ width: 15, height: 15, color: 'var(--m)' }} aria-hidden />
            {t('nav.profile')}
          </div>
          <div className="msep" />
          <div className="mi" role="menuitem" onClick={() => logout()}>
            <ArrowRightOnRectangleIcon style={{ width: 15, height: 15, color: 'var(--m)' }} aria-hidden />
            {t('nav.signOut')}
          </div>
        </div>
      )}
    </div>
  )
}

function LanguageSwitcher() {
  const { user } = useAuth()
  const { t, i18n } = useTranslation()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  const changeLanguage = async (code: AppLanguage) => {
    setAppLanguage(code)
    setOpen(false)
    if (user) {
      try {
        await api.updateMyPreferences(code)
      } catch {
        // Preference persists locally even if the API call fails
      }
    }
  }

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-flex' }}>
      <IconButton icon={LanguageIcon} label={t('common.language')} onClick={() => setOpen((o) => !o)} />
      {open && (
        <div className="menu" style={{ bottom: '100%', left: 0, top: 'auto', marginBottom: 6, minWidth: 140 }}>
          {LANGUAGES.map(({ code, labelKey }) => (
            <div
              key={code}
              className="mi"
              role="menuitem"
              style={i18n.language === code ? { color: 'var(--p)', fontWeight: 600 } : undefined}
              onClick={() => changeLanguage(code)}
            >
              {t(labelKey)}
              {i18n.language === code && <span className="kb">✓</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main Sidebar ──────────────────────────────────────────────────

export default function Sidebar({ open, onClose }: SidebarProps) {
  const { user } = useAuth()
  const { t, i18n } = useTranslation()
  const { theme, toggle } = useTheme()

  const allow = (p: Permission) => can(user, p)
  const sections = NAV_SECTIONS
    .map((sec) => ({ ...sec, items: sec.items.filter((i) => allow(i.permission)) }))
    .filter((sec) => sec.items.length > 0)
  const showUsage = allow(usageItem.permission)
  const hasAdmin = allow('admin')
  const filteredSuperAdmin = superAdminNav.filter((i) => allow(i.permission))

  const sidebarContent = (
    <nav
      className="col"
      aria-label="Main navigation"
      style={{
        width: 'var(--nav-w)', flexShrink: 0, height: '100%',
        background: 'var(--s)', borderRight: '1px solid var(--b)',
      }}
    >
      <div className="row" style={{ padding: '12px 12px 8px', gap: 8 }}>
        <Wordmark />
        <span className="grow" />
        <IconButton icon={XMarkIcon} label={t('nav.closeSidebar')} onClick={onClose} className="lg:hidden" />
      </div>

      <div className="scroll grow" style={{ padding: '4px 10px 10px' }}>
        {sections.map((sec, n) => (
          <div key={sec.label || n} style={{ marginBottom: 4 }}>
            {sec.label && <div className="sec-t" style={{ padding: '14px 10px 6px' }}>{t(sec.label)}</div>}
            {sec.items.map((item) => (
              <NavItemLink key={item.name} item={item} onClose={onClose} />
            ))}
          </div>
        ))}

        {(showUsage || hasAdmin) && (
          <div style={{ marginBottom: 4 }}>
            <div className="sec-t" style={{ padding: '14px 10px 6px' }}>{t('nav.sectionAdmin')}</div>
            {showUsage && <NavItemLink item={usageItem} onClose={onClose} />}
            {hasAdmin && <AdminFlyout allow={allow} onClose={onClose} />}
          </div>
        )}

        {filteredSuperAdmin.length > 0 && (
          <div style={{ marginBottom: 4 }}>
            <div className="sec-t" style={{ padding: '14px 10px 6px' }}>{t('nav.sectionSuperAdmin')}</div>
            {filteredSuperAdmin.map((item) => (
              <NavItemLink key={item.name} item={item} onClose={onClose} />
            ))}
          </div>
        )}
      </div>

      <div style={{ padding: 10, borderTop: '1px solid var(--b)' }}>
        <div className="row" style={{ gap: 6, marginBottom: 8 }}>
          <IconButton
            icon={theme === 'dark' ? SunIcon : MoonIcon}
            label={t('nav.toggleTheme')}
            onClick={toggle}
          />
          <LanguageSwitcher />
          <span className="grow" />
          <span className="faint mono" style={{ fontSize: 'var(--fs-2xs)', textTransform: 'uppercase' }}>
            {i18n.language}
          </span>
        </div>
        <UserMenu onClose={onClose} />
      </div>
    </nav>
  )

  return (
    <>
      {/* Mobile: scrim + drawer */}
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" style={{ background: 'rgba(9,9,11,.45)' }} onClick={onClose} aria-hidden="true" />
      )}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 transform transition-transform duration-300 ease-in-out lg:hidden',
          open ? 'translate-x-0' : '-translate-x-full'
        )}
        role="dialog"
        aria-modal="true"
        aria-label="Mobile navigation"
      >
        {sidebarContent}
      </div>

      {/* Desktop: in-flow fixed-width column */}
      <div className="hidden lg:flex h-full flex-shrink-0">{sidebarContent}</div>
    </>
  )
}

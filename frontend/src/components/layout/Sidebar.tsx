import { useState, useRef, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { NavLink, useLocation } from 'react-router-dom'
import {
  HomeIcon,
  DocumentTextIcon,
  CloudArrowUpIcon,
  ChatBubbleLeftRightIcon,
  UsersIcon,
  Cog6ToothIcon,
  XMarkIcon,
  ClipboardDocumentCheckIcon,
  CalendarDaysIcon,
  BuildingOffice2Icon,
  DocumentChartBarIcon,
  CircleStackIcon,
  ClockIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  GlobeAltIcon,
  AdjustmentsHorizontalIcon,
  UserGroupIcon,
  BuildingLibraryIcon,
  LinkIcon,
  ClipboardDocumentListIcon,
  ShieldCheckIcon,
  BeakerIcon,
  FolderIcon,
  SwatchIcon,
} from '@heroicons/react/24/outline'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/contexts/AuthContext'
import { useSidebar } from '@/contexts/SidebarContext'
import { cn } from '@/lib/utils'

interface SidebarProps {
  open: boolean
  onClose: () => void
}

interface NavItem {
  name: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  roles: string[]
}

interface NavGroup {
  label: string
  items: NavItem[]
  collapsible?: boolean
}

// ── Navigation Structure ──────────────────────────────────────────
// `name` holds an i18n key, translated at render time via t(item.name)

const mainSection: NavItem[] = [
  { name: 'nav.dashboard', href: '/dashboard', icon: HomeIcon, roles: ['admin', 'legal', 'procurement', 'bu_head'] },
  { name: 'nav.contracts', href: '/contracts', icon: DocumentTextIcon, roles: ['admin', 'legal', 'procurement', 'bu_head'] },
  { name: 'nav.compliance', href: '/compliance', icon: ClipboardDocumentCheckIcon, roles: ['admin', 'legal', 'procurement', 'bu_head'] },
  { name: 'nav.renewals', href: '/renewals', icon: CalendarDaysIcon, roles: ['admin', 'legal', 'procurement', 'bu_head'] },
]

const managementSection: NavItem[] = [
  { name: 'nav.vendors', href: '/vendors', icon: BuildingOffice2Icon, roles: ['admin', 'procurement', 'bu_head'] },
  { name: 'nav.reports', href: '/reports', icon: DocumentChartBarIcon, roles: ['admin', 'legal', 'bu_head'] },
  { name: 'nav.upload', href: '/upload', icon: CloudArrowUpIcon, roles: ['admin', 'legal', 'procurement'] },
]

const governanceSection: NavItem[] = [
  { name: 'nav.organizations', href: '/organizations', icon: BuildingLibraryIcon, roles: ['admin', 'legal', 'procurement'] },
  { name: 'nav.relationships', href: '/relationships', icon: LinkIcon, roles: ['admin', 'legal', 'procurement'] },
  { name: 'nav.kpiApprovals', href: '/kpi-approvals', icon: ShieldCheckIcon, roles: ['admin'] },
  { name: 'nav.surveys', href: '/surveys', icon: ClipboardDocumentListIcon, roles: ['admin', 'legal'] },
]

const intelligenceSection: NavItem[] = [
  { name: 'nav.askAi', href: '/query', icon: ChatBubbleLeftRightIcon, roles: ['admin', 'legal', 'procurement'] },
]

const adminGroups: NavGroup[] = [
  {
    label: 'nav.usersAccess',
    collapsible: true,
    items: [
      { name: 'nav.users', href: '/users', icon: UsersIcon, roles: ['admin'] },
      { name: 'nav.businessUnits', href: '/admin/business-units', icon: BuildingOffice2Icon, roles: ['admin'] },
      { name: 'nav.externalUsers', href: '/admin/external-users', icon: UserGroupIcon, roles: ['admin'] },
    ],
  },
  {
    label: 'nav.integrations',
    collapsible: true,
    items: [
      { name: 'nav.servicenow', href: '/admin/integrations/servicenow', icon: CloudArrowUpIcon, roles: ['admin'] },
      { name: 'nav.sharepoint', href: '/admin/integrations/sharepoint', icon: FolderIcon, roles: ['admin'] },
      { name: 'nav.sso', href: '/admin/sso', icon: ShieldCheckIcon, roles: ['admin'] },
    ],
  },
  {
    label: 'nav.system',
    collapsible: true,
    items: [
      { name: 'nav.industryProfiles', href: '/admin/industry-profiles', icon: SwatchIcon, roles: ['admin'] },
      { name: 'nav.extractionQuality', href: '/admin/extraction-quality', icon: BeakerIcon, roles: ['admin'] },
      { name: 'nav.masterData', href: '/admin/master-data', icon: CircleStackIcon, roles: ['admin'] },
      { name: 'nav.scheduler', href: '/admin/scheduler', icon: ClockIcon, roles: ['admin'] },
      { name: 'nav.settings', href: '/settings', icon: Cog6ToothIcon, roles: ['admin'] },
    ],
  },
]

const superAdminNav: NavItem[] = [
  { name: 'nav.platformOverview', href: '/super-admin', icon: GlobeAltIcon, roles: ['super_admin'] },
  { name: 'nav.tenants', href: '/super-admin/tenants', icon: BuildingOffice2Icon, roles: ['super_admin'] },
  { name: 'nav.allUsers', href: '/super-admin/users', icon: UserGroupIcon, roles: ['super_admin'] },
  { name: 'nav.extractionQuality', href: '/admin/extraction-quality', icon: BeakerIcon, roles: ['super_admin'] },
  { name: 'nav.industryProfiles', href: '/admin/industry-profiles', icon: SwatchIcon, roles: ['super_admin'] },
  { name: 'nav.customFields', href: '/super-admin/custom-fields', icon: AdjustmentsHorizontalIcon, roles: ['super_admin'] },
  { name: 'nav.integrations', href: '/super-admin/integrations', icon: CloudArrowUpIcon, roles: ['super_admin'] },
]

// ── Section Label ─────────────────────────────────────────────────

function SectionLabel({ label, collapsed }: { label: string; collapsed: boolean }) {
  const { t } = useTranslation()
  if (collapsed) return null
  return (
    <p className="px-3 pt-1 pb-1 text-[11px] font-medium text-gray-500 uppercase tracking-wider">
      {t(label)}
    </p>
  )
}

// ── Nav Item Component ────────────────────────────────────────────

function NavItemLink({
  item,
  onClose,
  collapsed,
  indent = false,
}: {
  item: NavItem
  onClose: () => void
  collapsed: boolean
  indent?: boolean
}) {
  const [showTooltip, setShowTooltip] = useState(false)
  const { t } = useTranslation()
  const label = t(item.name)

  return (
    <div className="relative">
      <NavLink
        to={item.href}
        onClick={onClose}
        onMouseEnter={() => collapsed && setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        aria-label={label}
        title={label}
        className={({ isActive }) =>
          cn(
            'flex items-center gap-3 rounded-lg transition-all duration-150',
            collapsed
              ? 'justify-center w-10 h-10'
              : indent
                ? 'pl-7 pr-3 py-2'
                : 'px-3 py-2',
            isActive
              ? 'bg-white/15 text-white'
              : 'text-gray-300 hover:bg-white/10 hover:text-white'
          )
        }
      >
        {({ isActive }) => (
          <>
            <item.icon
              className={cn(
                indent ? 'h-4 w-4' : 'h-5 w-5',
                'shrink-0',
                isActive ? 'text-white' : 'text-gray-400'
              )}
              aria-hidden="true"
            />
            {!collapsed && (
              <span className={cn('font-medium truncate', indent ? 'text-[13px]' : 'text-sm')}>{label}</span>
            )}
          </>
        )}
      </NavLink>

      {collapsed && showTooltip && (
        <div className="absolute left-full ml-2 top-1/2 -translate-y-1/2 z-50" role="tooltip">
          <div className="bg-gray-900 text-white text-xs font-medium px-2.5 py-1.5 rounded-md whitespace-nowrap shadow-lg">
            {label}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Flyout Menu Component (slides out to the right) ──────────────

function FlyoutMenu({
  groups,
  userRole,
  onClose,
  collapsed,
  triggerIcon: TriggerIcon,
  triggerLabel,
}: {
  groups: NavGroup[]
  userRole: string
  onClose: () => void
  collapsed: boolean
  triggerIcon: React.ComponentType<{ className?: string }>
  triggerLabel: string
}) {
  const { t } = useTranslation()
  const location = useLocation()
  const [isOpen, setIsOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const [panelPos, setPanelPos] = useState({ bottom: 0, left: 0 })

  // All items across groups for this role
  const allItems = groups.flatMap((g) => g.items.filter((item) => item.roles.includes(userRole)))
  const hasActiveChild = allItems.some((item) => location.pathname.startsWith(item.href))

  // Position the flyout panel next to the trigger button, growing upward
  const updatePosition = useCallback(() => {
    if (!triggerRef.current) return
    const rect = triggerRef.current.getBoundingClientRect()
    setPanelPos({
      bottom: window.innerHeight - rect.bottom,
      left: rect.right + 8,
    })
  }, [])

  // Close flyout on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node
      if (
        triggerRef.current && !triggerRef.current.contains(target) &&
        panelRef.current && !panelRef.current.contains(target)
      ) {
        setIsOpen(false)
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  // Close flyout on route change
  useEffect(() => {
    setIsOpen(false)
  }, [location.pathname])

  // Recalculate position when opening
  useEffect(() => {
    if (isOpen) updatePosition()
  }, [isOpen, updatePosition])

  if (allItems.length === 0) return null

  return (
    <>
      {/* Trigger button */}
      <button
        ref={triggerRef}
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'flex items-center gap-3 rounded-lg transition-all duration-150 w-full',
          collapsed
            ? 'justify-center w-10 h-10'
            : 'px-3 py-2',
          isOpen
            ? 'bg-white/20 text-white'
            : hasActiveChild
              ? 'bg-white/15 text-white'
              : 'text-gray-300 hover:bg-white/10 hover:text-white'
        )}
      >
        <TriggerIcon
          className={cn(
            'h-5 w-5 shrink-0',
            isOpen || hasActiveChild ? 'text-white' : 'text-gray-400'
          )}
        />
        {!collapsed && (
          <>
            <span className="text-sm font-medium truncate flex-1 text-left">{t(triggerLabel)}</span>
            <ChevronRightIcon className={cn(
              'h-3.5 w-3.5 shrink-0 transition-transform duration-200',
              isOpen && 'rotate-90'
            )} />
          </>
        )}
      </button>

      {/* Flyout panel — rendered via portal to escape sidebar overflow */}
      {isOpen && createPortal(
        <div
          ref={panelRef}
          className="fixed z-[9999] rounded-xl bg-primary-900 border border-white/15 shadow-2xl"
          style={{
            bottom: `${panelPos.bottom}px`,
            left: `${panelPos.left}px`,
            animation: 'flyoutIn 150ms ease-out',
            minWidth: '220px',
          }}
        >
          {/* Flyout header */}
          <div className="px-4 py-3 border-b border-white/10">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{t(triggerLabel)}</p>
          </div>

          {/* Groups */}
          <div className="py-2 max-h-[60vh] overflow-y-auto">
            {groups.map((group, gi) => {
              const items = group.items.filter((item) => item.roles.includes(userRole))
              if (items.length === 0) return null
              return (
                <div key={group.label}>
                  {gi > 0 && <div className="border-t border-white/10 my-1.5 mx-3" />}
                  <p className="px-4 pt-2 pb-1 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                    {t(group.label)}
                  </p>
                  {items.map((item) => (
                    <NavLink
                      key={item.name}
                      to={item.href}
                      onClick={() => {
                        setIsOpen(false)
                        onClose()
                      }}
                      className={({ isActive }) =>
                        cn(
                          'flex items-center gap-3 mx-2 px-3 py-2 rounded-lg text-sm transition-all duration-150',
                          isActive
                            ? 'bg-white/15 text-white'
                            : 'text-gray-300 hover:bg-white/10 hover:text-white'
                        )
                      }
                    >
                      {({ isActive }) => (
                        <>
                          <item.icon
                            className={cn('h-4 w-4 shrink-0', isActive ? 'text-white' : 'text-gray-400')}
                          />
                          <span className="font-medium">{t(item.name)}</span>
                        </>
                      )}
                    </NavLink>
                  ))}
                </div>
              )
            })}
          </div>
        </div>,
        document.body
      )}
    </>
  )
}

// ── Nav Section (label + items) ───────────────────────────────────

function NavSection({
  label,
  items,
  role,
  onClose,
  collapsed,
}: {
  label: string
  items: NavItem[]
  role: string
  onClose: () => void
  collapsed: boolean
}) {
  const filtered = items.filter((item) => item.roles.includes(role))
  if (filtered.length === 0) return null

  return (
    <>
      <SectionLabel label={label} collapsed={collapsed} />
      {filtered.map((item) => (
        <NavItemLink key={item.name} item={item} onClose={onClose} collapsed={collapsed} />
      ))}
    </>
  )
}

// ── Main Sidebar ──────────────────────────────────────────────────

export default function Sidebar({ open, onClose }: SidebarProps) {
  const { user } = useAuth()
  const { t } = useTranslation()
  const { collapsed, toggleCollapsed } = useSidebar()

  const role = user?.role || ''
  const filteredMain = mainSection.filter((item) => item.roles.includes(role))
  const filteredMgmt = managementSection.filter((item) => item.roles.includes(role))
  const filteredGov = governanceSection.filter((item) => item.roles.includes(role))
  const filteredIntel = intelligenceSection.filter((item) => item.roles.includes(role))
  const filteredSuperAdmin = superAdminNav.filter((item) => item.roles.includes(role))
  const hasAdmin = role === 'admin'
  const hasSuperAdmin = role === 'super_admin'

  const sidebarWidth = collapsed ? 'w-[60px]' : 'w-[220px]'

  const sidebarContent = (
    <div className={cn(
      'flex h-full flex-col bg-primary-800 transition-all duration-200',
      sidebarWidth
    )}>
      {/* Logo & Toggle */}
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-white/10 px-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="h-8 w-8 shrink-0 rounded-lg bg-primary-600 flex items-center justify-center">
            <span className="text-white font-bold text-sm">E</span>
          </div>
          {!collapsed && (
            <span className="text-base font-semibold text-white truncate">
              Evaluetor
            </span>
          )}
        </div>
        <button
          onClick={toggleCollapsed}
          className={cn(
            'p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-white/10 transition-colors',
            collapsed && 'absolute -right-3 top-4 bg-primary-800 border border-white/20 shadow-lg z-10'
          )}
          aria-label={collapsed ? t('nav.expandSidebar') : t('nav.collapseSidebar')}
          title={collapsed ? t('nav.expandSidebar') : t('nav.collapseSidebar')}
        >
          {collapsed ? (
            <ChevronRightIcon className="h-4 w-4" aria-hidden="true" />
          ) : (
            <ChevronLeftIcon className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav
        className={cn(
          'flex-1 flex flex-col py-4 overflow-y-auto',
          collapsed ? 'items-center space-y-1' : 'px-3 space-y-0.5'
        )}
        aria-label="Main navigation"
      >
        {/* MAIN */}
        {filteredMain.length > 0 && (
          <NavSection label="nav.sectionMain" items={mainSection} role={role} onClose={onClose} collapsed={collapsed} />
        )}

        {/* MANAGEMENT */}
        {filteredMgmt.length > 0 && (
          <>
            <div className={cn('border-t border-white/10 !my-3', collapsed ? 'w-6' : 'w-full')} />
            <NavSection label="nav.sectionManagement" items={managementSection} role={role} onClose={onClose} collapsed={collapsed} />
          </>
        )}

        {/* GOVERNANCE */}
        {filteredGov.length > 0 && (
          <>
            <div className={cn('border-t border-white/10 !my-3', collapsed ? 'w-6' : 'w-full')} />
            <NavSection label="nav.sectionGovernance" items={governanceSection} role={role} onClose={onClose} collapsed={collapsed} />
          </>
        )}

        {/* INTELLIGENCE */}
        {filteredIntel.length > 0 && (
          <>
            <div className={cn('border-t border-white/10 !my-3', collapsed ? 'w-6' : 'w-full')} />
            <NavSection label="nav.sectionIntelligence" items={intelligenceSection} role={role} onClose={onClose} collapsed={collapsed} />
          </>
        )}

        {/* Admin flyout */}
        {hasAdmin && (
          <>
            <div className={cn('border-t border-white/10 !my-3', collapsed ? 'w-6' : 'w-full')} />
            <SectionLabel label="nav.sectionAdmin" collapsed={collapsed} />
            <FlyoutMenu
              groups={adminGroups}
              userRole={role}
              onClose={onClose}
              collapsed={collapsed}
              triggerIcon={Cog6ToothIcon}
              triggerLabel="nav.administration"
            />
          </>
        )}

        {/* Super Admin — show items directly (no flyout needed, it's their only section) */}
        {hasSuperAdmin && filteredSuperAdmin.length > 0 && (
          <>
            <div className={cn('border-t border-white/10 !my-3', collapsed ? 'w-6' : 'w-full')} />
            <SectionLabel label="nav.sectionSuperAdmin" collapsed={collapsed} />
            {filteredSuperAdmin.map((item) => (
              <NavItemLink key={item.name} item={item} onClose={onClose} collapsed={collapsed} />
            ))}
          </>
        )}
      </nav>

      {/* User Avatar (bottom) */}
      <div className={cn(
        'border-t border-white/10 py-4',
        collapsed ? 'flex flex-col items-center' : 'px-3'
      )}>
        {user && (
          <div className={cn(
            'relative group',
            collapsed ? 'flex justify-center' : ''
          )}>
            <div className={cn(
              'flex items-center gap-3 rounded-lg transition-all cursor-pointer',
              collapsed
                ? 'justify-center'
                : 'p-2 hover:bg-white/10 w-full'
            )}>
              <div className="h-9 w-9 shrink-0 rounded-full bg-primary-600 flex items-center justify-center hover:ring-2 hover:ring-primary-400 transition-all">
                <span className="text-sm font-semibold text-white">
                  {user.username.charAt(0).toUpperCase()}
                </span>
              </div>
              {!collapsed && (
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">
                    {user.full_name || user.username}
                  </p>
                  <p className="text-xs text-gray-400 truncate">{t(`roles.${user.role}`)}</p>
                  {user.tenant_name && (
                    <p className="text-xs font-semibold text-primary-400 truncate">{user.tenant_name}</p>
                  )}
                </div>
              )}
            </div>

            {collapsed && (
              <div className="absolute left-full ml-2 top-1/2 -translate-y-1/2 z-50 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                <div className="bg-gray-900 text-white text-xs font-medium px-2.5 py-1.5 rounded-md whitespace-nowrap shadow-lg">
                  {user.full_name || user.username}
                  <span className="text-gray-400 ml-1">({t(`roles.${user.role}`)})</span>
                  {user.tenant_name && (
                    <span className="text-primary-400 ml-1">&middot; {user.tenant_name}</span>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )

  return (
    <>
      {/* Mobile sidebar overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/40 z-40 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Mobile sidebar */}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 transform transition-transform duration-300 ease-in-out lg:hidden',
          open ? 'translate-x-0' : '-translate-x-full'
        )}
        role="dialog"
        aria-modal="true"
        aria-label="Mobile navigation"
      >
        <button
          className="absolute right-2 top-2 p-2 text-gray-400 hover:text-white"
          onClick={onClose}
          aria-label={t('nav.closeSidebar')}
        >
          <XMarkIcon className="h-5 w-5" aria-hidden="true" />
        </button>
        {sidebarContent}
      </div>

      {/* Desktop sidebar */}
      <div
        className={cn(
          'hidden lg:fixed lg:inset-y-0 lg:flex lg:flex-col transition-all duration-200',
          collapsed ? 'lg:w-[60px]' : 'lg:w-[220px]'
        )}
        role="navigation"
        aria-label="Main navigation"
      >
        {sidebarContent}
      </div>
    </>
  )
}

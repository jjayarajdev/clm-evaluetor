import { useState } from 'react'
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
  ChevronDownIcon,
  GlobeAltIcon,
  AdjustmentsHorizontalIcon,
  UserGroupIcon,
  BuildingLibraryIcon,
  LinkIcon,
  ClipboardDocumentListIcon,
  ShieldCheckIcon,
  BeakerIcon,
  FolderIcon,
} from '@heroicons/react/24/outline'
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

const mainNav: NavItem[] = [
  { name: 'Dashboard', href: '/dashboard', icon: HomeIcon, roles: ['admin', 'legal', 'procurement', 'bu_head'] },
  { name: 'Contracts', href: '/contracts', icon: DocumentTextIcon, roles: ['admin', 'legal', 'procurement', 'bu_head'] },
  { name: 'Compliance', href: '/compliance', icon: ClipboardDocumentCheckIcon, roles: ['admin', 'legal', 'procurement', 'bu_head'] },
  { name: 'Renewals', href: '/renewals', icon: CalendarDaysIcon, roles: ['admin', 'legal', 'procurement', 'bu_head'] },
  { name: 'Vendors', href: '/vendors', icon: BuildingOffice2Icon, roles: ['admin', 'procurement', 'bu_head'] },
  { name: 'Reports', href: '/reports', icon: DocumentChartBarIcon, roles: ['admin', 'legal', 'bu_head'] },
  { name: 'Upload', href: '/upload', icon: CloudArrowUpIcon, roles: ['admin', 'legal', 'procurement'] },
  { name: 'Ask AI', href: '/query', icon: ChatBubbleLeftRightIcon, roles: ['admin', 'legal', 'procurement'] },
]

const governanceNav: NavGroup = {
  label: 'Governance',
  collapsible: true,
  items: [
    { name: 'Organizations', href: '/organizations', icon: BuildingLibraryIcon, roles: ['admin', 'legal', 'procurement'] },
    { name: 'Relationships', href: '/relationships', icon: LinkIcon, roles: ['admin', 'legal', 'procurement'] },
    { name: 'KPI Approvals', href: '/kpi-approvals', icon: ShieldCheckIcon, roles: ['admin'] },
    { name: 'Surveys', href: '/surveys', icon: ClipboardDocumentListIcon, roles: ['admin', 'legal'] },
  ],
}

const adminGroups: NavGroup[] = [
  {
    label: 'Users & Access',
    collapsible: true,
    items: [
      { name: 'Users', href: '/users', icon: UsersIcon, roles: ['admin'] },
      { name: 'Business Units', href: '/admin/business-units', icon: BuildingOffice2Icon, roles: ['admin'] },
      { name: 'External Users', href: '/admin/external-users', icon: UserGroupIcon, roles: ['admin'] },
    ],
  },
  {
    label: 'Integrations',
    collapsible: true,
    items: [
      { name: 'ServiceNow', href: '/admin/integrations/servicenow', icon: CloudArrowUpIcon, roles: ['admin'] },
      { name: 'SharePoint', href: '/admin/integrations/sharepoint', icon: FolderIcon, roles: ['admin'] },
      { name: 'SSO (OIDC)', href: '/admin/sso', icon: ShieldCheckIcon, roles: ['admin'] },
    ],
  },
  {
    label: 'System',
    collapsible: true,
    items: [
      { name: 'Extraction Quality', href: '/admin/extraction-quality', icon: BeakerIcon, roles: ['admin'] },
      { name: 'Master Data', href: '/admin/master-data', icon: CircleStackIcon, roles: ['admin'] },
      { name: 'Scheduler', href: '/admin/scheduler', icon: ClockIcon, roles: ['admin'] },
      { name: 'Settings', href: '/settings', icon: Cog6ToothIcon, roles: ['admin'] },
    ],
  },
]

const superAdminNav: NavItem[] = [
  { name: 'Platform Overview', href: '/super-admin', icon: GlobeAltIcon, roles: ['super_admin'] },
  { name: 'Tenants', href: '/super-admin/tenants', icon: BuildingOffice2Icon, roles: ['super_admin'] },
  { name: 'All Users', href: '/super-admin/users', icon: UserGroupIcon, roles: ['super_admin'] },
  { name: 'Extraction Quality', href: '/admin/extraction-quality', icon: BeakerIcon, roles: ['super_admin'] },
  { name: 'Custom Fields', href: '/super-admin/custom-fields', icon: AdjustmentsHorizontalIcon, roles: ['super_admin'] },
  { name: 'Integrations', href: '/super-admin/integrations', icon: CloudArrowUpIcon, roles: ['super_admin'] },
]

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

  return (
    <div className="relative">
      <NavLink
        to={item.href}
        onClick={onClose}
        onMouseEnter={() => collapsed && setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        aria-label={item.name}
        title={item.name}
        className={({ isActive }) =>
          cn(
            'flex items-center gap-3 rounded-lg transition-all duration-150',
            collapsed
              ? 'justify-center w-10 h-10'
              : indent
                ? 'pl-7 pr-3 py-2'
                : 'px-3 py-2.5',
            isActive
              ? 'bg-primary-100 text-primary-700'
              : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'
          )
        }
      >
        {({ isActive }) => (
          <>
            <item.icon
              className={cn(
                indent ? 'h-4 w-4' : 'h-5 w-5',
                'shrink-0',
                isActive ? 'text-primary-600' : ''
              )}
              aria-hidden="true"
            />
            {!collapsed && (
              <span className={cn('font-medium truncate', indent ? 'text-xs' : 'text-sm')}>{item.name}</span>
            )}
          </>
        )}
      </NavLink>

      {collapsed && showTooltip && (
        <div className="absolute left-full ml-2 top-1/2 -translate-y-1/2 z-50" role="tooltip">
          <div className="bg-gray-900 text-white text-xs font-medium px-2.5 py-1.5 rounded-md whitespace-nowrap shadow-lg">
            {item.name}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Collapsible Group Component ───────────────────────────────────

function CollapsibleGroup({
  group,
  userRole,
  onClose,
  collapsed,
}: {
  group: NavGroup
  userRole: string
  onClose: () => void
  collapsed: boolean
}) {
  const location = useLocation()
  const items = group.items.filter((item) => item.roles.includes(userRole))
  const hasActiveChild = items.some((item) => location.pathname.startsWith(item.href))
  const [isOpen, setIsOpen] = useState(hasActiveChild)

  if (items.length === 0) return null

  // When sidebar is collapsed, show only the first item's icon as a representative
  if (collapsed) {
    return (
      <>
        {items.map((item) => (
          <NavItemLink key={item.name} item={item} onClose={onClose} collapsed={collapsed} />
        ))}
      </>
    )
  }

  return (
    <div>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'w-full flex items-center justify-between px-3 py-1.5 rounded-md text-[10px] font-semibold uppercase tracking-wider transition-colors',
          hasActiveChild
            ? 'text-primary-600'
            : 'text-gray-400 hover:text-gray-600'
        )}
      >
        {group.label}
        <ChevronDownIcon
          className={cn(
            'h-3 w-3 transition-transform duration-200',
            isOpen ? '' : '-rotate-90'
          )}
        />
      </button>
      {isOpen && (
        <div className="mt-0.5 space-y-0.5">
          {items.map((item) => (
            <NavItemLink key={item.name} item={item} onClose={onClose} collapsed={collapsed} indent />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main Sidebar ──────────────────────────────────────────────────

export default function Sidebar({ open, onClose }: SidebarProps) {
  const { user } = useAuth()
  const { collapsed, toggleCollapsed } = useSidebar()

  const role = user?.role || ''

  const filteredMain = mainNav.filter((item) => item.roles.includes(role))
  const filteredGov = governanceNav.items.filter((item) => item.roles.includes(role))
  const filteredSuperAdmin = superAdminNav.filter((item) => item.roles.includes(role))
  const hasAdmin = role === 'admin'
  const hasSuperAdmin = role === 'super_admin'

  const sidebarWidth = collapsed ? 'w-[60px]' : 'w-[220px]'

  const sidebarContent = (
    <div className={cn(
      'flex h-full flex-col bg-white border-r border-gray-200 transition-all duration-200',
      sidebarWidth
    )}>
      {/* Logo & Toggle */}
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-gray-200 px-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="h-8 w-8 shrink-0 rounded-lg bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center">
            <span className="text-white font-bold text-sm">E</span>
          </div>
          {!collapsed && (
            <span className="text-base font-semibold text-gray-900 truncate">
              Evaluetor
            </span>
          )}
        </div>
        <button
          onClick={toggleCollapsed}
          className={cn(
            'p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors',
            collapsed && 'absolute -right-3 top-4 bg-white border border-gray-200 shadow-sm z-10'
          )}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <ChevronRightIcon className="h-4 w-4" aria-hidden="true" />
          ) : (
            <ChevronLeftIcon className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
      </div>

      {/* Main Navigation */}
      <nav
        className={cn(
          'flex-1 flex flex-col py-4 overflow-y-auto',
          collapsed ? 'items-center space-y-1' : 'px-3 space-y-0.5'
        )}
        aria-label="Main navigation"
      >
        {/* Core nav */}
        {filteredMain.map((item) => (
          <NavItemLink key={item.name} item={item} onClose={onClose} collapsed={collapsed} />
        ))}

        {/* Governance group */}
        {filteredGov.length > 0 && (
          <>
            <div className={cn('border-t border-gray-200 !my-3', collapsed ? 'w-6' : 'w-full')} />
            <CollapsibleGroup group={governanceNav} userRole={role} onClose={onClose} collapsed={collapsed} />
          </>
        )}

        {/* Admin groups */}
        {hasAdmin && (
          <>
            <div className={cn('border-t border-gray-200 !my-3', collapsed ? 'w-6' : 'w-full')} />
            {!collapsed && (
              <p className="px-3 mb-1 text-[10px] font-bold text-gray-300 uppercase tracking-wider">Admin</p>
            )}
            {adminGroups.map((group) => (
              <CollapsibleGroup key={group.label} group={group} userRole={role} onClose={onClose} collapsed={collapsed} />
            ))}
          </>
        )}

        {/* Super Admin */}
        {hasSuperAdmin && filteredSuperAdmin.length > 0 && (
          <>
            <div className={cn('border-t border-gray-200 !my-3', collapsed ? 'w-6' : 'w-full')} />
            {!collapsed && (
              <p className="px-3 mb-2 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                Super Admin
              </p>
            )}
            {filteredSuperAdmin.map((item) => (
              <NavItemLink key={item.name} item={item} onClose={onClose} collapsed={collapsed} />
            ))}
          </>
        )}
      </nav>

      {/* User Avatar (bottom) */}
      <div className={cn(
        'border-t border-gray-200 py-4',
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
                : 'p-2 hover:bg-gray-50 w-full'
            )}>
              <div className="h-9 w-9 shrink-0 rounded-full bg-gradient-to-br from-primary-100 to-primary-200 flex items-center justify-center hover:ring-2 hover:ring-primary-300 transition-all">
                <span className="text-sm font-semibold text-primary-700">
                  {user.username.charAt(0).toUpperCase()}
                </span>
              </div>
              {!collapsed && (
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {user.full_name || user.username}
                  </p>
                  <p className="text-xs text-gray-500 capitalize truncate">{user.role}</p>
                </div>
              )}
            </div>

            {collapsed && (
              <div className="absolute left-full ml-2 top-1/2 -translate-y-1/2 z-50 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                <div className="bg-gray-900 text-white text-xs font-medium px-2.5 py-1.5 rounded-md whitespace-nowrap shadow-lg">
                  {user.full_name || user.username}
                  <span className="text-gray-400 ml-1">({user.role})</span>
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
          className="fixed inset-0 bg-black/20 z-40 lg:hidden"
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
          className="absolute right-2 top-2 p-2 text-gray-500 hover:text-gray-700"
          onClick={onClose}
          aria-label="Close sidebar"
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

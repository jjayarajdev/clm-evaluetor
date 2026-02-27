import { useState } from 'react'
import { NavLink } from 'react-router-dom'
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
  FlagIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  GlobeAltIcon,
  AdjustmentsHorizontalIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline'
import { useAuth } from '@/contexts/AuthContext'
import { useSidebar } from '@/contexts/SidebarContext'
import { cn } from '@/lib/utils'

interface SidebarProps {
  open: boolean
  onClose: () => void
}

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: HomeIcon, roles: ['admin', 'legal', 'procurement'] },
  { name: 'Contracts', href: '/contracts', icon: DocumentTextIcon, roles: ['admin', 'legal', 'procurement'] },
  { name: 'Compliance', href: '/compliance', icon: ClipboardDocumentCheckIcon, roles: ['admin', 'legal', 'procurement'] },
  { name: 'Renewals', href: '/renewals', icon: CalendarDaysIcon, roles: ['admin', 'legal', 'procurement'] },
  { name: 'Vendors', href: '/vendors', icon: BuildingOffice2Icon, roles: ['admin', 'procurement'] },
  { name: 'Reports', href: '/reports', icon: DocumentChartBarIcon, roles: ['admin', 'legal'] },
  { name: 'Upload', href: '/upload', icon: CloudArrowUpIcon, roles: ['admin', 'legal', 'procurement'] },
  { name: 'Ask AI', href: '/query', icon: ChatBubbleLeftRightIcon, roles: ['admin', 'legal', 'procurement'] },
]

const bottomNavigation = [
  { name: 'Users', href: '/users', icon: UsersIcon, roles: ['admin'] },
  { name: 'Settings', href: '/settings', icon: Cog6ToothIcon, roles: ['admin'] },
]

const adminNavigation = [
  { name: 'SLA Config', href: '/admin/sla-config', icon: CircleStackIcon, roles: ['admin'] },
  { name: 'Milestones', href: '/admin/milestone-config', icon: FlagIcon, roles: ['admin'] },
  { name: 'Scheduler', href: '/admin/scheduler', icon: ClockIcon, roles: ['admin'] },
]

const superAdminNavigation = [
  { name: 'Platform Overview', href: '/super-admin', icon: GlobeAltIcon, roles: ['super_admin'] },
  { name: 'Tenants', href: '/super-admin/tenants', icon: BuildingOffice2Icon, roles: ['super_admin'] },
  { name: 'All Users', href: '/super-admin/users', icon: UserGroupIcon, roles: ['super_admin'] },
  { name: 'Custom Fields', href: '/super-admin/custom-fields', icon: AdjustmentsHorizontalIcon, roles: ['super_admin'] },
]

function NavItem({
  item,
  onClose,
  collapsed
}: {
  item: typeof navigation[0]
  onClose: () => void
  collapsed: boolean
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
              : 'px-3 py-2.5',
            isActive
              ? 'bg-violet-100 text-violet-700'
              : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'
          )
        }
      >
        {({ isActive }) => (
          <>
            <item.icon
              className={cn(
                'h-5 w-5 shrink-0',
                isActive ? 'text-violet-600' : ''
              )}
              aria-hidden="true"
            />
            {!collapsed && (
              <span className="text-sm font-medium truncate">{item.name}</span>
            )}
          </>
        )}
      </NavLink>

      {/* Tooltip - only shown when collapsed */}
      {collapsed && showTooltip && (
        <div
          className="absolute left-full ml-2 top-1/2 -translate-y-1/2 z-50"
          role="tooltip"
        >
          <div className="bg-gray-900 text-white text-xs font-medium px-2.5 py-1.5 rounded-md whitespace-nowrap shadow-lg">
            {item.name}
          </div>
        </div>
      )}
    </div>
  )
}

export default function Sidebar({ open, onClose }: SidebarProps) {
  const { user } = useAuth()
  const { collapsed, toggleCollapsed } = useSidebar()

  const filteredNavigation = navigation.filter(
    (item) => user && item.roles.includes(user.role)
  )

  const filteredBottomNavigation = bottomNavigation.filter(
    (item) => user && item.roles.includes(user.role)
  )

  const filteredAdminNavigation = adminNavigation.filter(
    (item) => user && item.roles.includes(user.role)
  )

  const filteredSuperAdminNavigation = superAdminNavigation.filter(
    (item) => user && item.roles.includes(user.role)
  )

  const sidebarWidth = collapsed ? 'w-[60px]' : 'w-[220px]'

  const sidebarContent = (
    <div className={cn(
      'flex h-full flex-col bg-white border-r border-gray-200 transition-all duration-200',
      sidebarWidth
    )}>
      {/* Logo & Toggle */}
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-gray-200 px-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="h-8 w-8 shrink-0 rounded-lg bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center">
            <span className="text-white font-bold text-sm">E</span>
          </div>
          {!collapsed && (
            <span className="text-base font-semibold text-gray-900 truncate">
              Evaluetor
            </span>
          )}
        </div>

        {/* Toggle button */}
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
          collapsed ? 'items-center space-y-1' : 'px-3 space-y-1'
        )}
        aria-label="Main navigation"
      >
        {filteredNavigation.map((item) => (
          <NavItem key={item.name} item={item} onClose={onClose} collapsed={collapsed} />
        ))}

        {/* Divider for admin section */}
        {filteredAdminNavigation.length > 0 && (
          <>
            <div className={cn(
              'border-t border-gray-200 my-3',
              collapsed ? 'w-6' : 'w-full'
            )} />

            {!collapsed && (
              <p className="px-3 mb-2 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                Admin
              </p>
            )}

            {filteredAdminNavigation.map((item) => (
              <NavItem key={item.name} item={item} onClose={onClose} collapsed={collapsed} />
            ))}
          </>
        )}

        {/* Divider for super admin section */}
        {filteredSuperAdminNavigation.length > 0 && (
          <>
            <div className={cn(
              'border-t border-gray-200 my-3',
              collapsed ? 'w-6' : 'w-full'
            )} />

            {!collapsed && (
              <p className="px-3 mb-2 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                Super Admin
              </p>
            )}

            {filteredSuperAdminNavigation.map((item) => (
              <NavItem key={item.name} item={item} onClose={onClose} collapsed={collapsed} />
            ))}
          </>
        )}
      </nav>

      {/* Bottom Navigation */}
      <div className={cn(
        'border-t border-gray-200 py-4',
        collapsed ? 'flex flex-col items-center space-y-1' : 'px-3 space-y-1'
      )}>
        {filteredBottomNavigation.map((item) => (
          <NavItem key={item.name} item={item} onClose={onClose} collapsed={collapsed} />
        ))}

        {/* User Avatar */}
        {user && (
          <div className={cn(
            'mt-3 relative group',
            collapsed ? 'flex justify-center' : 'px-0'
          )}>
            <div className={cn(
              'flex items-center gap-3 rounded-lg transition-all cursor-pointer',
              collapsed
                ? 'justify-center'
                : 'p-2 hover:bg-gray-50 w-full'
            )}>
              <div className="h-9 w-9 shrink-0 rounded-full bg-gradient-to-br from-violet-100 to-violet-200 flex items-center justify-center hover:ring-2 hover:ring-violet-300 transition-all">
                <span className="text-sm font-semibold text-violet-700">
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

            {/* User tooltip - only when collapsed */}
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

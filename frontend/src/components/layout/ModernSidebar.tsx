/**
 * Modern Sidebar Navigation
 * Role-based theming, collapsible, with quick actions
 */
import { NavLink, useLocation } from 'react-router-dom'
import {
  DocumentTextIcon,
  ArrowUpTrayIcon,
  SparklesIcon,
  ChartBarIcon,
  Cog6ToothIcon,
  UserGroupIcon,
  ClockIcon,
  BuildingOfficeIcon,
  ScaleIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  Squares2X2Icon,
  BellIcon,
  MagnifyingGlassIcon,
  FlagIcon,
  CalendarDaysIcon,
} from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'
import { roleThemes, type RoleType } from '@/styles/theme'

interface NavItem {
  name: string
  href: string
  icon: React.ElementType
  badge?: number
  roles?: RoleType[]
}

interface NavGroup {
  title: string
  items: NavItem[]
}

const navigation: NavGroup[] = [
  {
    title: 'Main',
    items: [
      { name: 'Dashboard', href: '/dashboard', icon: Squares2X2Icon },
      { name: 'Contracts', href: '/contracts', icon: DocumentTextIcon },
      { name: 'Upload', href: '/upload', icon: ArrowUpTrayIcon },
      { name: 'Ask AI', href: '/query', icon: SparklesIcon },
    ],
  },
  {
    title: 'Management',
    items: [
      { name: 'Compliance', href: '/compliance', icon: ScaleIcon },
      { name: 'Renewals', href: '/renewals', icon: CalendarDaysIcon },
      { name: 'Vendors', href: '/vendors', icon: BuildingOfficeIcon },
      { name: 'Reports', href: '/reports', icon: ChartBarIcon },
    ],
  },
  {
    title: 'Admin',
    items: [
      { name: 'Users', href: '/users', icon: UserGroupIcon, roles: ['admin'] },
      { name: 'SLA Config', href: '/admin/sla-config', icon: FlagIcon, roles: ['admin'] },
      { name: 'Scheduler', href: '/admin/scheduler', icon: ClockIcon, roles: ['admin'] },
      { name: 'Settings', href: '/settings', icon: Cog6ToothIcon },
    ],
  },
]

interface ModernSidebarProps {
  userRole: RoleType
  userName: string
  userEmail: string
  collapsed?: boolean
  onCollapsedChange?: (collapsed: boolean) => void
  notificationCount?: number
}

export default function ModernSidebar({
  userRole,
  userName,
  userEmail,
  collapsed = false,
  onCollapsedChange,
  notificationCount = 0,
}: ModernSidebarProps) {
  const location = useLocation()
  const theme = roleThemes[userRole]

  const filteredNavigation = navigation.map((group) => ({
    ...group,
    items: group.items.filter((item) =>
      !item.roles || item.roles.includes(userRole)
    ),
  })).filter((group) => group.items.length > 0)

  const initials = userName
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  return (
    <aside
      className={cn(
        'flex flex-col h-screen bg-white border-r border-gray-200',
        'transition-all duration-300 ease-in-out',
        collapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Logo */}
      <div className={cn(
        'flex items-center h-16 px-4 border-b border-gray-100',
        collapsed ? 'justify-center' : 'gap-3'
      )}>
        <div className={cn(
          'flex items-center justify-center rounded-xl',
          'bg-gradient-to-br',
          theme.gradient,
          collapsed ? 'w-9 h-9' : 'w-10 h-10'
        )}>
          <DocumentTextIcon className="w-5 h-5 text-white" />
        </div>
        {!collapsed && (
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-bold text-gray-900 truncate">Evaluetor</h1>
            <p className="text-xs text-gray-500 truncate">{theme.label}</p>
          </div>
        )}
      </div>

      {/* Search (expanded only) */}
      {!collapsed && (
        <div className="px-3 py-3">
          <button
            onClick={() => {
              // Trigger command palette
              const event = new KeyboardEvent('keydown', {
                key: 'k',
                metaKey: true,
                bubbles: true,
              })
              document.dispatchEvent(event)
            }}
            className={cn(
              'w-full flex items-center gap-2 px-3 py-2',
              'text-sm text-gray-500 bg-gray-50 rounded-lg',
              'hover:bg-gray-100 transition-colors',
              'border border-gray-200'
            )}
          >
            <MagnifyingGlassIcon className="w-4 h-4" />
            <span className="flex-1 text-left">Search...</span>
            <kbd className="text-xs bg-white px-1.5 py-0.5 rounded border">⌘K</kbd>
          </button>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-2">
        {filteredNavigation.map((group, groupIdx) => (
          <div key={group.title} className={cn(groupIdx > 0 && 'mt-6')}>
            {!collapsed && (
              <h3 className="px-3 mb-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                {group.title}
              </h3>
            )}
            <ul className="space-y-1">
              {group.items.map((item) => {
                const isActive = location.pathname === item.href ||
                  (item.href !== '/dashboard' && location.pathname.startsWith(item.href))

                return (
                  <li key={item.name}>
                    <NavLink
                      to={item.href}
                      className={cn(
                        'flex items-center gap-3 px-3 py-2.5 rounded-lg',
                        'text-sm font-medium transition-all duration-150',
                        isActive
                          ? cn(
                              'bg-gradient-to-r',
                              theme.lightGradient,
                              'text-gray-900',
                              'shadow-sm'
                            )
                          : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900',
                        collapsed && 'justify-center px-2'
                      )}
                      title={collapsed ? item.name : undefined}
                    >
                      <item.icon className={cn(
                        'flex-shrink-0',
                        isActive ? 'text-gray-900' : 'text-gray-400',
                        collapsed ? 'w-6 h-6' : 'w-5 h-5'
                      )} />
                      {!collapsed && (
                        <>
                          <span className="flex-1">{item.name}</span>
                          {item.badge !== undefined && item.badge > 0 && (
                            <span className="px-2 py-0.5 text-xs font-semibold bg-red-100 text-red-700 rounded-full">
                              {item.badge}
                            </span>
                          )}
                        </>
                      )}
                    </NavLink>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Collapse button */}
      {onCollapsedChange && (
        <div className="px-3 py-2 border-t border-gray-100">
          <button
            onClick={() => onCollapsedChange(!collapsed)}
            className={cn(
              'w-full flex items-center gap-2 px-3 py-2',
              'text-sm text-gray-500 rounded-lg',
              'hover:bg-gray-50 transition-colors',
              collapsed && 'justify-center'
            )}
          >
            {collapsed ? (
              <ChevronRightIcon className="w-5 h-5" />
            ) : (
              <>
                <ChevronLeftIcon className="w-5 h-5" />
                <span>Collapse</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* User section */}
      <div className={cn(
        'border-t border-gray-100 p-3',
        collapsed ? 'flex justify-center' : ''
      )}>
        <div className={cn(
          'flex items-center gap-3',
          collapsed && 'flex-col'
        )}>
          {/* Avatar */}
          <div className={cn(
            'flex items-center justify-center rounded-full',
            'bg-gradient-to-br',
            theme.gradient,
            'text-white font-semibold',
            collapsed ? 'w-9 h-9 text-sm' : 'w-10 h-10'
          )}>
            {initials}
          </div>

          {!collapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">{userName}</p>
              <p className="text-xs text-gray-500 truncate">{userEmail}</p>
            </div>
          )}

          {/* Notification bell */}
          {!collapsed && (
            <button className="relative p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-50">
              <BellIcon className="w-5 h-5" />
              {notificationCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 w-4 h-4 flex items-center justify-center text-[10px] font-bold bg-red-500 text-white rounded-full">
                  {notificationCount > 9 ? '9+' : notificationCount}
                </span>
              )}
            </button>
          )}
        </div>
      </div>
    </aside>
  )
}

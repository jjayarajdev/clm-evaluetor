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
} from '@heroicons/react/24/outline'
import { useAuth } from '@/contexts/AuthContext'
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
  { name: 'Users', href: '/users', icon: UsersIcon, roles: ['admin'] },
  { name: 'Settings', href: '/settings', icon: Cog6ToothIcon, roles: ['admin'] },
]

const adminNavigation = [
  { name: 'SLA Config', href: '/admin/sla-config', icon: CircleStackIcon, roles: ['admin'] },
  { name: 'Milestones', href: '/admin/milestone-config', icon: FlagIcon, roles: ['admin'] },
  { name: 'Scheduler', href: '/admin/scheduler', icon: ClockIcon, roles: ['admin'] },
]

export default function Sidebar({ open, onClose }: SidebarProps) {
  const { user } = useAuth()

  const filteredNavigation = navigation.filter(
    (item) => user && item.roles.includes(user.role)
  )

  const filteredAdminNavigation = adminNavigation.filter(
    (item) => user && item.roles.includes(user.role)
  )

  const sidebarContent = (
    <div className="flex h-full flex-col bg-white border-r border-gray-100">
      {/* Logo - Personio style */}
      <div className="flex h-16 shrink-0 items-center px-5 border-b border-gray-100">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center shadow-sm">
            <DocumentTextIcon className="h-5 w-5 text-white" />
          </div>
          <span className="text-lg font-semibold tracking-tight text-gray-900">Evaluetor</span>
        </div>
      </div>

      {/* Navigation - Personio minimal style */}
      <nav className="flex-1 space-y-0.5 px-3 py-4 overflow-y-auto">
        {filteredNavigation.map((item) => (
          <NavLink
            key={item.name}
            to={item.href}
            onClick={onClose}
            className={({ isActive }) =>
              cn(
                'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150',
                isActive
                  ? 'bg-violet-50 text-violet-700 border-l-2 border-violet-500 -ml-0.5 pl-3.5'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              )
            }
          >
            {({ isActive }) => (
              <>
                <item.icon className={cn(
                  'h-5 w-5 shrink-0 transition-colors',
                  isActive ? 'text-violet-600' : 'text-gray-400 group-hover:text-gray-600'
                )} />
                {item.name}
              </>
            )}
          </NavLink>
        ))}

        {/* Admin Section - Personio style divider */}
        {filteredAdminNavigation.length > 0 && (
          <>
            <div className="mt-6 mb-3 px-3">
              <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest">
                Administration
              </p>
            </div>
            {filteredAdminNavigation.map((item) => (
              <NavLink
                key={item.name}
                to={item.href}
                onClick={onClose}
                className={({ isActive }) =>
                  cn(
                    'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150',
                    isActive
                      ? 'bg-violet-50 text-violet-700 border-l-2 border-violet-500 -ml-0.5 pl-3.5'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <item.icon className={cn(
                      'h-5 w-5 shrink-0 transition-colors',
                      isActive ? 'text-violet-600' : 'text-gray-400 group-hover:text-gray-600'
                    )} />
                    {item.name}
                  </>
                )}
              </NavLink>
            ))}
          </>
        )}
      </nav>

      {/* User info - Personio style */}
      {user && (
        <div className="border-t border-gray-100 p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-gradient-to-br from-violet-100 to-violet-200 flex items-center justify-center ring-2 ring-white shadow-sm">
              <span className="text-sm font-semibold text-violet-700">
                {user.username.charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">
                {user.full_name || user.username}
              </p>
              <p className="text-xs text-gray-500 capitalize">{user.role}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )

  return (
    <>
      {/* Mobile sidebar */}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-64 transform transition-transform duration-300 ease-in-out lg:hidden',
          open ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <button
          className="absolute right-2 top-2 p-2 text-gray-500 hover:text-gray-700 lg:hidden"
          onClick={onClose}
        >
          <XMarkIcon className="h-6 w-6" />
        </button>
        {sidebarContent}
      </div>

      {/* Desktop sidebar */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col">
        {sidebarContent}
      </div>
    </>
  )
}

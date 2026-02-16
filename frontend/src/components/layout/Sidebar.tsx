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

function NavItem({ item, onClose }: { item: typeof navigation[0]; onClose: () => void }) {
  const [showTooltip, setShowTooltip] = useState(false)

  return (
    <div className="relative">
      <NavLink
        to={item.href}
        onClick={onClose}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className={({ isActive }) =>
          cn(
            'flex items-center justify-center w-10 h-10 rounded-lg transition-all duration-150',
            isActive
              ? 'bg-violet-100 text-violet-700'
              : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'
          )
        }
      >
        {({ isActive }) => (
          <item.icon className={cn(
            'h-5 w-5',
            isActive ? 'text-violet-600' : ''
          )} />
        )}
      </NavLink>

      {/* Tooltip */}
      {showTooltip && (
        <div className="absolute left-full ml-2 top-1/2 -translate-y-1/2 z-50">
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

  const filteredNavigation = navigation.filter(
    (item) => user && item.roles.includes(user.role)
  )

  const filteredBottomNavigation = bottomNavigation.filter(
    (item) => user && item.roles.includes(user.role)
  )

  const filteredAdminNavigation = adminNavigation.filter(
    (item) => user && item.roles.includes(user.role)
  )

  const sidebarContent = (
    <div className="flex h-full flex-col bg-white border-r border-gray-200 w-[60px]">
      {/* Logo */}
      <div className="flex h-14 shrink-0 items-center justify-center border-b border-gray-200">
        <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center">
          <span className="text-white font-bold text-sm">E</span>
        </div>
      </div>

      {/* Main Navigation */}
      <nav className="flex-1 flex flex-col items-center py-4 space-y-1 overflow-y-auto">
        {filteredNavigation.map((item) => (
          <NavItem key={item.name} item={item} onClose={onClose} />
        ))}

        {/* Divider for admin section */}
        {filteredAdminNavigation.length > 0 && (
          <>
            <div className="w-6 border-t border-gray-200 my-3" />
            {filteredAdminNavigation.map((item) => (
              <NavItem key={item.name} item={item} onClose={onClose} />
            ))}
          </>
        )}
      </nav>

      {/* Bottom Navigation */}
      <div className="border-t border-gray-200 py-4 flex flex-col items-center space-y-1">
        {filteredBottomNavigation.map((item) => (
          <NavItem key={item.name} item={item} onClose={onClose} />
        ))}

        {/* User Avatar */}
        {user && (
          <div className="mt-2 relative group">
            <div className="h-9 w-9 rounded-full bg-gradient-to-br from-violet-100 to-violet-200 flex items-center justify-center cursor-pointer hover:ring-2 hover:ring-violet-300 transition-all">
              <span className="text-sm font-semibold text-violet-700">
                {user.username.charAt(0).toUpperCase()}
              </span>
            </div>
            {/* User tooltip */}
            <div className="absolute left-full ml-2 top-1/2 -translate-y-1/2 z-50 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              <div className="bg-gray-900 text-white text-xs font-medium px-2.5 py-1.5 rounded-md whitespace-nowrap shadow-lg">
                {user.full_name || user.username}
                <span className="text-gray-400 ml-1">({user.role})</span>
              </div>
            </div>
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
        />
      )}

      {/* Mobile sidebar */}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 transform transition-transform duration-300 ease-in-out lg:hidden',
          open ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <button
          className="absolute right-2 top-2 p-2 text-gray-500 hover:text-gray-700"
          onClick={onClose}
        >
          <XMarkIcon className="h-5 w-5" />
        </button>
        {sidebarContent}
      </div>

      {/* Desktop sidebar */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-[60px] lg:flex-col">
        {sidebarContent}
      </div>
    </>
  )
}

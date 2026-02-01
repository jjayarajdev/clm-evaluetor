import { Menu, Transition } from '@headlessui/react'
import { Fragment } from 'react'
import {
  Bars3Icon,
  BellIcon,
  ChevronDownIcon,
  ArrowRightOnRectangleIcon,
  UserCircleIcon,
} from '@heroicons/react/24/outline'
import { useAuth } from '@/contexts/AuthContext'
import { cn } from '@/lib/utils'

interface HeaderProps {
  onMenuClick: () => void
}

export default function Header({ onMenuClick }: HeaderProps) {
  const { user, logout } = useAuth()

  return (
    <header className="sticky top-0 z-30 bg-white border-b border-gray-200">
      <div className="flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Mobile menu button */}
        <button
          type="button"
          className="lg:hidden -m-2.5 p-2.5 text-gray-700"
          onClick={onMenuClick}
        >
          <span className="sr-only">Open sidebar</span>
          <Bars3Icon className="h-6 w-6" />
        </button>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Right section */}
        <div className="flex items-center gap-4">
          {/* Notifications */}
          <button
            type="button"
            className="p-2 text-gray-500 hover:text-gray-700 relative"
          >
            <span className="sr-only">View notifications</span>
            <BellIcon className="h-6 w-6" />
            {/* Notification badge */}
            <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-red-500" />
          </button>

          {/* User menu */}
          <Menu as="div" className="relative">
            <Menu.Button className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-gray-50">
              <div className="h-8 w-8 rounded-full bg-primary-100 flex items-center justify-center">
                <span className="text-sm font-medium text-primary-700">
                  {user?.username.charAt(0).toUpperCase()}
                </span>
              </div>
              <span className="hidden sm:block text-gray-700 font-medium">
                {user?.full_name || user?.username}
              </span>
              <ChevronDownIcon className="h-4 w-4 text-gray-500" />
            </Menu.Button>

            <Transition
              as={Fragment}
              enter="transition ease-out duration-100"
              enterFrom="transform opacity-0 scale-95"
              enterTo="transform opacity-100 scale-100"
              leave="transition ease-in duration-75"
              leaveFrom="transform opacity-100 scale-100"
              leaveTo="transform opacity-0 scale-95"
            >
              <Menu.Items className="absolute right-0 z-10 mt-2 w-48 origin-top-right rounded-lg bg-white py-1 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                <div className="px-4 py-2 border-b border-gray-100">
                  <p className="text-sm font-medium text-gray-900">
                    {user?.full_name || user?.username}
                  </p>
                  <p className="text-xs text-gray-500">{user?.email}</p>
                </div>

                <Menu.Item>
                  {({ active }) => (
                    <a
                      href="/settings"
                      className={cn(
                        'flex items-center gap-2 px-4 py-2 text-sm',
                        active ? 'bg-gray-50 text-gray-900' : 'text-gray-700'
                      )}
                    >
                      <UserCircleIcon className="h-4 w-4" />
                      Profile
                    </a>
                  )}
                </Menu.Item>

                <Menu.Item>
                  {({ active }) => (
                    <button
                      onClick={logout}
                      className={cn(
                        'flex w-full items-center gap-2 px-4 py-2 text-sm',
                        active ? 'bg-gray-50 text-gray-900' : 'text-gray-700'
                      )}
                    >
                      <ArrowRightOnRectangleIcon className="h-4 w-4" />
                      Sign out
                    </button>
                  )}
                </Menu.Item>
              </Menu.Items>
            </Transition>
          </Menu>
        </div>
      </div>
    </header>
  )
}

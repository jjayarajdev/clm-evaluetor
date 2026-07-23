import { Menu, Transition } from '@headlessui/react'
import { Fragment } from 'react'
import {
  Bars3Icon,
  BellIcon,
  ChevronDownIcon,
  ArrowRightOnRectangleIcon,
  LanguageIcon,
  UserCircleIcon,
} from '@heroicons/react/24/outline'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/contexts/AuthContext'
import { setAppLanguage, type AppLanguage } from '@/i18n'
import api from '@/lib/api'
import { cn } from '@/lib/utils'

interface HeaderProps {
  onMenuClick: () => void
}

const LANGUAGES: { code: AppLanguage; labelKey: string }[] = [
  { code: 'en', labelKey: 'common.english' },
  { code: 'fr', labelKey: 'common.french' },
]

export default function Header({ onMenuClick }: HeaderProps) {
  const { user, logout } = useAuth()
  const { t, i18n } = useTranslation()

  const changeLanguage = async (code: AppLanguage) => {
    setAppLanguage(code)
    if (user) {
      try {
        await api.updateMyPreferences(code)
      } catch {
        // Preference persists locally even if the API call fails
      }
    }
  }

  return (
    <header className="sticky top-0 z-30 bg-white border-b border-gray-200">
      <div className="flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Mobile menu button */}
        <button
          type="button"
          className="lg:hidden -m-2.5 p-2.5 text-gray-700"
          onClick={onMenuClick}
        >
          <span className="sr-only">{t('nav.openSidebar')}</span>
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
            <span className="sr-only">{t('nav.viewNotifications')}</span>
            <BellIcon className="h-6 w-6" />
            {/* Notification badge */}
            <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-red-500" />
          </button>

          {/* Language switcher */}
          <Menu as="div" className="relative">
            <Menu.Button className="flex items-center gap-1.5 rounded-lg px-2 py-2 text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-50">
              <span className="sr-only">{t('common.language')}</span>
              <LanguageIcon className="h-5 w-5" />
              <span className="text-xs font-semibold uppercase">{i18n.language}</span>
              <ChevronDownIcon className="h-3 w-3 text-gray-400" />
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
              <Menu.Items className="absolute right-0 z-10 mt-2 w-36 origin-top-right rounded-lg bg-white py-1 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                {LANGUAGES.map(({ code, labelKey }) => (
                  <Menu.Item key={code}>
                    {({ active }) => (
                      <button
                        onClick={() => changeLanguage(code)}
                        className={cn(
                          'flex w-full items-center justify-between px-4 py-2 text-sm',
                          active ? 'bg-gray-50 text-gray-900' : 'text-gray-700',
                          i18n.language === code && 'font-semibold text-primary-700'
                        )}
                      >
                        {t(labelKey)}
                        {i18n.language === code && <span aria-hidden>✓</span>}
                      </button>
                    )}
                  </Menu.Item>
                ))}
              </Menu.Items>
            </Transition>
          </Menu>

          {/* User menu */}
          <Menu as="div" className="relative">
            <Menu.Button className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm hover:bg-gray-50">
              <div className="hidden sm:block text-right">
                <span className="block text-sm font-semibold text-gray-900">
                  {user?.full_name || user?.username}
                </span>
                <span className="block text-xs text-gray-500">
                  <span className={cn(
                    'inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide mr-1',
                    user?.role === 'super_admin' ? 'bg-pink-100 text-pink-700' :
                    user?.role === 'legal' ? 'bg-blue-100 text-blue-700' :
                    user?.role === 'admin' ? 'bg-primary-100 text-primary-700' :
                    'bg-gray-100 text-gray-600'
                  )}>
                    {user?.role ? t(`roles.${user.role}`) : ''}
                  </span>
                  {user?.tenant_name || t('nav.system')}
                </span>
              </div>
              <div className="h-9 w-9 rounded-full bg-primary-100 flex items-center justify-center">
                <span className="text-sm font-semibold text-primary-700">
                  {user?.username.charAt(0).toUpperCase()}
                </span>
              </div>
              <ChevronDownIcon className="h-4 w-4 text-gray-400" />
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
                  <p className="text-xs font-medium text-primary-600 capitalize mt-0.5">
                    {user?.role ? t(`roles.${user.role}`) : ''} &middot; {user?.tenant_name || t('nav.system')}
                  </p>
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
                      {t('nav.profile')}
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
                      {t('nav.signOut')}
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

import { Component, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline'

function ErrorFallback({ onReset }: { onReset: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="min-h-[50vh] flex items-center justify-center p-6">
      <div className="max-w-md text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
          <ExclamationTriangleIcon className="h-6 w-6 text-red-600" />
        </div>
        <h2 className="text-lg font-semibold text-gray-900">{t('error.title')}</h2>
        <p className="mt-2 text-sm text-gray-500">{t('error.body')}</p>
        <div className="mt-6 flex items-center justify-center gap-3">
          <button
            onClick={onReset}
            className="px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 transition-colors"
          >
            {t('error.retry')}
          </button>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            {t('error.reload')}
          </button>
        </div>
      </div>
    </div>
  )
}

interface Props {
  children: ReactNode
  // When this value changes (e.g. the route path), a previously-caught error is
  // cleared so navigating away from a broken page recovers automatically.
  resetKey?: unknown
}

interface State {
  hasError: boolean
}

/**
 * Contains render/runtime errors in the subtree so a single bad component
 * (e.g. a null field hitting .toFixed) shows a recoverable message instead of a
 * blank white screen.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: unknown, info: unknown) {
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary]', error, info)
  }

  componentDidUpdate(prevProps: Props) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false })
    }
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback onReset={() => this.setState({ hasError: false })} />
    }
    return this.props.children
  }
}

/**
 * React ErrorBoundary — catches render-time exceptions that would
 * otherwise white-screen the entire app.
 *
 * Shows the error message and a "Reload" button.
 * Wrap around <App/> in main.tsx.
 */
import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Log to console so it's visible in dev tools
    console.error('[ErrorBoundary] Uncaught render error:', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-ink-900 p-6">
          <div className="glass-overlay w-full max-w-md rounded-[28px] p-8 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-status-failed/[0.12]">
              <svg
                className="h-6 w-6 text-status-failed"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                />
              </svg>
            </div>
            <h1 className="font-display text-lg font-bold tracking-[-.02em] text-lilac-50">
              Something went wrong
            </h1>
            <p className="mt-2 text-sm text-lilac-50/62">
              An unexpected error occurred while rendering the page.
            </p>
            {this.state.error && (
              <pre className="mt-4 max-h-40 overflow-auto rounded-xl border border-status-failed/[0.26] bg-status-failed/[0.09] p-3 text-left text-xs text-[#FDA4AF]">
                {this.state.error.message}
              </pre>
            )}
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-6 rounded-pill bg-[linear-gradient(180deg,#AA3BFF,#7E14FF)] px-5 py-2.5 text-sm font-semibold text-white shadow-glow transition hover:brightness-110"
            >
              Reload page
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

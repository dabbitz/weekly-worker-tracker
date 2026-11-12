import { AlertTriangle, RefreshCw } from 'lucide-react'

import { Button } from './Button'

interface ErrorStateProps {
  title?: string
  message: string
  onRetry?: () => void
  compact?: boolean
}

export function ErrorState({
  title = 'Veriler yüklenemedi',
  message,
  onRetry,
  compact = false,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={
        compact
          ? 'flex flex-wrap items-center justify-between gap-3 px-5 py-4'
          : 'flex flex-col items-center px-6 py-12 text-center'
      }
    >
      <div
        className={
          compact
            ? 'flex min-w-0 items-center gap-3'
            : 'flex flex-col items-center'
        }
      >
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-50 text-red-600">
          <AlertTriangle className="h-5 w-5" aria-hidden="true" />
        </div>
        <div className={compact ? 'min-w-0' : 'mt-3'}>
          <h3 className="text-sm font-semibold text-worktrack-ink">
            {title}
          </h3>
          <p className="mt-0.5 text-sm text-slate-500">{message}</p>
        </div>
      </div>
      {onRetry ? (
        <Button
          variant="secondary"
          size="sm"
          onClick={onRetry}
          leftIcon={<RefreshCw className="h-3.5 w-3.5" />}
          className={compact ? '' : 'mt-5'}
        >
          Tekrar dene
        </Button>
      ) : null}
    </div>
  )
}

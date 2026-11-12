import { cn } from '../../lib/utils'

interface LoadingStateProps {
  variant?: 'table' | 'cards' | 'detail'
  rows?: number
}

function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-md bg-slate-200/80',
        className,
      )}
    />
  )
}

export function LoadingState({
  variant = 'table',
  rows = 5,
}: LoadingStateProps) {
  if (variant === 'cards') {
    return (
      <div
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
        aria-busy="true"
        aria-label="Yükleniyor"
      >
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="card p-5">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="mt-4 h-8 w-16" />
            <Skeleton className="mt-3 h-3 w-36" />
          </div>
        ))}
      </div>
    )
  }

  if (variant === 'detail') {
    return (
      <div className="space-y-4" aria-busy="true" aria-label="Yükleniyor">
        <div className="card p-5">
          <Skeleton className="h-5 w-48" />
          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index}>
                <Skeleton className="h-3 w-20" />
                <Skeleton className="mt-2 h-4 w-32" />
              </div>
            ))}
          </div>
        </div>
        <div className="card p-5">
          <Skeleton className="h-5 w-40" />
          <div className="mt-5 space-y-3">
            {Array.from({ length: rows }).map((_, index) => (
              <Skeleton key={index} className="h-10 w-full" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      className="table-shell p-4"
      aria-busy="true"
      aria-label="Yükleniyor"
    >
      <Skeleton className="h-9 w-full" />
      <div className="mt-3 space-y-2">
        {Array.from({ length: rows }).map((_, index) => (
          <Skeleton key={index} className="h-11 w-full" />
        ))}
      </div>
    </div>
  )
}

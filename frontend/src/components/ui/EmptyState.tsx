import type { LucideIcon } from 'lucide-react'
import { Inbox } from 'lucide-react'
import type { ReactNode } from 'react'

interface EmptyStateProps {
  title: string
  description: string
  action?: ReactNode
  icon?: LucideIcon
  compact?: boolean
}

export function EmptyState({
  title,
  description,
  action,
  icon: Icon = Inbox,
  compact = false,
}: EmptyStateProps) {
  return (
    <div
      className={
        compact
          ? 'flex flex-col items-center px-5 py-8 text-center'
          : 'flex flex-col items-center px-6 py-14 text-center'
      }
    >
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <Icon className="h-6 w-6" aria-hidden="true" />
      </div>
      <h3 className="text-base font-semibold text-worktrack-ink">{title}</h3>
      <p className="mt-1 max-w-md text-sm text-slate-500">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  )
}

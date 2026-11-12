import type { ReactNode } from 'react'

import { cn } from '../../lib/utils'

interface CardProps {
  children: ReactNode
  className?: string
}

export function Card({ children, className }: CardProps) {
  return <div className={cn('card', className)}>{children}</div>
}

interface CardHeaderProps {
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function CardHeader({
  title,
  description,
  action,
  className,
}: CardHeaderProps) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-start justify-between gap-3 border-b border-worktrack-line px-5 py-4',
        className,
      )}
    >
      <div className="min-w-0">
        <h2 className="text-base font-semibold text-worktrack-ink">
          {title}
        </h2>
        {description ? (
          <p className="mt-0.5 text-sm text-slate-500">{description}</p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  )
}

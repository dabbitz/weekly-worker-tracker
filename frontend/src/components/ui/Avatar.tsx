import { cn, getInitials } from '../../lib/utils'

interface AvatarProps {
  name: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const sizeClasses = {
  sm: 'h-7 w-7 text-[11px]',
  md: 'h-9 w-9 text-xs',
  lg: 'h-11 w-11 text-sm',
}

export function Avatar({ name, size = 'md', className }: AvatarProps) {
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-full bg-worktrack-navy/10 font-semibold text-worktrack-navy ring-1 ring-worktrack-navy/10',
        sizeClasses[size],
        className,
      )}
      aria-hidden="true"
      title={name}
    >
      {getInitials(name)}
    </span>
  )
}

interface AvatarGroupProps {
  names: string[]
  max?: number
}

export function AvatarGroup({ names, max = 3 }: AvatarGroupProps) {
  if (names.length === 0) {
    return <span className="text-xs text-slate-400">Atanmamış</span>
  }

  const visible = names.slice(0, max)
  const remaining = names.length - visible.length

  return (
    <div className="flex items-center">
      <div className="flex -space-x-2">
        {visible.map((name) => (
          <Avatar
            key={name}
            name={name}
            size="sm"
            className="ring-2 ring-white"
          />
        ))}
      </div>
      {remaining > 0 ? (
        <span className="ml-2 text-xs font-medium text-slate-500">
          +{remaining}
        </span>
      ) : null}
      <span className="sr-only">{names.join(', ')}</span>
    </div>
  )
}

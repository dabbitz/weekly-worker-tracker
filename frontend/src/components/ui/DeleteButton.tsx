import { Loader2, Trash2 } from 'lucide-react'

import { cn } from '../../lib/utils'

interface DeleteButtonProps {
  label: string
  onClick: () => void
  disabled?: boolean
  isDeleting?: boolean
  className?: string
}

/**
 * Compact trash action that matches the existing icon-button rows.
 * The native title acts as the visible "Sil" hint on hover while the
 * aria-label keeps the action accessible for screen readers.
 */
export function DeleteButton({
  label,
  onClick,
  disabled = false,
  isDeleting = false,
  className,
}: DeleteButtonProps) {
  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation()
        onClick()
      }}
      disabled={disabled || isDeleting}
      className={cn(
        'rounded-md p-1.5 text-slate-400 transition hover:bg-red-50 hover:text-red-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500 disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      aria-label={label}
      title={isDeleting ? 'Siliniyor…' : 'Sil'}
    >
      {isDeleting ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      ) : (
        <Trash2 className="h-4 w-4" aria-hidden="true" />
      )}
    </button>
  )
}

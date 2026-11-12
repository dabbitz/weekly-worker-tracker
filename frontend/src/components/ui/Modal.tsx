import { X } from 'lucide-react'
import {
  useEffect,
  useId,
  useRef,
  type ReactNode,
} from 'react'

import { cn } from '../../lib/utils'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  description?: string
  children: ReactNode
  footer?: ReactNode
  size?: 'sm' | 'md' | 'lg'
}

const sizeClasses = {
  sm: 'max-w-md',
  md: 'max-w-xl',
  lg: 'max-w-3xl',
}

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = 'md',
}: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const titleId = useId()

  useEffect(() => {
    const dialog = dialogRef.current

    if (!dialog) {
      return
    }

    if (open && !dialog.open) {
      dialog.showModal()
    } else if (!open && dialog.open) {
      dialog.close()
    }
  }, [open])

  useEffect(() => {
    const dialog = dialogRef.current

    if (!dialog) {
      return
    }

    const handleCancel = (event: Event) => {
      event.preventDefault()
      onClose()
    }

    dialog.addEventListener('cancel', handleCancel)
    return () => dialog.removeEventListener('cancel', handleCancel)
  }, [onClose])

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      className={cn(
        'm-auto w-[calc(100vw-2rem)] rounded-xl border border-slate-200 bg-white p-0 text-left shadow-2xl',
        sizeClasses[size],
      )}
      onClose={onClose}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose()
        }
      }}
    >
      <div className="flex max-h-[85vh] flex-col">
        <header className="flex items-start justify-between gap-4 border-b border-worktrack-line px-6 py-4">
          <div className="min-w-0">
            <h2
              id={titleId}
              className="text-lg font-semibold text-worktrack-ink"
            >
              {title}
            </h2>
            {description ? (
              <p className="mt-0.5 text-sm text-slate-500">
                {description}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
            aria-label="Pencereyi kapat"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </header>
        <div className="overflow-y-auto px-6 py-5">{children}</div>
        {footer ? (
          <footer className="flex flex-wrap justify-end gap-2 border-t border-worktrack-line bg-slate-50/70 px-6 py-3">
            {footer}
          </footer>
        ) : null}
      </div>
    </dialog>
  )
}

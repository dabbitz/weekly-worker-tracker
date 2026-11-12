import { ChevronLeft, ChevronRight } from 'lucide-react'

import { Button } from './Button'

interface PaginationProps {
  page: number
  pages: number
  total: number
  onPageChange: (page: number) => void
  disabled?: boolean
}

export function Pagination({
  page,
  pages,
  total,
  onPageChange,
  disabled = false,
}: PaginationProps) {
  if (total === 0) {
    return null
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-1 py-3">
      <p className="text-sm text-slate-500">
        Toplam <span className="font-medium text-slate-700">{total}</span>{' '}
        kayıt · Sayfa {page} / {Math.max(pages, 1)}
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(page - 1)}
          disabled={disabled || page <= 1}
          leftIcon={<ChevronLeft className="h-4 w-4" />}
        >
          Önceki
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(page + 1)}
          disabled={disabled || page >= pages}
        >
          Sonraki
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

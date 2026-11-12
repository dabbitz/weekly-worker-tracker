import { Search, X } from 'lucide-react'

interface SearchInputProps {
  value: string
  onChange: (value: string) => void
  placeholder: string
  label?: string
  className?: string
}

export function SearchInput({
  value,
  onChange,
  placeholder,
  label = 'Ara',
  className,
}: SearchInputProps) {
  return (
    <div className={className ?? 'relative w-full sm:max-w-xs'}>
      <Search
        className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400"
        aria-hidden="true"
      />
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={label}
        className="field-input pr-9 pl-9"
      />
      {value ? (
        <button
          type="button"
          onClick={() => onChange('')}
          className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
          aria-label="Aramayı temizle"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      ) : null}
    </div>
  )
}

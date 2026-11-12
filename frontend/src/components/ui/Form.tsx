import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react'

import { cn } from '../../lib/utils'

interface FieldProps {
  label: string
  htmlFor: string
  error?: string
  hint?: string
  required?: boolean
  children: ReactNode
  className?: string
}

export function Field({
  label,
  htmlFor,
  error,
  hint,
  required = false,
  children,
  className,
}: FieldProps) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <label
        htmlFor={htmlFor}
        className="block text-sm font-medium text-slate-700"
      >
        {label}
        {required ? (
          <span className="ml-0.5 text-red-600" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>
      {children}
      {error ? (
        <p id={`${htmlFor}-error`} className="text-xs text-red-600">
          {error}
        </p>
      ) : hint ? (
        <p id={`${htmlFor}-hint`} className="text-xs text-slate-500">
          {hint}
        </p>
      ) : null}
    </div>
  )
}

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean
}

export function Input({
  className,
  invalid = false,
  ...props
}: InputProps) {
  return (
    <input
      className={cn(
        'field-input',
        invalid && 'border-red-400 focus:border-red-500',
        className,
      )}
      aria-invalid={invalid || undefined}
      {...props}
    />
  )
}

interface TextareaProps
  extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean
}

export function Textarea({
  className,
  invalid = false,
  rows = 3,
  ...props
}: TextareaProps) {
  return (
    <textarea
      rows={rows}
      className={cn(
        'field-input resize-y',
        invalid && 'border-red-400 focus:border-red-500',
        className,
      )}
      aria-invalid={invalid || undefined}
      {...props}
    />
  )
}

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  invalid?: boolean
}

export function Select({
  className,
  invalid = false,
  children,
  ...props
}: SelectProps) {
  return (
    <select
      className={cn(
        'field-input cursor-pointer appearance-none bg-[length:16px] bg-[right_0.75rem_center] bg-no-repeat pr-10',
        invalid && 'border-red-400 focus:border-red-500',
        className,
      )}
      aria-invalid={invalid || undefined}
      style={{
        backgroundImage:
          "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3E%3Cpath stroke='%2364748b' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.6' d='m6 8 4 4 4-4'/%3E%3C/svg%3E\")",
      }}
      {...props}
    >
      {children}
    </select>
  )
}

interface CheckboxProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string
  description?: string
}

export function Checkbox({
  label,
  description,
  id,
  className,
  ...props
}: CheckboxProps) {
  return (
    <label
      htmlFor={id}
      className={cn(
        'flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 px-3 py-2.5 transition hover:border-slate-300 hover:bg-slate-50/70',
        props.disabled && 'cursor-not-allowed opacity-60 hover:bg-transparent',
        className,
      )}
    >
      <input
        id={id}
        type="checkbox"
        className="mt-0.5 h-4 w-4 rounded border-slate-300 text-worktrack-blue focus:ring-worktrack-blue/30"
        {...props}
      />
      <span className="min-w-0">
        <span className="block text-sm font-medium text-slate-700">
          {label}
        </span>
        {description ? (
          <span className="block text-xs text-slate-500">
            {description}
          </span>
        ) : null}
      </span>
    </label>
  )
}

'use client'

import * as React from 'react'
import { ChevronDown, Check } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SelectContextValue {
  value?: string
  onValueChange?: (value: string) => void
  placeholder?: string
}

const SelectContext = React.createContext<SelectContextValue | null>(null)

export interface SelectProps {
  value?: string
  onValueChange?: (value: string) => void
  placeholder?: string
  children: React.ReactNode
  className?: string
}

export const Select: React.FC<SelectProps> = ({
  value,
  onValueChange,
  placeholder,
  children,
  className,
}) => {
  const [open, setOpen] = React.useState(false)
  const ref = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <SelectContext.Provider value={{ value, onValueChange, placeholder }}>
      <div ref={ref} className={cn('relative', className)} data-open={open}>
        {React.Children.map(children, (child) =>
          React.isValidElement(child)
            ? React.cloneElement(child, { open, setOpen })
            : child
        )}
      </div>
    </SelectContext.Provider>
  )
}

export const SelectTrigger = ({
  children,
  open,
  setOpen,
}: {
  children: React.ReactNode
  open?: boolean
  setOpen?: (v: boolean) => void
}) => (
  <button
    type="button"
    onClick={() => setOpen?.(!open)}
    className={cn(
      'flex w-full items-center justify-between rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 shadow-sm',
      'focus:outline-none focus:ring-2 focus:ring-blue-500'
    )}
  >
    {children}
    <ChevronDown
      className={cn('h-4 w-4 text-gray-500 transition-transform', {
        'rotate-180': open,
      })}
    />
  </button>
)

export const SelectValue = ({ placeholder }: { placeholder?: string }) => {
  const ctx = React.useContext(SelectContext)
  if (!ctx) throw new Error('SelectValue must be used within Select')

  const { value } = ctx
  return (
    <span className={cn(!value && 'text-gray-400')}>
      {value || placeholder || 'Select...'}
    </span>
  )
}

export const SelectContent = ({
  children,
  open,
}: {
  children: React.ReactNode
  open?: boolean
}) => {
  if (!open) return null
  return (
    <ul className="absolute z-50 mt-1 max-h-56 w-full overflow-auto rounded-md border border-gray-200 bg-white shadow-lg">
      {children}
    </ul>
  )
}

export const SelectItem = ({
  value,
  children,
}: {
  value: string
  children: React.ReactNode
}) => {
  const ctx = React.useContext(SelectContext)
  if (!ctx) throw new Error('SelectItem must be used within Select')

  const selected = ctx.value === value
  return (
    <li
      onClick={() => ctx.onValueChange?.(value)}
      className={cn(
        'flex cursor-pointer items-center justify-between px-3 py-2 text-sm text-gray-800 hover:bg-blue-50',
        selected && 'bg-blue-100 text-blue-800'
      )}
    >
      {children}
      {selected && <Check className="h-4 w-4 text-blue-600" />}
    </li>
  )
}

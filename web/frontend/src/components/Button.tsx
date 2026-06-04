import React from 'react'
import { cn } from '../lib/utils'

// Lightweight Button primitive (MagicPatterns shipped this file empty).
// Provided for completeness; not currently consumed by any ported screen.
export function Button({
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-full px-5 py-2.5 text-sm font-medium transition-all min-h-[44px] bg-garage-green text-[#0A0D0B] hover:bg-garage-green-deep',
        className,
      )}
      {...props}
    />
  )
}

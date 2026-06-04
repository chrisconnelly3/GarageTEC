import React from 'react'
import { cn } from '../lib/utils'

// Lightweight Badge primitive (MagicPatterns shipped this file empty).
// Provided for completeness; not currently consumed by any ported screen.
export function Badge({
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full bg-[#1A211D] px-2.5 py-0.5 text-xs font-medium text-[#E7EEE9]',
        className,
      )}
      {...props}
    />
  )
}

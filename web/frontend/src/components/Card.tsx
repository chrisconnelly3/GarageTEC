import React from 'react'
import { cn } from '../lib/utils'

// Lightweight Card primitive (MagicPatterns shipped this file empty).
// Provided for completeness; not currently consumed by any ported screen.
export function Card({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'bg-[#121714] border border-[#242C27] rounded-[18px] p-5',
        className,
      )}
      {...props}
    />
  )
}

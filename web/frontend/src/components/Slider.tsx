import React from 'react'
import { cn } from '../lib/utils'

// Lightweight Slider primitive (MagicPatterns shipped this file empty).
// Provided for completeness; not currently consumed by any ported screen.
export function Slider({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type="range"
      className={cn('w-full accent-garage-green', className)}
      {...props}
    />
  )
}

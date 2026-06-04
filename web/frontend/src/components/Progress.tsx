import { cn } from '../lib/utils'

// Lightweight Progress primitive (MagicPatterns shipped this file empty).
// Provided for completeness; not currently consumed by any ported screen.
interface ProgressProps {
  value?: number
  className?: string
}
export function Progress({ value = 0, className }: ProgressProps) {
  return (
    <div
      className={cn(
        'h-1.5 w-full overflow-hidden rounded-full bg-[#1A211D]',
        className,
      )}
    >
      <div
        className="h-full rounded-full bg-garage-green transition-all"
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  )
}

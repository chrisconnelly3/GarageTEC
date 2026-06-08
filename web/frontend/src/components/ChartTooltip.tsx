import { cn } from '../lib/utils'

/** Datum shape both history charts feed into recharts. `swingId` is present only
 *  on the body-metric chart, where a point maps to a single swing. */
interface PinnedDatum {
  date: string
  value: number
  swingId?: number
}

// Loose props so the recharts `content` callback (which hands over its own
// generically-typed tooltip props) assigns cleanly. We only read active/payload/label.
interface PinnedChartTooltipProps {
  active?: boolean
  payload?: Array<{ payload?: PinnedDatum }>
  label?: string | number
  unit?: string
  decimals?: number
  onOpenSwing?: (id: number) => void
}

/** Tap-to-pin tooltip for the history charts. Paired with `<Tooltip trigger="click">`,
 *  so a finger tap (not a hover, which a touch bay never fires) pins the point's value.
 *  When the point maps to a swing, a full-width button opens it: reading the value and
 *  navigating away are two separate, deliberate actions. */
export function PinnedChartTooltip({
  active, payload, unit = '', decimals = 1, onOpenSwing,
}: PinnedChartTooltipProps) {
  if (!active || !payload?.length) return null
  const datum = payload[0].payload
  if (!datum) return null
  const tightUnit = unit === '°' || unit === '"'
  const swingId = datum.swingId
  return (
    <div
      className="bg-[#1A211D] border border-[#242C27] rounded-xl px-4 py-3 shadow-xl shadow-black/40"
      // recharts gives the tooltip wrapper pointer-events:none; re-enable so the
      // Open-swing button is tappable.
      style={{ pointerEvents: 'auto' }}
    >
      <div className="text-[11px] uppercase tracking-wider text-[#8B978F] mb-1">{datum.date}</div>
      <div className="font-mono font-bold text-[#E7EEE9] leading-none">
        <span className="text-2xl">{datum.value.toFixed(decimals)}</span>
        {unit && (
          <span className={cn('text-[#8B978F] text-base', tightUnit ? '' : 'ml-1')}>
            {unit}
          </span>
        )}
      </div>
      {onOpenSwing && swingId != null && (
        <button
          type="button"
          onClick={() => onOpenSwing(swingId)}
          className="mt-3 w-full min-h-[40px] rounded-lg bg-garage-green/15 text-garage-green text-sm font-semibold px-3 transition-colors active:bg-garage-green/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60"
        >
          Open swing →
        </button>
      )}
    </div>
  )
}

import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import { cn } from '../lib/utils'
import { motion } from 'framer-motion'
import type { MetricZone, MetricState } from '../lib/types'

// Zone reads in-card (full tinted border + faint wash + leading dot) — no side-stripe.
const ZONE_BORDER: Record<MetricZone, string> = {
  green: 'border-garage-green/40',
  yellow: 'border-[#E8B931]/40',
  red: 'border-garage-red/40',
}
const ZONE_WASH: Record<MetricZone, string> = {
  green: 'bg-garage-green/[0.08]',
  yellow: 'bg-[#E8B931]/[0.08]',
  red: 'bg-garage-red/[0.08]',
}
const ZONE_DOT: Record<MetricZone, string> = {
  green: 'bg-garage-green',
  yellow: 'bg-[#E8B931]',
  red: 'bg-garage-red',
}
const ZONE_TEXT: Record<MetricZone, string> = {
  green: 'text-garage-green',
  yellow: 'text-[#E8B931]',
  red: 'text-garage-red',
}

// Only render a known measurement unit as a suffix. A method/confidence string
// (e.g. "foreshortening_2d;confidence=low") must NEVER print next to the value.
const KNOWN_UNITS: Record<string, string> = {
  deg: '°', in: '"', mph: 'mph', rpm: 'rpm', yds: 'yds', rps: 'rps',
}
const unitSuffix = (unit: string) => KNOWN_UNITS[unit] ?? ''

export interface MetricCardTrend { delta: number; towardPro: boolean | null }

export interface MetricCardProps {
  label: string
  value: number | null
  unit: string
  target: number | null
  delta: number | null
  zone: MetricZone | null
  state: MetricState
  trend: MetricCardTrend
  phase?: string          // inline phase badge (body cards)
  offPhase?: string       // when set, card is dimmed: "— measured at <offPhase>"
  isEstimated?: boolean
  highlight?: boolean
}

function fmt(v: number, unit: string) {
  const r = unit === 'rpm' ? Math.round(v) : Math.round(v * 10) / 10
  const suffix = unitSuffix(unit)
  if (suffix === '°' || suffix === '"') return `${r}${suffix}`
  return suffix ? `${r} ${suffix}` : `${r}`
}

export function MetricCard({
  label, value, unit, target, delta, zone, state, trend,
  phase, offPhase, isEstimated, highlight,
}: MetricCardProps) {
  // Off-phase: dimmed placeholder, grid stays stable.
  if (offPhase || value == null) {
    return (
      <div className="bg-[#0E1210] border border-dashed border-[#242C27] rounded-[18px] p-5 opacity-50 flex flex-col">
        <span className="text-[10px] uppercase tracking-[0.1em] text-[#8B978F] font-semibold">{label}</span>
        <span className="mt-3 text-sm text-[#8B978F]">
          {offPhase ? `— measured at ${offPhase}` : '—'}
        </span>
      </div>
    )
  }

  const zoned = state === 'ok' && zone
  const zoneBorder = zoned ? ZONE_BORDER[zone] : 'border-[#242C27]'
  const zoneWash = zoned ? ZONE_WASH[zone] : ''
  const deltaColor = zoned ? ZONE_TEXT[zone] : 'text-[#8B978F]'
  const trendColor =
    trend.towardPro == null ? 'text-[#8B978F]'
      : trend.towardPro ? 'text-garage-green' : 'text-garage-red'
  const suffix = unitSuffix(unit)

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
      className={cn(
        'bg-[#121714] border rounded-[18px] p-4 flex flex-col transition-all duration-300',
        zoneBorder, zoneWash, highlight && 'shadow-glow-primary-sm',
      )}
    >
      <div className="flex justify-between items-center gap-2">
        <span className="flex items-center gap-2 min-w-0">
          {zoned && (
            <span className={cn('shrink-0 w-1.5 h-1.5 rounded-full', ZONE_DOT[zone])} />
          )}
          <span className="text-[10px] uppercase tracking-[0.1em] text-[#8B978F] font-semibold truncate">{label}</span>
          {phase && (
            <span className="shrink-0 text-[9px] uppercase tracking-wider text-[#8B978F] bg-[#1A211D] px-1.5 py-0.5 rounded">{phase}</span>
          )}
          {isEstimated && (
            <span className="shrink-0 text-[9px] text-[#8B978F]">~est</span>
          )}
        </span>
        {trend.delta !== 0 ? (
          <span className={cn('shrink-0 flex items-center text-xs font-medium', trendColor)}>
            {trend.delta > 0 ? <ArrowUpRight className="w-3 h-3 mr-0.5" /> : <ArrowDownRight className="w-3 h-3 mr-0.5" />}
            {Math.abs(trend.delta)}
          </span>
        ) : (
          <span className="shrink-0 flex items-center text-xs text-[#8B978F]"><Minus className="w-3 h-3 mr-0.5" />0</span>
        )}
      </div>

      <div className="mt-2 flex items-baseline gap-1 min-w-0">
        <span className="text-3xl font-bold font-mono tracking-tight text-[#E7EEE9]">
          {unit === 'rpm' ? Math.round(value) : Math.round(value * 10) / 10}
        </span>
        {suffix && <span className="text-sm text-[#8B978F]">{suffix}</span>}
      </div>

      <div className="mt-1 text-xs font-mono text-[#8B978F]">
        {state === 'raw' ? (
          <span>no tour avg</span>
        ) : state === 'needs_3d' ? (
          <span className="bg-[#1A211D] px-1.5 py-0.5 rounded">NEEDS 3D · tour {target}</span>
        ) : (
          <>Tour {target != null ? fmt(target, unit) : '—'}{' '}
            {delta != null && <span className={deltaColor}>· {delta >= 0 ? '+' : ''}{fmt(delta, unit)}</span>}
          </>
        )}
      </div>
    </motion.div>
  )
}

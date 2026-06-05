import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import { cn } from '../lib/utils'
import { motion } from 'framer-motion'
import type { MetricZone, MetricState } from '../lib/types'

const ZONE_ACCENT: Record<MetricZone, string> = {
  green: 'border-l-garage-green',
  yellow: 'border-l-[#E8B931]',
  red: 'border-l-garage-red',
}
const ZONE_TEXT: Record<MetricZone, string> = {
  green: 'text-garage-green',
  yellow: 'text-[#E8B931]',
  red: 'text-garage-red',
}

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
  return unit === 'deg' ? `${r}°` : unit === 'in' ? `${r}"` : unit ? `${r} ${unit}` : `${r}`
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

  const accent = state === 'ok' && zone ? ZONE_ACCENT[zone] : 'border-l-[#4A554E]'
  const deltaColor = state === 'ok' && zone ? ZONE_TEXT[zone] : 'text-[#8B978F]'
  const trendColor =
    trend.towardPro == null ? 'text-[#8B978F]'
      : trend.towardPro ? 'text-garage-green' : 'text-garage-red'

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
      className={cn(
        'bg-[#121714] border border-[#242C27] border-l-4 rounded-[18px] p-4 flex flex-col transition-all duration-300',
        accent, highlight && 'shadow-glow-primary-sm',
      )}
    >
      <div className="flex justify-between items-center">
        <span className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-[0.1em] text-[#8B978F] font-semibold">{label}</span>
          {phase && (
            <span className="text-[9px] uppercase tracking-wider text-[#8B978F] bg-[#1A211D] px-1.5 py-0.5 rounded">{phase}</span>
          )}
          {isEstimated && (
            <span className="text-[9px] text-[#8B978F]">~est</span>
          )}
        </span>
        {trend.delta !== 0 ? (
          <span className={cn('flex items-center text-xs font-medium', trendColor)}>
            {trend.delta > 0 ? <ArrowUpRight className="w-3 h-3 mr-0.5" /> : <ArrowDownRight className="w-3 h-3 mr-0.5" />}
            {Math.abs(trend.delta)}
          </span>
        ) : (
          <span className="flex items-center text-xs text-[#8B978F]"><Minus className="w-3 h-3 mr-0.5" />0</span>
        )}
      </div>

      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-3xl font-bold font-mono tracking-tight text-[#E7EEE9]">
          {unit === 'rpm' ? Math.round(value) : Math.round(value * 10) / 10}
        </span>
        <span className="text-sm text-[#8B978F]">{unit === 'deg' ? '°' : unit === 'in' ? 'in' : unit}</span>
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

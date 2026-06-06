import { useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import {
  Star,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
} from 'lucide-react'
import { cn } from '../lib/utils'
import { motion } from 'framer-motion'
import { useApi } from '../lib/useApi'
import { getHistory } from '../lib/api'
import { BallHistorySection } from '../components/BallHistorySection'
import { labelFor, deltaVsBaseline, METRIC_GOOD, withinTimeframe } from '../lib/format'
import type { Timeframe } from '../lib/format'
import type { History } from '../lib/types'
import { BODY_CARD_ORDER } from '../lib/metricConfig'

const TREND_METRICS = [
  'shoulder_tilt_deg', 'hip_sway_in', 'spine_angle_deg', 'shoulder_turn_deg',
]

// All body metrics that have meaningful history (exclude hand_depth_in which is raw-only)
const HERO_METRIC_OPTIONS = BODY_CARD_ORDER.filter(
  (m) => m !== 'hand_depth_in',
)

const CONTEXT_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'address', label: 'Address' },
  { value: 'top', label: 'Top' },
  { value: 'impact', label: 'Impact' },
]

const shortDate = (iso: string) => {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

const timeOfDay = (iso: string) => {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

/** Returns true when every ISO string falls on the same calendar date (YYYY-MM-DD). */
const allSameDay = (isos: string[]): boolean => {
  if (isos.length < 2) return false
  const day0 = isos[0].slice(0, 10)
  return isos.every((s) => s.slice(0, 10) === day0)
}

interface TrendVM {
  name: string
  value: string
  delta: number
  deltaGood: 'up' | 'down' | 'neutral'
  isPB: boolean
  sparkline: number[]
}

interface HistoryScreenProps {
  playerId: number | null
}

export function HistoryScreen({ playerId }: HistoryScreenProps) {
  const [timeframe, setTimeframe] = useState<Timeframe>('Month')
  const [heroMetric, setHeroMetric] = useState('shoulder_tilt_deg')
  const [heroContext, setHeroContext] = useState('impact')

  const { data: hero, loading, error } = useApi<History | null>(
    () =>
      playerId
        ? getHistory(playerId, heroMetric, heroContext)
        : Promise.resolve(null),
    [playerId, heroMetric, heroContext],
  )

  const { data: trends } = useApi<TrendVM[]>(
    async () => {
      if (!playerId) return []
      const histories = await Promise.all(
        TREND_METRICS.map((name) =>
          getHistory(playerId, name, 'impact').catch(
            () => ({ points: [] } as Pick<History, 'points'>),
          ),
        ),
      )
      return TREND_METRICS.map((name, i) => {
        const points = withinTimeframe(histories[i].points ?? [], timeframe)
        const vals = points.map((p) => p.value)
        const { value, delta } = deltaVsBaseline(points)
        const good = METRIC_GOOD[name] ?? 'neutral'
        const latest = vals[vals.length - 1]
        const isPB =
          vals.length > 1 &&
          (good === 'down'
            ? latest === Math.min(...vals)
            : good === 'up'
              ? latest === Math.max(...vals)
              : false)
        return {
          name: labelFor(name),
          value: Number(value.toFixed(1)).toString(),
          delta,
          deltaGood: good,
          isPB,
          sparkline: vals.slice(-5),
        }
      })
    },
    [playerId, timeframe],
  )

  const heroPoints = withinTimeframe(hero?.points ?? [], timeframe)
  const heroIsos = heroPoints.map((p) => p.created_at)
  const useTimeAxis = allSameDay(heroIsos)
  const chartData = heroPoints.map((p) => ({
    date: useTimeAxis ? timeOfDay(p.created_at) : shortDate(p.created_at),
    value: p.value,
  }))

  return (
    <div className="h-full flex flex-col p-6 space-y-6 overflow-y-auto">
      {/* Header & Filters */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3 flex-wrap gap-y-2">
          <h1 className="text-2xl font-semibold text-[#E7EEE9]">History</h1>
          <div className="h-6 w-px bg-[#242C27] mx-2" />
          <div className="flex space-x-2 flex-wrap gap-y-2">
            {/* Metric selector — real native select, touch-friendly */}
            <label className="relative flex items-center bg-[#121714] border border-[#242C27] rounded-full px-4 py-2 min-h-[44px] cursor-pointer hover:bg-[#1A211D] transition-colors">
              <span className="text-sm text-[#8B978F] mr-1 shrink-0">Metric:</span>
              <select
                data-testid="metric-select"
                value={heroMetric}
                onChange={(e) => setHeroMetric(e.target.value)}
                className="appearance-none bg-transparent text-sm text-[#E7EEE9] pr-5 cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-garage-green/60"
              >
                {HERO_METRIC_OPTIONS.map((m) => (
                  <option key={m} value={m}>{labelFor(m)}</option>
                ))}
              </select>
              <span className="pointer-events-none absolute right-3 text-[#8B978F] text-xs">▾</span>
            </label>
            {/* Context selector */}
            <label className="relative flex items-center bg-[#121714] border border-[#242C27] rounded-full px-4 py-2 min-h-[44px] cursor-pointer hover:bg-[#1A211D] transition-colors">
              <span className="text-sm text-[#8B978F] mr-1 shrink-0">Context:</span>
              <select
                data-testid="context-select"
                value={heroContext}
                onChange={(e) => setHeroContext(e.target.value)}
                className="appearance-none bg-transparent text-sm text-[#E7EEE9] pr-5 cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-garage-green/60"
              >
                {CONTEXT_OPTIONS.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
              <span className="pointer-events-none absolute right-3 text-[#8B978F] text-xs">▾</span>
            </label>
          </div>
        </div>

        <div className="flex bg-[#121714] border border-[#242C27] rounded-full p-1">
          {(['Session', 'Week', 'Month', 'Year'] as Timeframe[]).map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={cn(
                'px-5 py-2 rounded-full text-sm font-medium transition-all min-h-[44px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60',
                timeframe === tf
                  ? 'bg-[#242C27] text-[#E7EEE9]'
                  : 'text-[#8B978F] hover:text-[#E7EEE9]',
              )}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* HERO Chart */}
      <div className="flex-1 bg-[#121714] border border-[#242C27] rounded-[24px] p-6 flex flex-col min-h-[300px]">
        <h3 className="text-[#8B978F] text-sm font-medium mb-6 uppercase tracking-wider">
          {labelFor(heroMetric)} ({CONTEXT_OPTIONS.find((c) => c.value === heroContext)?.label ?? heroContext})
        </h3>
        {loading ? (
          <div className="flex-1 flex items-center justify-center text-[#8B978F]">
            Loading…
          </div>
        ) : error ? (
          <div className="flex-1 flex items-center justify-center text-garage-red text-sm">
            Failed to load history: {error}
          </div>
        ) : chartData.length === 0 ? (
          <div className="flex-1 flex items-center justify-center text-[#8B978F]">
            No history yet for this player.
          </div>
        ) : (
          <div className="flex-1 w-full min-h-[240px] h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={chartData}
                margin={{ top: 20, right: 20, bottom: 0, left: -20 }}
              >
                <XAxis
                  dataKey="date"
                  stroke="#4A554E"
                  tick={{ fill: '#8B978F', fontSize: 12 }}
                  tickLine={false}
                  axisLine={false}
                  dy={10}
                />
                <YAxis
                  stroke="#4A554E"
                  tick={{ fill: '#8B978F', fontSize: 12 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1A211D',
                    borderColor: '#242C27',
                    borderRadius: '12px',
                    color: '#E7EEE9',
                  }}
                  itemStyle={{ color: '#79BC30', fontWeight: 'bold' }}
                  cursor={{
                    stroke: '#242C27',
                    strokeWidth: 2,
                    strokeDasharray: '4 4',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#79BC30"
                  strokeWidth={4}
                  dot={{
                    fill: '#0A0D0B',
                    stroke: '#79BC30',
                    strokeWidth: 2,
                    r: 6,
                  }}
                  activeDot={{
                    r: 8,
                    fill: '#79BC30',
                    stroke: '#0A0D0B',
                    strokeWidth: 3,
                  }}
                  style={{
                    filter: 'drop-shadow(0px 0px 8px rgba(121,188,48,0.25))',
                  }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Trend Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {(trends ?? []).map((metric, i) => {
          const isGood =
            metric.deltaGood === 'up'
              ? metric.delta > 0
              : metric.deltaGood === 'down'
                ? metric.delta < 0
                : true
          const isNeutral = metric.delta === 0
          const max = Math.max(...metric.sparkline, 1)
          const min = Math.min(...metric.sparkline, 0)
          return (
            <motion.div
              key={metric.name}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className="bg-[#121714] border border-[#242C27] rounded-[18px] p-4 relative overflow-hidden"
            >
              <div className="flex justify-between items-start mb-3 gap-2">
                <span className="text-[10px] uppercase tracking-[0.1em] text-[#8B978F] font-semibold truncate min-w-0">
                  {metric.name}
                </span>
                {metric.isPB && (
                  <div
                    className="bg-garage-amber/10 text-garage-amber p-1 rounded-full"
                    title="Personal Best"
                  >
                    <Star className="w-3.5 h-3.5 fill-current" />
                  </div>
                )}
              </div>

              <div className="flex items-end justify-between">
                <div className="flex flex-col">
                  <span className="text-3xl font-bold font-mono tracking-tight text-[#E7EEE9] mb-1">
                    {metric.value}
                  </span>
                  {!isNeutral ? (
                    <div
                      className={cn(
                        'flex items-center text-xs font-medium',
                        isGood ? 'text-garage-green' : 'text-garage-red',
                      )}
                    >
                      {metric.delta > 0 ? (
                        <ArrowUpRight className="w-3 h-3 mr-0.5" />
                      ) : (
                        <ArrowDownRight className="w-3 h-3 mr-0.5" />
                      )}
                      {Math.abs(metric.delta)} vs base
                    </div>
                  ) : (
                    <div className="flex items-center text-xs font-medium text-[#8B978F]">
                      <Minus className="w-3 h-3 mr-0.5" />
                      No change
                    </div>
                  )}
                </div>

                {/* Mini Sparkline */}
                <div className="w-16 h-8 flex items-end space-x-0.5 opacity-60">
                  {metric.sparkline.map((val, idx) => {
                    const height =
                      max === min ? 50 : Math.max(10, ((val - min) / (max - min)) * 100)
                    return (
                      <div
                        key={idx}
                        className={cn(
                          'flex-1 rounded-t-sm',
                          isGood ? 'bg-garage-green' : 'bg-[#8B978F]',
                        )}
                        style={{ height: `${height}%` }}
                      />
                    )
                  })}
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>

      {/* Ball-data trends vs TrackMan tour averages, per club */}
      <div className="border-t border-[#242C27] pt-6">
        <BallHistorySection playerId={playerId} timeframe={timeframe} />
      </div>
    </div>
  )
}

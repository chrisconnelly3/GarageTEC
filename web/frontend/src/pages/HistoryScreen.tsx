import { useState } from 'react'
import { Activity } from 'lucide-react'
import { cn } from '../lib/utils'
import { useApi } from '../lib/useApi'
import { getHistory } from '../lib/api'
import { BallHistorySection } from '../components/BallHistorySection'
import { HistoryLineChart } from '../components/HistoryLineChart'
import { labelFor, withinTimeframe, unitForMetric, shortDate, timeOfDay, allSameDay } from '../lib/format'
import type { Timeframe } from '../lib/format'
import type { History } from '../lib/types'
import { BODY_CARD_ORDER } from '../lib/metricConfig'

// All body metrics that have meaningful history (exclude hand_depth_in which is raw-only)
const HERO_METRIC_OPTIONS = BODY_CARD_ORDER.filter(
  (m) => m !== 'hand_depth_in',
)

const CONTEXT_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'address', label: 'Address' },
  { value: 'top', label: 'Top' },
  { value: 'impact', label: 'Impact' },
]

interface HistoryScreenProps {
  playerId: number | null
  onOpenSwing: (id: number) => void
}

export function HistoryScreen({ playerId, onOpenSwing }: HistoryScreenProps) {
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

  const heroPoints = withinTimeframe(hero?.points ?? [], timeframe)
  const heroIsos = heroPoints.map((p) => p.created_at)
  const useTimeAxis = allSameDay(heroIsos)
  const chartData = heroPoints.map((p, i) => ({
    idx: i,
    date: useTimeAxis ? timeOfDay(p.created_at) : shortDate(p.created_at),
    value: p.value,
    swingId: p.swing_id,
  }))
  const heroUnit = unitForMetric(heroMetric)
  const heroTarget = hero?.target ?? null

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
          {heroTarget != null && (
            <span className="ml-2 text-[#79BC30] normal-case tracking-normal">
              Tour avg {heroTarget}{heroUnit}
            </span>
          )}
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
          <div className="flex-1 flex flex-col items-center justify-center text-center px-6 gap-3">
            <div className="w-12 h-12 rounded-full bg-[#1A211D] border border-[#242C27] flex items-center justify-center">
              <Activity className="w-5 h-5 text-[#4A554E]" />
            </div>
            {!playerId ? (
              <p className="text-[#8B978F] max-w-xs">
                Select a player above to see their swing history.
              </p>
            ) : (
              <>
                <p className="text-[#E7EEE9] font-medium">
                  No shots in this {timeframe.toLowerCase()} yet
                </p>
                <p className="text-[#8B978F] text-sm max-w-xs">
                  Take some swings on the range, or switch to a longer range above.
                </p>
              </>
            )}
          </div>
        ) : (
          <div className="flex-1 w-full min-h-[240px] h-[240px]">
            <HistoryLineChart
              data={chartData}
              unit={heroUnit}
              target={heroTarget}
              onOpenSwing={onOpenSwing}
            />
          </div>
        )}
      </div>

      {/* Ball-data trends vs TrackMan tour averages, per club */}
      <div className="border-t border-[#242C27] pt-6">
        <BallHistorySection playerId={playerId} timeframe={timeframe} />
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Activity } from 'lucide-react'
import { HistoryLineChart } from './HistoryLineChart'
import { useApi } from '../lib/useApi'
import { getBallHistory, getClubs } from '../lib/api'
import { BALL_METRICS, withinTimeframe, shortDate, timeOfDay, allSameDay } from '../lib/format'
import type { Timeframe } from '../lib/format'
import type { BallHistory } from '../lib/types'

interface Props {
  playerId: number | null
  timeframe: Timeframe
}

/** History → ball metrics over time vs the TrackMan tour average for a chosen
 *  club. Each shot's metric is read from the shot table; the dashed line on the
 *  hero chart is that club's tour target. */
export function BallHistorySection({ playerId, timeframe }: Props) {
  const [clubs, setClubs] = useState<string[]>([])
  // Initialize to null so we don't fire a fetch with a hardcoded 'Driver' before
  // the real clubs list arrives. The useApi dep on `club` means no fetch occurs
  // until club is non-null (guarded below).
  const [club, setClub] = useState<string | null>(null)
  const [heroKey, setHeroKey] = useState<string>('ball_speed')

  useEffect(() => {
    getClubs().then((c) => {
      setClubs(c)
      // Always adopt the first club from the server list on load.
      if (c.length) setClub(c[0])
    }).catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const { data: heroHist } = useApi<BallHistory | null>(
    () =>
      playerId && club
        ? getBallHistory(playerId, heroKey, club).catch(() => null)
        : Promise.resolve(null),
    [playerId, club, heroKey],
  )

  const heroDef = BALL_METRICS.find((m) => m.key === heroKey) ?? BALL_METRICS[0]
  const heroPts = withinTimeframe(
    (heroHist?.points ?? []).map((p) => ({ created_at: p.captured_at, value: p.value })),
    timeframe,
  )
  const useTimeAxis = allSameDay(heroPts.map((p) => p.created_at))
  const chartData = heroPts.map((p, i) => ({
    idx: i,
    date: useTimeAxis ? timeOfDay(p.created_at) : shortDate(p.created_at),
    value: p.value,
  }))
  const heroTarget = heroHist?.target ?? null

  return (
    <div className="space-y-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <h2 className="text-xl font-semibold text-[#E7EEE9]">Ball Data vs Tour</h2>
          <div className="h-6 w-px bg-[#242C27] mx-2" />
          <div className="flex items-center gap-2">
            <label className="text-[11px] uppercase tracking-wider text-[#8B978F] font-semibold">Club</label>
            <select
              value={club ?? ''}
              onChange={(e) => setClub(e.target.value)}
              className="bg-[#121714] border border-[#242C27] rounded-full px-4 py-2 text-sm text-[#E7EEE9] focus:border-garage-green outline-none min-h-[44px]"
            >
              {clubs.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-[11px] uppercase tracking-wider text-[#8B978F] font-semibold">Metric</label>
          <select
            value={heroKey}
            onChange={(e) => setHeroKey(e.target.value)}
            className="bg-[#121714] border border-[#242C27] rounded-full px-4 py-2 text-sm text-[#E7EEE9] focus:border-garage-green outline-none min-h-[44px]"
          >
            {BALL_METRICS.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
          </select>
        </div>
      </div>

      {/* Hero chart with tour target reference line */}
      <div className="bg-[#121714] border border-[#242C27] rounded-[24px] p-6">
        <h3 className="text-[#8B978F] text-sm font-medium mb-6 uppercase tracking-wider">
          {heroDef.label} · {club ?? '—'}
          {heroTarget != null && (
            <span className="ml-2 text-[#79BC30] normal-case tracking-normal">
              Tour avg {heroTarget}{heroDef.unit ? ` ${heroDef.unit}` : ''}
            </span>
          )}
        </h3>
        {chartData.length === 0 ? (
          <div className="h-[260px] flex flex-col items-center justify-center text-center px-6 gap-3">
            <div className="w-12 h-12 rounded-full bg-[#1A211D] border border-[#242C27] flex items-center justify-center">
              <Activity className="w-5 h-5 text-[#4A554E]" />
            </div>
            <p className="text-[#8B978F] max-w-xs">
              No {club ?? 'club'} shots in this range yet. Hit a few, or pick another club above.
            </p>
          </div>
        ) : (
          <div className="w-full h-[260px]">
            <HistoryLineChart
              data={chartData}
              unit={heroDef.unit}
              decimals={heroDef.decimals}
              target={heroTarget}
            />
          </div>
        )}
      </div>
    </div>
  )
}

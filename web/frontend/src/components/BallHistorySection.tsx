import { useEffect, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { Star, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react'
import { cn } from '../lib/utils'
import { useApi } from '../lib/useApi'
import { getBallHistory, getClubs } from '../lib/api'
import { BALL_METRICS, withinTimeframe } from '../lib/format'
import type { BallMetricDef, Timeframe } from '../lib/format'
import type { BallHistory } from '../lib/types'

const shortDate = (iso: string) => {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

interface BallTrendVM {
  def: BallMetricDef
  value: number | null
  target: number | null
  deltaVsTour: number | null   // latest - target
  isGood: boolean
  isPB: boolean
  sparkline: number[]
}

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

  const { data: histories } = useApi<Record<string, BallHistory>>(
    async () => {
      if (!playerId || !club) return {}
      const results = await Promise.all(
        BALL_METRICS.map((m) =>
          getBallHistory(playerId, m.key, club).catch(
            () => ({ player: playerId, metric: m.key, club, target: null, points: [] } as BallHistory),
          ),
        ),
      )
      return Object.fromEntries(results.map((h) => [h.metric, h]))
    },
    [playerId, club],
  )

  // Filter a history's points to the timeframe (keyed on captured_at).
  const filtered = (h: BallHistory | undefined) =>
    withinTimeframe(
      (h?.points ?? []).map((p) => ({ created_at: p.captured_at, value: p.value })),
      timeframe,
    )

  const trends: BallTrendVM[] = BALL_METRICS.map((def) => {
    const h = histories?.[def.key]
    const pts = filtered(h)
    const vals = pts.map((p) => p.value)
    const value = vals.length ? vals[vals.length - 1] : null
    const target = h?.target ?? null
    // Raw delta; rounded only at display time so 2-decimal metrics (smash) keep
    // their precision instead of collapsing to 0.0.
    const deltaVsTour =
      value != null && target != null ? value - target : null
    const isGood =
      deltaVsTour == null || def.good === 'neutral'
        ? false
        : def.good === 'up'
          ? deltaVsTour >= 0
          : deltaVsTour <= 0
    const isPB =
      vals.length > 1 && def.good !== 'neutral' &&
      (def.good === 'up'
        ? value === Math.max(...vals)
        : value === Math.min(...vals))
    return { def, value, target, deltaVsTour, isGood, isPB, sparkline: vals.slice(-5) }
  })

  const heroDef = BALL_METRICS.find((m) => m.key === heroKey) ?? BALL_METRICS[0]
  const heroHist = histories?.[heroKey]
  const heroPts = filtered(heroHist)
  const chartData = heroPts.map((p) => ({ date: shortDate(p.created_at), value: p.value }))
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
          <div className="h-[260px] flex items-center justify-center text-[#8B978F]">
            No {club} shots yet for this player.
          </div>
        ) : (
          <div className="w-full h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 20, right: 20, bottom: 0, left: -20 }}>
                <XAxis dataKey="date" stroke="#4A554E" tick={{ fill: '#8B978F', fontSize: 12 }}
                       tickLine={false} axisLine={false} dy={10} />
                <YAxis stroke="#4A554E" tick={{ fill: '#8B978F', fontSize: 12 }}
                       tickLine={false} axisLine={false} domain={['auto', 'auto']} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1A211D', borderColor: '#242C27', borderRadius: '12px', color: '#E7EEE9' }}
                  itemStyle={{ color: '#79BC30', fontWeight: 'bold' }}
                  cursor={{ stroke: '#242C27', strokeWidth: 2, strokeDasharray: '4 4' }}
                />
                {heroTarget != null && (
                  <ReferenceLine y={heroTarget} stroke="#79BC30" strokeDasharray="6 6"
                                 strokeOpacity={0.6} />
                )}
                <Line type="monotone" dataKey="value" stroke="#79BC30" strokeWidth={4}
                      dot={{ fill: '#0A0D0B', stroke: '#79BC30', strokeWidth: 2, r: 5 }}
                      activeDot={{ r: 7, fill: '#79BC30', stroke: '#0A0D0B', strokeWidth: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Per-metric cards: latest value + vs-tour delta */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {trends.map((t) => {
          const max = Math.max(...t.sparkline, 1)
          const min = Math.min(...t.sparkline, 0)
          const dp = t.def.decimals
          // Benchmarked cards (have a tour target + a good/bad direction) carry a
          // tinted full border + faint wash so they pop above the neutral "raw"
          // (no tour avg) cards — same in-card zone language as MetricCard, no stripe.
          const benchmarked = t.deltaVsTour != null && t.def.good !== 'neutral'
          const cardZone = benchmarked
            ? t.isGood
              ? 'border-garage-green/40 bg-garage-green/[0.08]'
              : 'border-garage-red/40 bg-garage-red/[0.08]'
            : 'border-[#242C27]'
          return (
            <div key={t.def.key}
                 className={cn('bg-[#121714] border rounded-[18px] p-4 relative overflow-hidden', cardZone)}>
              <div className="flex justify-between items-start mb-3 gap-2">
                <span className="flex items-center gap-2 min-w-0">
                  {benchmarked && (
                    <span className={cn('shrink-0 w-1.5 h-1.5 rounded-full',
                      t.isGood ? 'bg-garage-green' : 'bg-garage-red')} />
                  )}
                  <span className="text-[10px] uppercase tracking-[0.1em] text-[#8B978F] font-semibold truncate">
                    {t.def.label}
                  </span>
                </span>
                {t.isPB && (
                  <div className="bg-garage-amber/10 text-garage-amber p-1 rounded-full" title="Personal Best">
                    <Star className="w-3.5 h-3.5 fill-current" />
                  </div>
                )}
              </div>
              <div className="flex items-end justify-between">
                <div className="flex flex-col">
                  <span className="text-3xl font-bold font-mono tracking-tight text-[#E7EEE9] mb-1">
                    {t.value == null ? '--' : t.value.toFixed(dp)}
                  </span>
                  {t.deltaVsTour == null ? (
                    <div className="flex items-center text-xs font-medium text-[#8B978F]">
                      <Minus className="w-3 h-3 mr-0.5" />
                      {t.value == null ? 'No data' : 'No tour avg'}
                    </div>
                  ) : t.def.good === 'neutral' ? (
                    <div className="flex items-center text-xs font-medium text-[#8B978F]">
                      {t.deltaVsTour >= 0 ? '+' : ''}{t.deltaVsTour.toFixed(dp)} vs tour
                    </div>
                  ) : (
                    <div className={cn('flex items-center text-xs font-medium',
                      t.isGood ? 'text-garage-green' : 'text-garage-red')}>
                      {t.deltaVsTour >= 0
                        ? <ArrowUpRight className="w-3 h-3 mr-0.5" />
                        : <ArrowDownRight className="w-3 h-3 mr-0.5" />}
                      {Math.abs(t.deltaVsTour).toFixed(dp)} vs tour
                    </div>
                  )}
                </div>
                <div className="w-16 h-8 flex items-end space-x-0.5 opacity-60">
                  {t.sparkline.map((val, idx) => {
                    const height = max === min ? 50 : Math.max(10, ((val - min) / (max - min)) * 100)
                    return (
                      <div key={idx}
                           className={cn('flex-1 rounded-t-sm',
                             t.def.good !== 'neutral' && t.isGood ? 'bg-garage-green' : 'bg-[#8B978F]')}
                           style={{ height: `${height}%` }} />
                    )
                  })}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

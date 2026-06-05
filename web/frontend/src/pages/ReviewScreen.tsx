import { useEffect, useState } from 'react'
import { SwingReplay } from '../components/SwingReplay'
import { AIInsightCard } from '../components/AIInsightCard'
import { BenchmarkPanel } from '../components/BenchmarkPanel'
import { BallClubStrip } from '../components/BallClubStrip'
import { cn } from '../lib/utils'
import { CheckCircle2, AlertCircle } from 'lucide-react'
import { useApi } from '../lib/useApi'
import { getSwing, getSwings } from '../lib/api'
import { labelFor, coachingToInsights, METRIC_IDEAL } from '../lib/format'
import type { SwingDetail, Metric, SwingSummary } from '../lib/types'

const PHASES = [
  'Address', 'Takeaway', 'Lead-arm', 'Top',
  'Transition', 'Shaft par.', 'Impact', 'Follow-thru',
]

function fmtMetric(m: Metric | undefined): string {
  if (!m || m.value == null) return '--'
  const v = Number(m.value.toFixed(1))
  if (m.unit === 'deg') return `${v}°`
  if (m.unit === 'in') return `${v}"`
  return `${v}${m.unit ?? ''}`
}

function statusFor(name: string, impactVal: number | null | undefined): string {
  const ideal = METRIC_IDEAL[name]
  if (!ideal || impactVal == null) return 'neutral'
  return impactVal >= ideal[0] && impactVal <= ideal[1] ? 'good' : 'bad'
}

interface ReviewScreenProps {
  playerId: number | null
  sessionId: number | null
  defaultSwingId: number | null
}

export function ReviewScreen({ playerId, sessionId, defaultSwingId }: ReviewScreenProps) {
  const [activePhase, setActivePhase] = useState('Impact')
  const [selectedId, setSelectedId] = useState<number | null>(defaultSwingId)
  useEffect(() => { setSelectedId(defaultSwingId) }, [defaultSwingId])

  const { data: swings } = useApi<SwingSummary[]>(
    () => (playerId ? getSwings(playerId, sessionId ?? undefined, 50) : Promise.resolve([])),
    [playerId, sessionId],
  )

  const swingId = selectedId ?? defaultSwingId
  const { data, loading, error } = useApi<SwingDetail | null>(
    () => (swingId ? getSwing(swingId) : Promise.resolve(null)),
    [swingId],
  )

  const picker = (swings?.length ?? 0) > 0 && (
    <div className="flex items-center gap-3">
      <label className="text-[11px] uppercase tracking-wider text-[#8B978F] font-semibold">Swing</label>
      <select
        value={swingId ?? ''}
        onChange={(e) => setSelectedId(Number(e.target.value))}
        className="bg-[#1A211D] border border-[#242C27] rounded-xl px-4 py-2 text-[#E7EEE9] focus:border-garage-green outline-none min-h-[44px]"
      >
        {(swings ?? []).map((s, i) => (
          <option key={s.id} value={s.id}>
            {`#${s.id} · ${s.club ?? '—'} · ${new Date(s.created_at).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}${s.has_shot ? ' · R50' : ''}${i === 0 ? ' (latest)' : ''}`}
          </option>
        ))}
      </select>
    </div>
  )

  if (!swingId || (!data && !loading && !error)) {
    return (
      <div className="h-full flex flex-col p-6 space-y-6 overflow-y-auto">
        {picker}
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center border-2 border-dashed border-[#242C27] rounded-[24px] bg-[#0A0D0B]/50 px-12 py-16">
            <h2 className="text-xl font-semibold text-[#E7EEE9] mb-2">
              Select a swing to review
            </h2>
            <p className="text-[#8B978F]">
              Take a swing or pick one from a session to see the breakdown.
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center text-[#8B978F]">
        Loading…
      </div>
    )
  }
  if (error || !data) {
    return (
      <div className="h-full flex items-center justify-center p-6">
        <div className="rounded-[18px] border border-garage-red/40 bg-garage-red/10 px-6 py-4 text-sm text-garage-red">
          Failed to load swing: {error ?? 'not found'}
        </div>
      </div>
    )
  }

  // Group metrics by name → one row per name with address/top/impact columns.
  const byName = new Map<string, Metric[]>()
  for (const m of data.metrics) {
    const arr = byName.get(m.name) ?? []
    arr.push(m)
    byName.set(m.name, arr)
  }
  const rows = Array.from(byName.entries()).map(([name, ms]) => {
    const impact = ms.find((x) => x.context === 'impact')
    return {
      name: labelFor(name),
      address: fmtMetric(ms.find((x) => x.context === 'address')),
      top: fmtMetric(ms.find((x) => x.context === 'top')),
      impact: fmtMetric(impact),
      status: statusFor(name, impact?.value),
    }
  })

  const presentPhases = new Set(
    data.moments.map((m) => {
      if (m.kind === 'address') return 'Address'
      if (m.kind === 'top') return 'Top'
      if (m.kind === 'impact') return 'Impact'
      return m.kind
    }),
  )

  const coachContent = data.coaching[0]?.content ?? null
  const insights = coachingToInsights(coachContent)

  return (
    <div className="h-full flex flex-col p-6 space-y-6 overflow-y-auto">
      {picker}
      {/* HERO: Video Scrubber & Timeline */}
      <div className="bg-[#121714] border border-[#242C27] rounded-[24px] p-6 flex flex-col space-y-6">
        <div className="h-[360px] rounded-[18px] overflow-hidden">
          <SwingReplay />
        </div>

        {/* 8-Phase Timeline */}
        <div className="relative pt-4 pb-2 px-4">
          <div className="absolute top-6 left-8 right-8 h-0.5 bg-[#242C27]" />
          <div className="flex justify-between relative">
            {PHASES.map((phase) => {
              const isActive = activePhase === phase
              const exists = presentPhases.has(phase)
              return (
                <button
                  key={phase}
                  onClick={() => setActivePhase(phase)}
                  className="flex flex-col items-center space-y-3 group"
                >
                  <div
                    className={cn(
                      'w-4 h-4 rounded-full border-2 z-10 transition-all',
                      isActive
                        ? 'bg-garage-green border-garage-green shadow-glow-primary-sm scale-125'
                        : exists
                          ? 'bg-[#121714] border-garage-green/60 group-hover:border-garage-green'
                          : 'bg-[#121714] border-[#4A554E] group-hover:border-[#8B978F]',
                    )}
                  />
                  <span
                    className={cn(
                      'text-[10px] uppercase tracking-wider font-medium transition-colors',
                      isActive
                        ? 'text-garage-green'
                        : 'text-[#8B978F] group-hover:text-[#E7EEE9]',
                    )}
                  >
                    {phase}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Full Metric Panel */}
        <div className="lg:col-span-2 bg-[#121714] border border-[#242C27] rounded-[24px] p-6">
          <h3 className="text-lg font-semibold text-[#E7EEE9] mb-6">
            Body Mechanics Breakdown
          </h3>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#242C27]">
                  <th className="pb-3 text-[11px] uppercase tracking-wider text-[#8B978F] font-semibold">
                    Metric
                  </th>
                  <th className="pb-3 text-[11px] uppercase tracking-wider text-[#8B978F] font-semibold">
                    Address
                  </th>
                  <th className="pb-3 text-[11px] uppercase tracking-wider text-[#8B978F] font-semibold">
                    Top
                  </th>
                  <th className="pb-3 text-[11px] uppercase tracking-wider text-[#8B978F] font-semibold">
                    Impact
                  </th>
                  <th className="pb-3 text-[11px] uppercase tracking-wider text-[#8B978F] font-semibold">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#242C27]/50">
                {rows.map((m) => (
                  <tr
                    key={m.name}
                    className="hover:bg-[#1A211D]/50 transition-colors"
                  >
                    <td className="py-4 text-sm font-medium text-[#E7EEE9]">
                      {m.name}
                    </td>
                    <td className="py-4 text-sm font-mono text-[#8B978F]">
                      {m.address}
                    </td>
                    <td className="py-4 text-sm font-mono text-[#8B978F]">
                      {m.top}
                    </td>
                    <td
                      className={cn(
                        'py-4 text-sm font-mono font-semibold',
                        m.status === 'bad'
                          ? 'text-garage-red'
                          : 'text-[#E7EEE9]',
                      )}
                    >
                      {m.impact}
                    </td>
                    <td className="py-4">
                      {m.status === 'good' && (
                        <CheckCircle2 className="w-4 h-4 text-garage-green" />
                      )}
                      {m.status === 'bad' && (
                        <AlertCircle className="w-4 h-4 text-garage-red" />
                      )}
                      {m.status === 'neutral' && (
                        <div className="w-2 h-2 rounded-full bg-[#8B978F] ml-1" />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* AI Feedback + vs Tour Pro */}
        <div className="flex flex-col space-y-6">
          <AIInsightCard
            headline={coachContent?.headline ?? 'Detailed Swing Analysis'}
            insights={insights}
          />
          <BenchmarkPanel benchmarks={data.benchmarks ?? []} />
        </div>
      </div>

      {/* Matched Shot Panel */}
      <div className="mt-auto">
        <h4 className="text-[11px] uppercase tracking-wider text-[#8B978F] font-semibold mb-3 ml-2">
          Matched R50 Data
        </h4>
        <BallClubStrip shot={data.shot} />
      </div>
    </div>
  )
}

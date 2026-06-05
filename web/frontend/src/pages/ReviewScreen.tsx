import { useEffect, useState } from 'react'
import { SwingReplay } from '../components/SwingReplay'
import { AIInsightCard } from '../components/AIInsightCard'
import { MetricCard } from '../components/MetricCard'
import { PhaseTimeline } from '../components/PhaseTimeline'
import { useApi } from '../lib/useApi'
import { getSwing, getSwings, mediaUrl } from '../lib/api'
import { labelFor, coachingToInsights } from '../lib/format'
import { BALL_BENCHMARK_ORDER, BALL_RAW_ORDER, BODY_CARD_ORDER } from '../lib/metricConfig'
import { phaseAtTime } from '../lib/phase'
import type { SwingDetail, SwingSummary, Benchmark } from '../lib/types'

const ZONE_TEXT: Record<string, string> = {
  green: 'text-garage-green', yellow: 'text-[#E8B931]', red: 'text-garage-red',
}

const CAP = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

interface ReviewScreenProps {
  playerId: number | null
  sessionId: number | null
  defaultSwingId: number | null
}

export function ReviewScreen({ playerId, sessionId, defaultSwingId }: ReviewScreenProps) {
  const [activePhase, setActivePhase] = useState('Impact')
  const [seek, setSeek] = useState<{ t: number } | null>(null)
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

  // Benchmark lookup keyed by "name|context"; the body table colors each cell
  // vs the tour target via the per-row `state`/`zone` from the backend.
  const benchByKey = new Map<string, Benchmark>()
  for (const b of data.benchmarks ?? []) benchByKey.set(`${b.name}|${b.context}`, b)

  const annotated = data.media?.find((m) => m.kind === 'annotated_video')
  const videoSrc = annotated ? mediaUrl(annotated.path) : null

  const cell = (name: string, context: string) => {
    const b = benchByKey.get(`${name}|${context}`)
    if (!b) return <span className="text-[#4A554E]">—</span>
    const color = b.state === 'ok' && b.zone ? ZONE_TEXT[b.zone] : 'text-[#E7EEE9]'
    const sub = b.state === 'raw' ? 'no tour avg'
      : b.state === 'needs_3d' ? `needs 3D · tour ${b.target}`
        : `${b.delta != null && b.delta >= 0 ? '+' : ''}${b.delta} · tour ${b.target}`
    return (
      <span>
        <span className={color}>{b.value}{b.unit === 'deg' ? '°' : b.unit === 'in' ? '"' : ''}</span>
        <span className="block text-[9px] text-[#8B978F]">{sub}</span>
      </span>
    )
  }

  const coachContent = data.coaching[0]?.content ?? null
  const insights = coachingToInsights(coachContent)

  return (
    <div className="h-full flex flex-col p-6 space-y-6 overflow-y-auto">
      {picker}
      {/* HERO: Video Scrubber & Timeline */}
      <div className="bg-[#121714] border border-[#242C27] rounded-[24px] p-6 flex flex-col space-y-6">
        <div className="h-[360px] rounded-[18px] overflow-hidden">
          <SwingReplay src={videoSrc} seek={seek}
            onTime={(t) => setActivePhase(CAP(phaseAtTime(data.moments, t)))} />
        </div>

        {/* 8-Phase Timeline */}
        <PhaseTimeline
          present={new Set(data.moments.map((m) => m.kind === 'address' ? 'Address' : m.kind === 'top' ? 'Top' : m.kind === 'impact' ? 'Impact' : m.kind))}
          active={activePhase}
          onSeek={(label) => {
            setActivePhase(label)
            const mt = data.moments.find((m) => CAP(m.kind) === label)
            if (mt?.time_s != null) setSeek({ t: mt.time_s })
          }} />
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
                </tr>
              </thead>
              <tbody className="divide-y divide-[#242C27]/50">
                {BODY_CARD_ORDER.map((name) => (
                  <tr key={name} className="hover:bg-[#1A211D]/50 transition-colors">
                    <td className="py-3 text-sm font-medium text-[#E7EEE9]">{labelFor(name)}</td>
                    <td className="py-3 text-sm font-mono">{cell(name, 'address')}</td>
                    <td className="py-3 text-sm font-mono">{cell(name, 'top')}</td>
                    <td className="py-3 text-sm font-mono">{cell(name, 'impact')}</td>
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
        </div>
      </div>

      {/* Ball & Club · vs Tour Pro */}
      <div className="mt-auto">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-sm font-semibold text-[#E7EEE9]">Ball &amp; Club · vs Tour Pro</span>
          <span className="text-[10px] uppercase tracking-wider text-[#8B978F]">
            {data.shot?.club ? `${data.shot.club} · impact` : 'no matched shot'}
          </span>
        </div>
        <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
          {(() => {
            const bench = new Map((data.ball_benchmarks ?? []).map((b) => [b.key, b]))
            const raw = new Map((data.ball_raw ?? []).map((r) => [r.key, r]))
            const cards: JSX.Element[] = []
            for (const key of BALL_BENCHMARK_ORDER) {
              const b = bench.get(key); if (!b) continue
              cards.push(<MetricCard key={key} label={b.label} value={b.value} unit={b.unit}
                target={b.target} delta={b.delta} zone={b.zone} state="ok"
                trend={{ delta: 0, towardPro: null }} />)
            }
            for (const key of BALL_RAW_ORDER) {
              const r = raw.get(key); if (!r || r.value == null) continue
              cards.push(<MetricCard key={key} label={r.label} value={r.value} unit={r.unit}
                target={null} delta={null} zone={null} state="raw"
                trend={{ delta: 0, towardPro: null }} />)
            }
            return cards.length ? cards : <p className="text-sm text-[#8B978F] col-span-full">No matched ball data.</p>
          })()}
        </div>
      </div>
    </div>
  )
}

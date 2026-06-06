import { useEffect, useMemo, useState } from 'react'
import { SwingReplay } from '../components/SwingReplay'
import { MetricCard } from '../components/MetricCard'
import { AIInsightCard } from '../components/AIInsightCard'
import { LiveTimeline } from '../components/LiveTimeline'
import { motion, AnimatePresence } from 'framer-motion'
import { useApi } from '../lib/useApi'
import { getLatestSwing, getHistory, getBallHistory, mediaUrl } from '../lib/api'
import { labelFor, isEstimated } from '../lib/format'
import { BODY_CARD_ORDER, BALL_BENCHMARK_ORDER, BALL_RAW_ORDER, METRIC_UNIT } from '../lib/metricConfig'
import { phaseAtTime, momentKindToLabel } from '../lib/phase'
import { computeTrend } from '../lib/trend'
import type { SwingDetail, Benchmark, BallBenchmark, BallRawField } from '../lib/types'

const CAP = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

interface LiveScreenProps {
  playerId: number | null
  sessionId: number | null
  lastSwing: unknown
  lastCapture: unknown
  activeClub?: string | null
}

export function LiveScreen({ playerId, sessionId, lastSwing, activeClub = null }: LiveScreenProps) {
  const { data, error, reload } = useApi<SwingDetail | null>(
    () => (playerId ? getLatestSwing(playerId, sessionId ?? undefined) : Promise.resolve(null)),
    [playerId, sessionId],
  )
  useEffect(() => { reload() }, [lastSwing]) // eslint-disable-line react-hooks/exhaustive-deps

  const [videoTime, setVideoTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [seek, setSeek] = useState<{ t: number } | null>(null)
  const moments = data?.moments ?? []

  // The body metric cards only have three real phases (address/top/impact), so
  // they snap to the latest CARD phase at the playhead. Before any video plays
  // (videoTime 0) we default to impact, the most data-rich phase.
  const cardPhase = videoTime > 0 ? phaseAtTime(moments, videoTime) : 'impact'

  // The position stepper shows EVERY detected swing position (takeaway, lead-arm,
  // transition, shaft-parallel, follow-through, …), so its highlight is the
  // finest-grained marker at/under the playhead — independent of the card phase.
  const stepLabel = useMemo(() => {
    const ms = moments
      .filter((m) => m.time_s != null && Number.isFinite(m.time_s as number))
      .map((m) => ({ t: m.time_s as number, label: momentKindToLabel(m.kind) }))
      .sort((a, b) => a.t - b.t)
    if (ms.length === 0) return CAP(cardPhase)
    let label = ms[0].label
    for (const m of ms) if (m.t <= videoTime) label = m.label
    return label
  }, [moments, videoTime, cardPhase])

  const swingId = data?.swing.id ?? null
  const { data: histories } = useApi<Record<string, { value: number }[]>>(
    async () => {
      if (!playerId || !swingId) return {}
      const entries = await Promise.all(
        BODY_CARD_ORDER.map(async (name) => {
          const h = await getHistory(playerId, name, cardPhase).catch(() => ({ points: [] }))
          return [name, (h.points ?? []).slice(0, -1)] as const
        }),
      )
      return Object.fromEntries(entries)
    },
    [playerId, swingId, cardPhase],
  )

  const ballClub = data?.shot?.club ?? null
  const { data: ballHistories } = useApi<Record<string, { value: number }[]>>(
    async () => {
      if (!playerId || !swingId || !ballClub) return {}
      const entries = await Promise.all(
        BALL_BENCHMARK_ORDER.map(async (key) => {
          const h = await getBallHistory(playerId, key, ballClub).catch(() => ({ points: [] }))
          return [key, (h.points ?? []).slice(0, -1)] as const
        }),
      )
      return Object.fromEntries(entries)
    },
    [playerId, swingId, ballClub],
  )

  const annotated = data?.media?.find((m) => m.kind === 'annotated_video')
  const videoSrc = annotated ? mediaUrl(annotated.path) : null

  // Open the replay on the impact frame (matches the impact-default cards).
  const impactTime = moments.find((m) => m.kind === 'impact')?.time_s ?? null

  const benchByKey = useMemo(() => {
    const map = new Map<string, Benchmark>()
    for (const b of data?.benchmarks ?? []) map.set(`${b.name}|${b.context}`, b)
    return map
  }, [data])

  // Use the NEWEST coaching entry (a real read is generated after the mock seed).
  const coachContent = data?.coaching[data.coaching.length - 1]?.content ?? null
  const status: 'waiting' | 'captured' = data ? 'captured' : 'waiting'

  // Ball & Club cards (benchmark cards first, then the raw no-reference fields).
  const ballCards = (() => {
    const bench = new Map((data?.ball_benchmarks ?? []).map((b: BallBenchmark) => [b.key, b]))
    const raw = new Map((data?.ball_raw ?? []).map((r: BallRawField) => [r.key, r]))
    const cards = []
    for (const key of BALL_BENCHMARK_ORDER) {
      const b = bench.get(key); if (!b) continue
      cards.push(<MetricCard key={key} label={b.label} value={b.value} unit={b.unit}
        target={b.target} delta={b.delta} zone={b.zone} state="ok" compact
        trend={computeTrend((ballHistories?.[key] ?? []).slice(-10), b.value, b.target, b.direction)} />)
    }
    for (const key of BALL_RAW_ORDER) {
      const r = raw.get(key); if (!r || r.value == null) continue
      cards.push(<MetricCard key={key} label={r.label} value={r.value} unit={r.unit}
        target={null} delta={null} zone={null} state="raw" compact
        trend={{ delta: 0, towardPro: null }} />)
    }
    return cards
  })()

  return (
    <div className="h-full flex flex-col p-4 gap-3 overflow-hidden">
      {error && (
        <div className="flex-shrink-0 rounded-[18px] border border-garage-red/40 bg-garage-red/10 px-6 py-3 text-sm text-garage-red">
          Failed to load live data: {error}
        </div>
      )}

      <AnimatePresence mode="wait">
        {status === 'waiting' ? (
          <motion.div key="waiting" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-[#242C27] rounded-[24px] bg-[#0A0D0B]/50">
            <div className="w-16 h-16 rounded-full bg-[#121714] border border-[#242C27] flex items-center justify-center mb-6 relative">
              <div className="absolute inset-0 rounded-full border-2 border-garage-green animate-ping opacity-20" />
              <div className="w-3 h-3 rounded-full bg-garage-green animate-pulse" />
            </div>
            <h2 className="text-2xl font-semibold text-[#E7EEE9] mb-2">Waiting for your R50</h2>
            <p className="text-[#8B978F]">Step up and take a swing. Data will appear here automatically.</p>
          </motion.div>
        ) : (
          <motion.div key="captured" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            className="flex-1 min-h-0 flex flex-col lg:flex-row gap-3">
            {/* LEFT (~46%): video player → position stepper → AI coach read. */}
            <div className="flex flex-col gap-3 min-h-0 lg:basis-[46%] lg:flex-none">
              {/* Video grows to fill leftover height above the stepper + coach. */}
              <div className="flex-[4] min-h-0">
                <SwingReplay src={videoSrc} highlight fill seek={seek} impactTime={impactTime}
                  onDuration={setDuration}
                  onTime={setVideoTime} />
              </div>

              {/* Position stepper — every detected swing position on one time-accurate track. */}
              <div className="flex-shrink-0 rounded-[18px] border border-[#242C27] bg-[#121714]">
                <LiveTimeline moments={moments} duration={duration} currentTime={videoTime}
                  activeLabel={stepLabel}
                  onSeek={(t) => setSeek({ t })} />
              </div>

              {/* AI coach read. */}
              <div className="flex-[2] min-h-0">
                <AIInsightCard headline={coachContent?.headline ?? 'No coaching available yet.'}
                  summary={coachContent?.summary} highlight />
              </div>
            </div>

            {/* RIGHT (~56%): ALL metric cards — Ball & Club and Body Mechanics. */}
            <div className="flex-1 min-h-0 overflow-y-auto pr-1 flex flex-col gap-4" data-testid="metrics-column">
              {/* Ball & Club · vs Tour Pro */}
              <section data-testid="ball-club-section">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-semibold text-[#E7EEE9]">Ball &amp; Club · vs Tour Pro</span>
                  {activeClub && (
                    <span className="text-[10px] uppercase tracking-wider text-[#8B978F]">
                      {activeClub} · impact
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-2 xl:grid-cols-4 gap-2">
                  {ballCards.length ? ballCards : (
                    <p className="text-sm text-[#8B978F] col-span-full">
                      {activeClub
                        ? "No ball data for this swing yet. It appears when your R50 reports the shot."
                        : "Pick the club you're hitting so we compare your ball numbers to the right Tour average."}
                    </p>
                  )}
                </div>
              </section>

              {/* Body Mechanics · vs Tour Pro */}
              <section data-testid="body-section">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-semibold text-[#E7EEE9]">Body Mechanics · vs Tour Pro</span>
                  <span className="text-[10px] uppercase tracking-wider text-[#8B978F]">{cardPhase}</span>
                </div>
                <div className="grid grid-cols-2 xl:grid-cols-4 gap-2">
                  {BODY_CARD_ORDER.map((name) => {
                    const b = benchByKey.get(`${name}|${cardPhase}`)
                    const unit = b?.unit ?? METRIC_UNIT[name] ?? ''
                    if (!b) {
                      return <MetricCard key={name} label={labelFor(name)} value={null} unit={unit}
                        target={null} delta={null} zone={null} state="raw" offPhase={cardPhase}
                        trend={{ delta: 0, towardPro: null }} compact />
                    }
                    const trend = computeTrend(histories?.[name] ?? [], b.value, b.target, b.direction)
                    return <MetricCard key={name} label={labelFor(name)} phase={cardPhase}
                      value={b.value} unit={b.unit ?? unit} target={b.target} delta={b.delta}
                      zone={b.zone} state={b.state} trend={trend} isEstimated={isEstimated(null)} compact />
                  })}
                </div>
              </section>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

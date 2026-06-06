import { useEffect, useMemo, useState } from 'react'
import { SwingReplay } from '../components/SwingReplay'
import { MetricCard } from '../components/MetricCard'
import { AIInsightCard } from '../components/AIInsightCard'
import { LiveTimeline } from '../components/LiveTimeline'
import { motion, AnimatePresence } from 'framer-motion'
import { useApi } from '../lib/useApi'
import { getLatestSwing, getHistory, getBallHistory, mediaUrl } from '../lib/api'
import { labelFor, coachingToInsights, isEstimated } from '../lib/format'
import { BODY_CARD_ORDER, BALL_BENCHMARK_ORDER, BALL_RAW_ORDER, METRIC_UNIT } from '../lib/metricConfig'
import { phaseAtTime } from '../lib/phase'
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
  const [manualPhase, setManualPhase] = useState<string | null>(null)
  const moments = data?.moments ?? []
  // Default to impact (the most data-rich phase). Follows the real playhead once
  // video plays (videoTime > 0). A tapped PhaseTimeline button sets manualPhase
  // immediately (even with no video). Real playback clears the manual override.
  const currentPhase = manualPhase ?? (videoTime > 0 ? phaseAtTime(moments, videoTime) : 'impact')

  const swingId = data?.swing.id ?? null
  const { data: histories } = useApi<Record<string, { value: number }[]>>(
    async () => {
      if (!playerId || !swingId) return {}
      const entries = await Promise.all(
        BODY_CARD_ORDER.map(async (name) => {
          const h = await getHistory(playerId, name, currentPhase).catch(() => ({ points: [] }))
          return [name, (h.points ?? []).slice(0, -1)] as const
        }),
      )
      return Object.fromEntries(entries)
    },
    [playerId, swingId, currentPhase],
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

  // Use the NEWEST coaching entry (a real read is generated after the mock seed),
  // so the displayed analysis is the latest one for this swing.
  const coachContent = data?.coaching[data.coaching.length - 1]?.content ?? null
  const insights = coachingToInsights(coachContent)
  const status: 'waiting' | 'captured' = data ? 'captured' : 'waiting'

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
            {/* LEFT (~62%): video fills remaining height → LiveTimeline → Ball & Club strip.
                The strip is flex-shrink-0 so the video area absorbs height variance. */}
            <div className="flex flex-col gap-2 min-h-0 lg:basis-[62%] lg:flex-none">
              {/* Video player grows to fill leftover height above the timeline + strip. */}
              <SwingReplay src={videoSrc} highlight fill seek={seek} impactTime={impactTime}
                onDuration={setDuration}
                onTime={(t) => {
                  setVideoTime(t)
                  if (t > 0) setManualPhase(null) // real playback takes over
                }} />
              {/* Unified time-accurate scrubber — single source of truth for the playhead. */}
              <div className="flex-shrink-0 rounded-[18px] border border-[#242C27] bg-[#121714]">
                <LiveTimeline moments={moments} duration={duration} currentTime={videoTime}
                  activeLabel={CAP(currentPhase)}
                  onSeek={(t, label) => {
                    setManualPhase(label.toLowerCase())
                    setSeek({ t })
                  }} />
              </div>
              {/* Ball & Club strip — compact grid spanning the left column width. */}
              <div className="flex-shrink-0 rounded-[18px] border border-[#242C27] bg-[#121714] p-3"
                data-testid="ball-club-strip">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-xs font-semibold text-[#E7EEE9]">Ball &amp; Club · vs Tour Pro</span>
                  {activeClub && (
                    <span className="text-[10px] uppercase tracking-wider text-[#8B978F]">
                      {activeClub} · impact
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-6 gap-1.5">
                  {(() => {
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
                    if (cards.length) return cards
                    if (!activeClub) {
                      return (
                        <p className="text-sm text-[#8B978F] col-span-full">
                          Pick the club you're hitting so we compare your ball numbers to the right Tour average.
                        </p>
                      )
                    }
                    return (
                      <p className="text-sm text-[#8B978F] col-span-full">
                        No ball data for this swing yet. It appears when your R50 reports the shot.
                      </p>
                    )
                  })()}
                </div>
              </div>
            </div>

            {/* RIGHT (~38%): AI coach (capped max-h-[38%]) + Body Mechanics only.
                Ball cards moved to left column — this column should fit without scroll. */}
            <div className="flex-1 min-h-0 flex flex-col gap-3">
              <div className="flex-shrink-0 min-h-0 max-h-[38%]">
                <AIInsightCard headline={coachContent?.headline ?? 'No coaching available yet.'}
                  summary={coachContent?.summary} insights={insights} highlight />
              </div>

              <div className="flex-shrink-0">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-xs font-semibold text-[#E7EEE9]">Body Mechanics · vs Tour Pro</span>
                  <span className="text-[10px] uppercase tracking-wider text-[#8B978F]">{currentPhase}</span>
                </div>
                <div className="grid grid-cols-2 gap-1.5">
                  {BODY_CARD_ORDER.map((name) => {
                    const b = benchByKey.get(`${name}|${currentPhase}`)
                    const unit = b?.unit ?? METRIC_UNIT[name] ?? ''
                    if (!b) {
                      return <MetricCard key={name} label={labelFor(name)} value={null} unit={unit}
                        target={null} delta={null} zone={null} state="raw" offPhase={currentPhase}
                        trend={{ delta: 0, towardPro: null }} compact />
                    }
                    const trend = computeTrend(histories?.[name] ?? [], b.value, b.target, b.direction)
                    return <MetricCard key={name} label={labelFor(name)} phase={currentPhase}
                      value={b.value} unit={b.unit ?? unit} target={b.target} delta={b.delta}
                      zone={b.zone} state={b.state} trend={trend} isEstimated={isEstimated(null)} compact />
                  })}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

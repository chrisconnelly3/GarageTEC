import { useEffect } from 'react'
import { SwingReplay } from '../components/SwingReplay'
import { MetricCard } from '../components/MetricCard'
import { AIInsightCard } from '../components/AIInsightCard'
import { BallClubStrip } from '../components/BallClubStrip'
import { motion, AnimatePresence } from 'framer-motion'
import { useApi } from '../lib/useApi'
import { getLatestSwing, getHistory } from '../lib/api'
import {
  labelFor, isEstimated, deltaVsBaseline, coachingToInsights,
  METRIC_GOOD, METRIC_IDEAL,
} from '../lib/format'
import type { SwingDetail } from '../lib/types'

const CARD_METRICS = [
  'shoulder_tilt_deg', 'hip_sway_in', 'spine_angle_deg',
  'early_extension_in', 'hand_depth_in', 'shoulder_turn_deg',
]

interface LiveScreenProps {
  playerId: number | null
  sessionId: number | null
  lastSwing: unknown
  lastCapture: unknown
}

export function LiveScreen({ playerId, sessionId, lastSwing }: LiveScreenProps) {
  const { data, loading, error, reload } = useApi<SwingDetail | null>(
    () =>
      playerId
        ? getLatestSwing(playerId, sessionId ?? undefined)
        : Promise.resolve(null),
    [playerId, sessionId],
  )

  // Re-fetch when a new swing becomes ready over SSE.
  useEffect(() => { reload() }, [lastSwing]) // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch the per-metric history once (for delta vs baseline), keyed on swing id.
  const swingId = data?.swing.id ?? null
  const { data: deltas } = useApi<Record<string, number>>(
    async () => {
      if (!playerId || !swingId) return {}
      const results = await Promise.all(
        CARD_METRICS.map((name) =>
          getHistory(playerId, name, 'impact')
            .then((h) => [name, deltaVsBaseline(h.points).delta] as const)
            .catch(() => [name, 0] as const),
        ),
      )
      return Object.fromEntries(results)
    },
    [playerId, swingId],
  )

  const status: 'waiting' | 'captured' = data ? 'captured' : 'waiting'

  const impactMetrics = data?.metrics.filter((m) => m.context === 'impact') ?? []
  const cards = CARD_METRICS
    .map((name) => impactMetrics.find((m) => m.name === name))
    .filter((m): m is NonNullable<typeof m> => !!m)

  const coachContent = data?.coaching[0]?.content ?? null
  const insights = coachingToInsights(coachContent)

  return (
    <div className="h-full flex flex-col p-6 space-y-6 overflow-y-auto">
      {error && (
        <div className="rounded-[18px] border border-garage-red/40 bg-garage-red/10 px-6 py-4 text-sm text-garage-red">
          Failed to load live data: {error}
        </div>
      )}
      <AnimatePresence mode="wait">
        {status === 'waiting' ? (
          <motion.div
            key="waiting"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-[#242C27] rounded-[24px] bg-[#0A0D0B]/50"
          >
            <div className="w-16 h-16 rounded-full bg-[#121714] border border-[#242C27] flex items-center justify-center mb-6 relative">
              <div className="absolute inset-0 rounded-full border-2 border-garage-green animate-ping opacity-20" />
              <div className="w-3 h-3 rounded-full bg-garage-green shadow-glow-primary-sm animate-pulse" />
            </div>
            <h2 className="text-2xl font-semibold text-[#E7EEE9] mb-2">
              {loading ? 'Loading…' : 'Waiting for your R50'}
            </h2>
            <p className="text-[#8B978F]">
              Step up and take a swing. Data will appear here automatically.
            </p>
          </motion.div>
        ) : (
          <motion.div
            key="captured"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex-1 flex flex-col space-y-6"
          >
            {/* Top Row: Hero Video + AI Insights */}
            <div className="flex flex-col lg:flex-row gap-6 h-[400px]">
              <div className="flex-[2] h-full">
                <SwingReplay highlight={true} />
              </div>
              <div className="flex-1 h-full">
                <AIInsightCard
                  headline={
                    coachContent?.headline ?? 'No coaching available yet.'
                  }
                  insights={insights}
                  highlight={true}
                />
              </div>
            </div>

            {/* Middle Row: Metrics Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              {cards.map((m) => (
                <MetricCard
                  key={m.name}
                  name={labelFor(m.name)}
                  value={m.value ?? 0}
                  unit={m.unit ?? ''}
                  delta={deltas?.[m.name] ?? 0}
                  deltaGood={METRIC_GOOD[m.name] ?? 'neutral'}
                  idealRange={METRIC_IDEAL[m.name] ?? [0, 1]}
                  currentNum={m.value ?? 0}
                  isEstimated={isEstimated(m.method)}
                  highlight={m.name === 'hip_sway_in'}
                />
              ))}
            </div>

            {/* Bottom Row: Ball & Club Strip */}
            <div className="mt-auto pt-2">
              <BallClubStrip shot={data?.shot ?? null} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

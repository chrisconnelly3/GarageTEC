import { useEffect, useState } from 'react'
import { SwingReplay } from '../components/SwingReplay'
import { MetricCard } from '../components/MetricCard'
import { AIInsightCard } from '../components/AIInsightCard'
import { BallClubStrip } from '../components/BallClubStrip'
import { motion, AnimatePresence } from 'framer-motion'
export function LiveScreen() {
  const [status, setStatus] = useState<'waiting' | 'captured'>('waiting')
  // Simulate a shot capture for demonstration
  useEffect(() => {
    const timer = setInterval(() => {
      setStatus((prev) => (prev === 'waiting' ? 'captured' : 'waiting'))
    }, 8000)
    return () => clearInterval(timer)
  }, [])
  const metrics = [
    {
      name: 'Shoulder Tilt',
      value: 38,
      unit: 'deg',
      delta: 2,
      deltaGood: 'up' as const,
      idealRange: [35, 45] as [number, number],
      currentNum: 38,
    },
    {
      name: 'Hip Sway',
      value: 2.5,
      unit: 'in',
      delta: -1.2,
      deltaGood: 'down' as const,
      idealRange: [0, 2] as [number, number],
      currentNum: 2.5,
    },
    {
      name: 'Spine Angle',
      value: 42,
      unit: 'deg',
      delta: 0,
      deltaGood: 'neutral' as const,
      idealRange: [40, 45] as [number, number],
      currentNum: 42,
      isEstimated: true,
    },
    {
      name: 'Early Ext.',
      value: 1.8,
      unit: 'in',
      delta: -0.5,
      deltaGood: 'down' as const,
      idealRange: [0, 1] as [number, number],
      currentNum: 1.8,
    },
    {
      name: 'Hand Depth',
      value: 14,
      unit: 'in',
      delta: 1,
      deltaGood: 'up' as const,
      idealRange: [12, 16] as [number, number],
      currentNum: 14,
    },
    {
      name: 'Shoulder Turn',
      value: 95,
      unit: 'deg',
      delta: 5,
      deltaGood: 'up' as const,
      idealRange: [90, 110] as [number, number],
      currentNum: 95,
    },
  ]
  const insights = [
    {
      id: '1',
      type: 'mechanic' as const,
      text: 'Hips slid 2.5 in toward target at impact',
      metric: 'Hip Sway',
      drill: 'Chair Drill',
      severity: 'bad' as const,
    },
    {
      id: '2',
      type: 'power' as const,
      text: 'Excellent shoulder turn generated +3mph club speed',
      metric: 'Shoulder Turn',
      drill: 'Maintain',
      severity: 'good' as const,
    },
  ]
  return (
    <div className="h-full flex flex-col p-6 space-y-6 overflow-y-auto">
      <AnimatePresence mode="wait">
        {status === 'waiting' ? (
          <motion.div
            key="waiting"
            initial={{
              opacity: 0,
            }}
            animate={{
              opacity: 1,
            }}
            exit={{
              opacity: 0,
            }}
            className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-[#242C27] rounded-[24px] bg-[#0A0D0B]/50"
          >
            <div className="w-16 h-16 rounded-full bg-[#121714] border border-[#242C27] flex items-center justify-center mb-6 relative">
              <div className="absolute inset-0 rounded-full border-2 border-garage-green animate-ping opacity-20" />
              <div className="w-3 h-3 rounded-full bg-garage-green shadow-glow-primary-sm animate-pulse" />
            </div>
            <h2 className="text-2xl font-semibold text-[#E7EEE9] mb-2">
              Waiting for your R50
            </h2>
            <p className="text-[#8B978F]">
              Step up and take a swing. Data will appear here automatically.
            </p>
          </motion.div>
        ) : (
          <motion.div
            key="captured"
            initial={{
              opacity: 0,
              y: 20,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            className="flex-1 flex flex-col space-y-6"
          >
            {/* Top Row: Hero Video + AI Insights */}
            <div className="flex flex-col lg:flex-row gap-6 h-[400px]">
              <div className="flex-[2] h-full">
                <SwingReplay highlight={true} />
              </div>
              <div className="flex-1 h-full">
                <AIInsightCard
                  headline="Good power, but sliding hips are causing inconsistency."
                  insights={insights}
                  highlight={true}
                />
              </div>
            </div>

            {/* Middle Row: Metrics Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              {metrics.map((m, i) => (
                <MetricCard
                  key={m.name}
                  {...m}
                  highlight={i === 1} // Highlight the problematic metric
                />
              ))}
            </div>

            {/* Bottom Row: Ball & Club Strip */}
            <div className="mt-auto pt-2">
              <BallClubStrip />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

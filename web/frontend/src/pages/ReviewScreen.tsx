import { useState } from 'react'
import { SwingReplay } from '../components/SwingReplay'
import { AIInsightCard } from '../components/AIInsightCard'
import { BallClubStrip } from '../components/BallClubStrip'
import { cn } from '../lib/utils'
import { CheckCircle2, AlertCircle } from 'lucide-react'
export function ReviewScreen() {
  const [activePhase, setActivePhase] = useState('Impact')
  const phases = [
    'Address',
    'Takeaway',
    'Lead-arm',
    'Top',
    'Transition',
    'Shaft par.',
    'Impact',
    'Follow-thru',
  ]
  const fullMetrics = [
    {
      name: 'Shoulder Tilt',
      address: '8°',
      top: '32°',
      impact: '38°',
      status: 'good',
    },
    {
      name: 'Hip Sway',
      address: '0"',
      top: '0.5"',
      impact: '2.5"',
      status: 'bad',
    },
    {
      name: 'Spine Angle',
      address: '45°',
      top: '43°',
      impact: '42°',
      status: 'neutral',
    },
    {
      name: 'Hand Depth',
      address: '4"',
      top: '14"',
      impact: '6"',
      status: 'good',
    },
  ]
  const reviewInsights = [
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
      type: 'timing' as const,
      text: 'Transition started slightly before top of backswing',
      metric: 'Kinematic Seq',
      drill: 'Pause at Top',
      severity: 'neutral' as const,
    },
    {
      id: '3',
      type: 'power' as const,
      text: 'Excellent shoulder turn generated +3mph club speed',
      metric: 'Shoulder Turn',
      drill: 'Maintain',
      severity: 'good' as const,
    },
  ]
  return (
    <div className="h-full flex flex-col p-6 space-y-6 overflow-y-auto">
      {/* HERO: Video Scrubber & Timeline */}
      <div className="bg-[#121714] border border-[#242C27] rounded-[24px] p-6 flex flex-col space-y-6">
        <div className="h-[360px] rounded-[18px] overflow-hidden">
          <SwingReplay />
        </div>

        {/* 8-Phase Timeline */}
        <div className="relative pt-4 pb-2 px-4">
          <div className="absolute top-6 left-8 right-8 h-0.5 bg-[#242C27]" />
          <div className="flex justify-between relative">
            {phases.map((phase) => {
              const isActive = activePhase === phase
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
                {fullMetrics.map((m) => (
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

        {/* AI Feedback Panel */}
        <div className="flex flex-col space-y-6">
          <AIInsightCard
            headline="Detailed Swing Analysis"
            insights={reviewInsights}
          />
        </div>
      </div>

      {/* Matched Shot Panel */}
      <div className="mt-auto">
        <h4 className="text-[11px] uppercase tracking-wider text-[#8B978F] font-semibold mb-3 ml-2">
          Matched R50 Data
        </h4>
        <BallClubStrip />
      </div>
    </div>
  )
}

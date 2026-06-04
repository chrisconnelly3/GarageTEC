import { Link, Unlink, Check, AlertCircle, Video, Activity } from 'lucide-react'
import { cn } from '../lib/utils'
const matches = [
  {
    id: 1,
    time: '2:34:12 PM',
    confidence: 98,
    status: 'matched',
    swing: {
      metrics: ['Hip Sway 2.1"', 'Tilt 38°'],
    },
    shot: {
      speed: '162mph',
      carry: '284y',
    },
  },
  {
    id: 2,
    time: '2:36:05 PM',
    confidence: 82,
    status: 'matched',
    swing: {
      metrics: ['Hip Sway 1.8"', 'Tilt 40°'],
    },
    shot: {
      speed: '158mph',
      carry: '275y',
    },
  },
  {
    id: 3,
    time: '2:39:40 PM',
    confidence: 45,
    status: 'review',
    swing: {
      metrics: ['Hip Sway 2.5"', 'Tilt 35°'],
    },
    shot: {
      speed: '165mph',
      carry: '290y',
    },
  },
  {
    id: 4,
    time: '2:41:10 PM',
    confidence: 0,
    status: 'unmatched_swing',
    swing: {
      metrics: ['Practice Swing'],
    },
    shot: null as { speed: string; carry: string } | null,
  },
]
export function SyncScreen() {
  return (
    <div className="h-full flex flex-col p-6 space-y-6 overflow-y-auto">
      <div className="flex flex-col space-y-2">
        <h1 className="text-2xl font-semibold text-[#E7EEE9]">Sync</h1>
        <p className="text-[#8B978F] flex items-center">
          Match camera swings to R50 launch data.{' '}
          <span className="text-[#E7EEE9] font-medium ml-2 bg-[#1A211D] px-2 py-0.5 rounded">
            12 auto-matched — 2 need review
          </span>
        </p>
      </div>

      <div className="flex flex-col space-y-4">
        {matches.map((match) => (
          <div
            key={match.id}
            className="bg-[#121714] border border-[#242C27] rounded-[24px] p-4 flex flex-col lg:flex-row items-center gap-4"
          >
            {/* Left: Camera Swing */}
            <div className="flex-1 w-full bg-[#1A211D] rounded-[18px] p-4 flex items-center space-x-4 border border-[#242C27]">
              <div className="w-16 h-12 bg-[#0A0D0B] rounded-lg flex items-center justify-center border border-[#242C27] relative overflow-hidden">
                <Video className="w-5 h-5 text-[#4A554E]" />
                <div className="absolute bottom-1 right-1 text-[9px] font-mono text-[#8B978F]">
                  {match.time}
                </div>
              </div>
              <div className="flex flex-col space-y-1.5">
                <span className="text-xs font-semibold uppercase tracking-wider text-[#8B978F]">
                  Camera Swing
                </span>
                <div className="flex gap-2">
                  {match.swing.metrics.map((m) => (
                    <span
                      key={m}
                      className="text-xs text-[#E7EEE9] bg-[#242C27] px-2 py-1 rounded-md"
                    >
                      {m}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Center: Connector */}
            <div className="flex flex-col items-center px-2 py-4 lg:py-0">
              {match.shot ? (
                <>
                  <div
                    className={cn(
                      'px-3 py-1.5 rounded-full text-xs font-bold flex items-center space-x-1.5',
                      match.confidence >= 75
                        ? 'bg-garage-green/10 text-garage-green'
                        : 'bg-garage-amber/10 text-garage-amber',
                    )}
                  >
                    <Link className="w-3.5 h-3.5" />
                    <span>{match.confidence}% Match</span>
                  </div>
                  <div className="w-px h-6 lg:w-6 lg:h-px bg-[#242C27] my-2 lg:my-0 lg:mx-2" />
                </>
              ) : (
                <div className="px-3 py-1.5 rounded-full text-xs font-bold bg-garage-red/10 text-garage-red flex items-center space-x-1.5">
                  <AlertCircle className="w-3.5 h-3.5" />
                  <span>No Match</span>
                </div>
              )}
            </div>

            {/* Right: R50 Shot */}
            <div
              className={cn(
                'flex-1 w-full rounded-[18px] p-4 flex items-center justify-between border border-[#242C27]',
                match.shot ? 'bg-[#1A211D]' : 'bg-[#0A0D0B] border-dashed',
              )}
            >
              {match.shot ? (
                <div className="flex items-center space-x-4">
                  <div className="w-12 h-12 bg-[#242C27] rounded-full flex items-center justify-center">
                    <Activity className="w-5 h-5 text-garage-green" />
                  </div>
                  <div className="flex flex-col space-y-1.5">
                    <span className="text-xs font-semibold uppercase tracking-wider text-[#8B978F]">
                      R50 Shot
                    </span>
                    <div className="flex gap-2">
                      <span className="text-xs font-mono text-[#E7EEE9] bg-[#242C27] px-2 py-1 rounded-md">
                        {match.shot.speed}
                      </span>
                      <span className="text-xs font-mono text-[#E7EEE9] bg-[#242C27] px-2 py-1 rounded-md">
                        {match.shot.carry}
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-[#8B978F] italic px-4">
                  Waiting for R50 data...
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center space-x-2 ml-4">
                {match.status === 'review' && (
                  <button
                    className="bg-garage-green text-[#0A0D0B] p-3 rounded-full hover:bg-garage-green-deep transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                    title="Confirm Match"
                  >
                    <Check className="w-5 h-5" />
                  </button>
                )}
                {match.shot && (
                  <button
                    className="bg-[#242C27] text-[#E7EEE9] p-3 rounded-full hover:bg-[#4A554E] transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                    title="Unlink"
                  >
                    <Unlink className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

import { useState } from 'react'
import { Play, Pause, SkipBack, SkipForward, Maximize2 } from 'lucide-react'
import { cn } from '../lib/utils'
interface SwingReplayProps {
  highlight?: boolean
}
export function SwingReplay({ highlight }: SwingReplayProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [speed, setSpeed] = useState<'realtime' | 'slowmo'>('realtime')
  const [progress] = useState(65)
  return (
    <div
      className={cn(
        'relative w-full h-full bg-[#0A0D0B] rounded-[18px] overflow-hidden border flex flex-col',
        highlight
          ? 'border-garage-green shadow-glow-primary'
          : 'border-[#242C27]',
      )}
    >
      {/* Video Area Placeholder */}
      <div className="flex-1 relative bg-gradient-to-b from-[#121714] to-[#0A0D0B] flex items-center justify-center">
        {/* Placeholder for Golfer + Skeleton */}
        <div className="absolute inset-0 opacity-20 bg-[url('https://cdn.magicpatterns.com/uploads/1i3Ysve75E55g6JKty6nz5/bb5596c1d539e28a0e476041bef4ab72.webp')] bg-cover bg-center mix-blend-luminosity" />

        {/* Abstract Skeleton Overlay */}
        <svg
          className="absolute inset-0 w-full h-full"
          viewBox="0 0 100 100"
          preserveAspectRatio="xMidYMid meet"
        >
          <g
            stroke="rgba(132, 206, 57, 0.6)"
            strokeWidth="0.5"
            fill="none"
            className="drop-shadow-[0_0_4px_rgba(132,206,57,0.8)]"
          >
            <line x1="50" y1="20" x2="50" y2="45" /> {/* Spine */}
            <line x1="40" y1="25" x2="60" y2="25" /> {/* Shoulders */}
            <line x1="45" y1="45" x2="55" y2="45" /> {/* Hips */}
            <line x1="40" y1="25" x2="35" y2="40" /> {/* Left Arm */}
            <line x1="60" y1="25" x2="45" y2="42" /> {/* Right Arm */}
            <line x1="35" y1="40" x2="40" y2="55" /> {/* Left Forearm */}
            <line x1="45" y1="42" x2="40" y2="55" /> {/* Right Forearm */}
            <circle cx="50" cy="15" r="4" fill="rgba(132, 206, 57, 0.2)" />{' '}
            {/* Head */}
            <circle cx="40" cy="55" r="1.5" fill="#79BC30" /> {/* Hands */}
            {/* Club */}
            <line
              x1="40"
              y1="55"
              x2="25"
              y2="85"
              stroke="white"
              strokeWidth="0.3"
              opacity="0.5"
            />
          </g>
        </svg>

        {/* Top Controls Overlay */}
        <div className="absolute top-4 right-4 flex space-x-2">
          <div className="bg-[#0A0D0B]/80 backdrop-blur rounded-full p-1 border border-[#242C27] flex">
            <button
              onClick={() => setSpeed('realtime')}
              className={cn(
                'px-3 py-1 rounded-full text-xs font-medium transition-colors',
                speed === 'realtime'
                  ? 'bg-[#242C27] text-[#E7EEE9]'
                  : 'text-[#8B978F] hover:text-[#E7EEE9]',
              )}
            >
              Realtime
            </button>
            <button
              onClick={() => setSpeed('slowmo')}
              className={cn(
                'px-3 py-1 rounded-full text-xs font-medium transition-colors',
                speed === 'slowmo'
                  ? 'bg-[#242C27] text-[#E7EEE9]'
                  : 'text-[#8B978F] hover:text-[#E7EEE9]',
              )}
            >
              Slow-mo
            </button>
          </div>
          <button className="bg-[#0A0D0B]/80 backdrop-blur rounded-full p-2 border border-[#242C27] text-[#8B978F] hover:text-[#E7EEE9] transition-colors">
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Scrubber & Controls */}
      <div className="h-16 bg-[#121714] border-t border-[#242C27] px-6 flex items-center space-x-4">
        <button
          onClick={() => setIsPlaying(!isPlaying)}
          className="w-10 h-10 rounded-full bg-garage-green text-[#0A0D0B] flex items-center justify-center hover:bg-garage-green-deep transition-colors flex-shrink-0"
        >
          {isPlaying ? (
            <Pause className="w-5 h-5 fill-current" />
          ) : (
            <Play className="w-5 h-5 fill-current ml-0.5" />
          )}
        </button>

        <div className="flex space-x-1 flex-shrink-0">
          <button className="p-2 text-[#8B978F] hover:text-[#E7EEE9] transition-colors">
            <SkipBack className="w-4 h-4" />
          </button>
          <button className="p-2 text-[#8B978F] hover:text-[#E7EEE9] transition-colors">
            <SkipForward className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 flex items-center space-x-3">
          <span className="text-xs font-mono text-[#8B978F]">0:02</span>
          <div className="flex-1 h-2 bg-[#1A211D] rounded-full relative cursor-pointer group">
            <div
              className="absolute top-0 left-0 h-full bg-garage-green rounded-full shadow-glow-primary-sm"
              style={{
                width: `${progress}%`,
              }}
            />
            <div
              className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full shadow opacity-0 group-hover:opacity-100 transition-opacity"
              style={{
                left: `calc(${progress}% - 8px)`,
              }}
            />
          </div>
          <span className="text-xs font-mono text-[#8B978F]">0:04</span>
        </div>
      </div>
    </div>
  )
}

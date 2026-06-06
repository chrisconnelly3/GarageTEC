import { useEffect, useRef, useState } from 'react'
import { Play, Pause, Maximize2 } from 'lucide-react'
import { cn } from '../lib/utils'

interface SwingReplayProps {
  src?: string | null            // annotated video URL; null -> placeholder
  highlight?: boolean
  seek?: { t: number } | null    // a fresh token each request, so repeat-seek to the same time re-fires
  onTime?: (t: number) => void   // playback time (seconds), for phase sync
}

export function SwingReplay({ src, highlight, seek, onTime }: SwingReplayProps) {
  const ref = useRef<HTMLVideoElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [speed, setSpeed] = useState<'realtime' | 'slowmo'>('realtime')
  const [progress, setProgress] = useState(0)

  // Controlled seek from the PhaseTimeline. `seek` is a new object reference each
  // request, so clicking the same phase twice still re-fires this effect.
  useEffect(() => {
    const v = ref.current
    if (v && seek && Number.isFinite(seek.t)) v.currentTime = seek.t
  }, [seek])

  useEffect(() => {
    const v = ref.current
    if (v) v.playbackRate = speed === 'slowmo' ? 0.25 : 1
  }, [speed])

  const toggle = () => {
    const v = ref.current
    if (!v) return
    if (v.paused) { v.play(); setIsPlaying(true) }
    else { v.pause(); setIsPlaying(false) }
  }

  const onTimeUpdate = () => {
    const v = ref.current
    if (!v) return
    onTime?.(v.currentTime)
    setProgress(v.duration ? (v.currentTime / v.duration) * 100 : 0)
  }

  return (
    <div className={cn(
      'relative w-full h-full bg-[#0A0D0B] rounded-[18px] overflow-hidden border flex flex-col',
      highlight ? 'border-garage-green shadow-glow-primary' : 'border-[#242C27]',
    )}>
      <div className="flex-1 relative bg-gradient-to-b from-[#121714] to-[#0A0D0B] flex items-center justify-center">
        {src ? (
          <video ref={ref} src={src} onTimeUpdate={onTimeUpdate}
            onEnded={() => setIsPlaying(false)} playsInline
            className="w-full h-full object-contain" />
        ) : (
          <div className="text-[#8B978F] text-sm">No swing video yet.</div>
        )}
        <div className="absolute top-4 right-4 flex space-x-2">
          <div className="bg-[#0A0D0B]/80 backdrop-blur rounded-full p-1 border border-[#242C27] flex">
            {(['realtime', 'slowmo'] as const).map((s) => (
              <button key={s} onClick={() => setSpeed(s)}
                className={cn('px-3 py-1 rounded-full text-xs font-medium transition-colors',
                  speed === s ? 'bg-[#242C27] text-[#E7EEE9]' : 'text-[#8B978F] hover:text-[#E7EEE9]')}>
                {s === 'realtime' ? 'Realtime' : 'Slow-mo'}
              </button>
            ))}
          </div>
          <button className="bg-[#0A0D0B]/80 backdrop-blur rounded-full p-2 border border-[#242C27] text-[#8B978F]">
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="h-16 bg-[#121714] border-t border-[#242C27] px-6 flex items-center space-x-4">
        <button onClick={toggle} disabled={!src}
          className="w-10 h-10 rounded-full bg-garage-green text-[#0A0D0B] flex items-center justify-center disabled:opacity-40 flex-shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#121714]">
          {isPlaying ? <Pause className="w-5 h-5 fill-current" /> : <Play className="w-5 h-5 fill-current ml-0.5" />}
        </button>
        <div className="flex-1 h-2 bg-[#1A211D] rounded-full relative">
          <div className="absolute top-0 left-0 h-full bg-garage-green rounded-full shadow-glow-primary-sm"
            style={{ width: `${progress}%` }} />
        </div>
      </div>
    </div>
  )
}

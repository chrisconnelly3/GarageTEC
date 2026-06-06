import { useEffect, useRef, useState } from 'react'
import { Play, Pause, Maximize2, PersonStanding } from 'lucide-react'
import { cn } from '../lib/utils'
import { PoseOverlay, type PoseData } from './PoseOverlay'

interface SwingReplayProps {
  src?: string | null            // annotated video URL; null -> placeholder
  poseSrc?: string | null        // per-frame pose JSON URL; enables the skeleton toggle
  highlight?: boolean
  seek?: { t: number } | null    // a fresh token each request, so repeat-seek to the same time re-fires
  impactTime?: number | null     // auto-seek here on load so the replay opens on impact
  onTime?: (t: number) => void   // playback time (seconds), for phase sync
  onDuration?: (d: number) => void // total duration (seconds), for the timeline scale
  fill?: boolean                 // Live: the player fills its parent column (no fixed aspect) and lets object-contain center the real frame
}

export function SwingReplay({ src, poseSrc, highlight, seek, impactTime, onTime, onDuration, fill }: SwingReplayProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const ref = useRef<HTMLVideoElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  // Default to slow-mo (0.25x) so the swing is studyable the moment it loads.
  const [speed, setSpeed] = useState<'slowmo' | 'realtime'>('slowmo')
  const [progress, setProgress] = useState(0)
  const [isFullscreen, setIsFullscreen] = useState(false)
  // Skeleton (exoskeleton) overlay — OFF by default.
  const [showSkeleton, setShowSkeleton] = useState(false)
  const [pose, setPose] = useState<PoseData | null>(null)

  // Lazy-load the pose JSON when a source is provided.
  useEffect(() => {
    if (!poseSrc) { setPose(null); return }
    let alive = true
    fetch(poseSrc)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (alive) setPose(d) })
      .catch(() => { if (alive) setPose(null) })
    return () => { alive = false }
  }, [poseSrc])

  // Controlled seek from the PhaseTimeline. `seek` is a new object reference each
  // request, so clicking the same phase twice still re-fires this effect.
  useEffect(() => {
    const v = ref.current
    if (v && seek && Number.isFinite(seek.t)) v.currentTime = seek.t
  }, [seek])

  // Auto-seek to the impact frame when the source or impact time changes, and
  // again once metadata is loaded (currentTime is only honored after that).
  useEffect(() => {
    const v = ref.current
    if (v && impactTime != null && Number.isFinite(impactTime) && v.readyState >= 1) {
      v.currentTime = impactTime
    }
  }, [impactTime, src])

  useEffect(() => {
    const v = ref.current
    if (v) v.playbackRate = speed === 'slowmo' ? 0.25 : 1
  }, [speed])

  useEffect(() => {
    const onFsChange = () => setIsFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', onFsChange)
    return () => document.removeEventListener('fullscreenchange', onFsChange)
  }, [])

  const onLoadedMetadata = () => {
    const v = ref.current
    if (!v) return
    // Re-assert the chosen rate (some browsers reset it when a new source loads).
    v.playbackRate = speed === 'slowmo' ? 0.25 : 1
    if (Number.isFinite(v.duration)) onDuration?.(v.duration)
    if (impactTime != null && Number.isFinite(impactTime)) {
      v.currentTime = impactTime
    }
  }

  const toggle = () => {
    const v = ref.current
    if (!v) return
    if (v.paused) { v.play(); setIsPlaying(true) }
    else { v.pause(); setIsPlaying(false) }
  }

  const toggleFullscreen = () => {
    if (document.fullscreenElement) {
      document.exitFullscreen?.()
    } else {
      containerRef.current?.requestFullscreen?.()
    }
  }

  const onTimeUpdate = () => {
    const v = ref.current
    if (!v) return
    onTime?.(v.currentTime)
    if (Number.isFinite(v.duration)) onDuration?.(v.duration)
    setProgress(v.duration ? (v.currentTime / v.duration) * 100 : 0)
  }

  return (
    <div ref={containerRef} className={cn(
      'relative w-full bg-[#0A0D0B] rounded-[18px] overflow-hidden border flex flex-col',
      fill && 'h-full',
      highlight ? 'border-garage-green shadow-glow-primary' : 'border-[#242C27]',
    )}>
      {/* fill: the area grows to fill the column and object-contain centers the
          real frame (portrait mock now, 32:9 composite in production) — no
          distortion. Otherwise a 32:9 width-driven box (two 16:9 cameras). */}
      <div className={cn(
        'relative bg-gradient-to-b from-[#121714] to-[#0A0D0B] flex items-center justify-center',
        fill ? 'flex-1 min-h-0' : 'aspect-[32/9]',
      )}>
        {src ? (
          <video ref={ref} src={src} onTimeUpdate={onTimeUpdate}
            onLoadedMetadata={onLoadedMetadata}
            onPlay={() => setIsPlaying(true)} onPause={() => setIsPlaying(false)}
            loop playsInline
            className="w-full h-full object-contain" />
        ) : (
          <div className="text-[#8B978F] text-sm">No swing video yet.</div>
        )}

        {/* Toggleable pose skeleton drawn over the video. */}
        {src && <PoseOverlay videoRef={ref} pose={pose} enabled={showSkeleton} />}

        {/* Large center play overlay when paused (hidden while playing). */}
        {src && !isPlaying && (
          <button onClick={toggle} aria-label="Play"
            className="absolute inset-0 z-20 flex items-center justify-center group focus-visible:outline-none">
            <span className="w-16 h-16 rounded-full bg-garage-green/90 text-[#0A0D0B] flex items-center justify-center shadow-glow-primary transition-transform group-hover:scale-105 group-focus-visible:ring-2 group-focus-visible:ring-garage-green">
              <Play className="w-8 h-8 fill-current ml-1" />
            </span>
          </button>
        )}

        <div className="absolute top-4 right-4 z-20 flex space-x-2">
          {pose && (
            <button onClick={() => setShowSkeleton((v) => !v)}
              aria-label="Toggle skeleton overlay" aria-pressed={showSkeleton}
              title={showSkeleton ? 'Hide skeleton' : 'Show skeleton'}
              className={cn(
                'flex items-center gap-1.5 backdrop-blur rounded-full px-3 py-1 border text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60',
                showSkeleton
                  ? 'bg-garage-green text-[#0A0D0B] border-garage-green'
                  : 'bg-[#0A0D0B]/80 text-[#8B978F] border-[#242C27] hover:text-[#E7EEE9]',
              )}>
              <PersonStanding className="w-4 h-4" />
              Skeleton
            </button>
          )}
          <div className="bg-[#0A0D0B]/80 backdrop-blur rounded-full p-1 border border-[#242C27] flex">
            {(['slowmo', 'realtime'] as const).map((s) => (
              <button key={s} onClick={() => setSpeed(s)}
                className={cn('px-3 py-1 rounded-full text-xs font-medium transition-colors',
                  speed === s ? 'bg-[#242C27] text-[#E7EEE9]' : 'text-[#8B978F] hover:text-[#E7EEE9]')}>
                {s === 'realtime' ? 'Realtime' : 'Slow-mo'}
              </button>
            ))}
          </div>
          <button onClick={toggleFullscreen}
            aria-label={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
            className="bg-[#0A0D0B]/80 backdrop-blur rounded-full p-2 border border-[#242C27] text-[#8B978F] hover:text-[#E7EEE9] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60">
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* In fill mode (Live), the LiveTimeline below is the single scrubber — we
          only show the play/pause button here (no redundant progress fill).
          In non-fill mode (Review), keep the full bar with progress fill. */}
      {fill ? (
        <div className="h-12 bg-[#121714] border-t border-[#242C27] px-4 flex items-center">
          <button onClick={toggle} disabled={!src} aria-label={isPlaying ? 'Pause' : 'Play'}
            className="w-9 h-9 rounded-full bg-garage-green text-[#0A0D0B] flex items-center justify-center disabled:opacity-40 flex-shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#121714]">
            {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current ml-0.5" />}
          </button>
        </div>
      ) : (
        <div className="h-12 bg-[#121714] border-t border-[#242C27] px-4 flex items-center space-x-4">
          <button onClick={toggle} disabled={!src} aria-label={isPlaying ? 'Pause' : 'Play'}
            className="w-9 h-9 rounded-full bg-garage-green text-[#0A0D0B] flex items-center justify-center disabled:opacity-40 flex-shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#121714]">
            {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current ml-0.5" />}
          </button>
          <div className="flex-1 h-2 bg-[#1A211D] rounded-full relative">
            <div className="absolute top-0 left-0 h-full bg-garage-green rounded-full shadow-glow-primary-sm"
              style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}
    </div>
  )
}

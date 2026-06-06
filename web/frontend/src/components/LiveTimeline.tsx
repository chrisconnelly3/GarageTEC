import { cn } from '../lib/utils'
import type { Moment } from '../lib/types'
import { momentKindToLabel } from '../lib/phase'

interface LiveTimelineProps {
  moments: Moment[]            // swing phases; each marker sits at time_s / duration
  duration: number             // total video length (s); markers/playhead are fractions of this
  currentTime: number          // playhead position (s)
  activeLabel: string          // current phase label (e.g. "Impact") — its marker is highlighted
  onSeek: (time: number, label: string) => void  // tap a marker / scrub the track
}

// A single time-accurate scrubber for Live: the playhead and the swing's phase
// markers share ONE track, so they line up with the video (unlike the old
// evenly-spaced PhaseTimeline). Markers sit at their real time_s/duration.
export function LiveTimeline({ moments, duration, currentTime, activeLabel, onSeek }: LiveTimelineProps) {
  const safeDur = duration > 0 ? duration : 0
  const pct = (t: number) => (safeDur > 0 ? Math.min(100, Math.max(0, (t / safeDur) * 100)) : 0)

  // Only markers with a real timestamp can be positioned; sort by time.
  const markers = moments
    .filter((m) => m.time_s != null && Number.isFinite(m.time_s as number))
    .map((m) => ({ time: m.time_s as number, label: momentKindToLabel(m.kind) }))
    .sort((a, b) => a.time - b.time)

  const onTrackClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (safeDur <= 0) return
    const rect = e.currentTarget.getBoundingClientRect()
    const frac = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
    const t = frac * safeDur
    // Snap the active phase label to the latest marker at/under this time.
    let label = markers[0]?.label ?? activeLabel
    for (const m of markers) if (m.time <= t) label = m.label
    onSeek(t, label)
  }

  return (
    <div className="px-4 pt-3 pb-2 select-none" data-testid="live-timeline">
      {/* Clickable track. The playhead and phase markers share this one bar. */}
      <div className="relative h-9">
        <button
          type="button"
          onClick={onTrackClick as unknown as React.MouseEventHandler<HTMLButtonElement>}
          aria-label="Scrub timeline"
          className="absolute inset-x-0 top-3 h-2 rounded-full bg-[#1A211D] cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60"
        >
          {/* Played portion up to the playhead. */}
          <span className="absolute left-0 top-0 h-full rounded-full bg-garage-green/70"
            style={{ width: `${pct(currentTime)}%` }} />
        </button>

        {/* Playhead — reflects currentTime / duration. */}
        <div className="absolute top-0 -translate-x-1/2 pointer-events-none"
          style={{ left: `${pct(currentTime)}%` }} data-testid="live-playhead">
          <div className="w-0.5 h-8 bg-garage-green shadow-glow-primary-sm" />
        </div>

        {/* Phase markers at their real time_s / duration. */}
        {markers.map((m) => {
          const isActive = m.label === activeLabel
          return (
            <button
              key={m.label + m.time}
              type="button"
              onClick={() => onSeek(m.time, m.label)}
              data-testid={`marker-${m.label}`}
              data-pct={pct(m.time).toFixed(2)}
              style={{ left: `${pct(m.time)}%` }}
              className="absolute top-2 -translate-x-1/2 flex flex-col items-center group focus-visible:outline-none"
            >
              <span className={cn(
                'rounded-full border-2 z-10 transition-all',
                isActive
                  ? 'w-4 h-4 bg-garage-green border-garage-green shadow-glow-primary-sm scale-110'
                  : 'w-3 h-3 bg-[#121714] border-garage-green/60 group-hover:border-garage-green',
              )} />
            </button>
          )
        })}
      </div>

      {/* Labels row, positioned under their markers. */}
      <div className="relative h-4 mt-0.5">
        {markers.map((m) => {
          const isActive = m.label === activeLabel
          return (
            <button
              key={m.label + m.time}
              type="button"
              onClick={() => onSeek(m.time, m.label)}
              style={{ left: `${pct(m.time)}%` }}
              tabIndex={-1}
              className="absolute -translate-x-1/2 focus-visible:outline-none"
            >
              <span className={cn(
                'text-[9px] uppercase tracking-wider font-medium whitespace-nowrap transition-colors',
                isActive ? 'text-garage-green' : 'text-[#8B978F] group-hover:text-[#E7EEE9]',
              )}>{m.label}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

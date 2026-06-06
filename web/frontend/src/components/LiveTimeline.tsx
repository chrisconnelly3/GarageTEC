import { cn } from '../lib/utils'
import type { Moment } from '../lib/types'
import { momentKindToLabel } from '../lib/phase'

interface LiveTimelineProps {
  moments: Moment[]            // swing phases; rendered EQUALLY spaced across the track
  duration: number             // total video length (s) — kept for API compatibility
  currentTime: number          // playhead position (s)
  activeLabel: string          // current phase label (e.g. "Impact") — its marker is highlighted
  onSeek: (time: number, label: string) => void  // tap a marker / scrub the track
}

// The position stepper: the eight swing positions are spaced EVENLY across the
// track (so none bunch up), and the playhead moves at VARIABLE speed — it
// interpolates between adjacent markers by real time, so it races through the
// quick parts of the swing (transition → impact) and crawls through the slow
// parts. Visual position is decoupled from real time on purpose.
export function LiveTimeline({ moments, currentTime, activeLabel, onSeek }: LiveTimelineProps) {
  // Only markers with a real timestamp can anchor the playhead; sort by time.
  const markers = moments
    .filter((m) => m.time_s != null && Number.isFinite(m.time_s as number))
    .map((m) => ({ time: m.time_s as number, label: momentKindToLabel(m.kind) }))
    .sort((a, b) => a.time - b.time)

  const n = markers.length
  // Even horizontal spacing: marker i sits at i/(n-1) of the track width.
  const vx = (i: number) => (n > 1 ? (i / (n - 1)) * 100 : 0)

  // Playhead visual position (%): piecewise-linear in real time between the
  // evenly-spaced markers. Clamps to the ends outside the swing window.
  const playheadPct = (() => {
    if (n === 0) return 0
    if (currentTime <= markers[0].time) return 0
    if (currentTime >= markers[n - 1].time) return 100
    for (let i = 0; i < n - 1; i++) {
      const a = markers[i].time
      const b = markers[i + 1].time
      if (currentTime >= a && currentTime < b) {
        const frac = b > a ? (currentTime - a) / (b - a) : 0
        return ((i + frac) / (n - 1)) * 100
      }
    }
    return 100
  })()

  const onTrackClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (n === 0) return
    const rect = e.currentTarget.getBoundingClientRect()
    const fx = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
    if (n === 1) { onSeek(markers[0].time, markers[0].label); return }
    const scaled = fx * (n - 1)              // which evenly-spaced segment
    const seg = Math.min(n - 2, Math.floor(scaled))
    const local = scaled - seg
    const t = markers[seg].time + local * (markers[seg + 1].time - markers[seg].time)
    const label = markers[Math.min(n - 1, Math.round(scaled))].label
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
            style={{ width: `${playheadPct}%` }} />
        </button>

        {/* Playhead — variable-speed, decoupled from even marker spacing. */}
        <div className="absolute top-0 -translate-x-1/2 pointer-events-none"
          style={{ left: `${playheadPct}%` }} data-testid="live-playhead">
          <div className="w-0.5 h-8 bg-garage-green shadow-glow-primary-sm" />
        </div>

        {/* Evenly-spaced phase markers. */}
        {markers.map((m, i) => {
          const isActive = m.label === activeLabel
          return (
            <button
              key={m.label + m.time}
              type="button"
              onClick={() => onSeek(m.time, m.label)}
              data-testid={`marker-${m.label}`}
              data-pct={vx(i).toFixed(2)}
              style={{ left: `${vx(i)}%` }}
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

      {/* Labels row, evenly spaced under their markers. */}
      <div className="relative h-4 mt-0.5">
        {markers.map((m, i) => {
          const isActive = m.label === activeLabel
          return (
            <button
              key={m.label + m.time}
              type="button"
              onClick={() => onSeek(m.time, m.label)}
              style={{ left: `${vx(i)}%` }}
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

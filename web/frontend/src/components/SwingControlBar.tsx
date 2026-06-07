import { cn } from '../lib/utils'
import type { SwingSummary } from '../lib/types'

export type R50State = 'connected' | 'waiting' | 'paused' | 'error'

interface SwingControlBarProps {
  following: boolean          // true = following latest (selectedSwingId === null)
  newCount: number            // swings newer than the pinned one (0 when following)
  r50: R50State
  label: string               // dropdown display for the current swing
  swings: SwingSummary[]      // newest-first
  currentSwingId: number | null
  canPrev: boolean            // an older swing exists
  canNext: boolean            // can step newer / go live (true only when pinned)
  onGoLive: () => void
  onPrev: () => void
  onNext: () => void
  onPickSwing: (id: number) => void
}

const fmtOption = (s: SwingSummary, i: number) =>
  `#${s.id} · ${s.club ?? '—'} · ${new Date(s.created_at).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}`
  + (s.has_shot ? ' · R50' : '') + (i === 0 ? ' (latest)' : '')

export function SwingControlBar({
  following, newCount, r50, label, swings, currentSwingId,
  canPrev, canNext, onGoLive, onPrev, onNext, onPickSwing,
}: SwingControlBarProps) {
  // Pill appearance encodes BOTH live/pinned and R50 health.
  const pillClass = following
    ? (r50 === 'waiting'
        ? 'bg-[#E8B931] text-[#0A0D0B] border-[#E8B931]'
        : r50 === 'error' || r50 === 'paused'
          ? 'bg-transparent text-[#5b6b5f] border-[#3a443d]'
          : 'bg-garage-green text-[#0A0D0B] border-garage-green')
    : 'bg-transparent text-garage-green border-garage-green'

  return (
    <div className="flex items-center gap-2 rounded-[14px] border border-[#242C27] bg-[#0d110f] px-2 py-1.5"
         data-testid="swing-control-bar">
      <button
        type="button"
        data-testid="live-pill"
        onClick={() => { if (!following) onGoLive() }}
        aria-label={following ? 'Live (following latest)' : 'Go live'}
        className={cn(
          'relative inline-flex items-center gap-1.5 rounded-full border px-3 min-h-[40px] text-xs font-bold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60',
          pillClass,
        )}
      >
        <span className="w-2 h-2 rounded-full bg-current opacity-80" />
        LIVE
        {!following && newCount > 0 && (
          <span data-testid="new-count"
            className="absolute -top-1.5 -right-2 rounded-full border border-garage-green bg-[#0A0D0B] px-1.5 text-[10px] font-extrabold text-garage-green">
            {newCount}
          </span>
        )}
      </button>

      <button type="button" aria-label="Older swing" disabled={!canPrev} onClick={onPrev}
        className="flex items-center justify-center w-10 min-h-[40px] rounded-lg border border-[#242C27] bg-[#121714] text-[#E7EEE9] disabled:opacity-35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60">‹</button>

      <select
        data-testid="swing-select"
        value={currentSwingId ?? ''}
        onChange={(e) => onPickSwing(Number(e.target.value))}
        aria-label="Select swing"
        className="flex-1 min-h-[40px] rounded-lg border border-[#242C27] bg-[#121714] px-3 text-sm text-[#E7EEE9] outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60"
      >
        {currentSwingId == null && <option value="">{label}</option>}
        {swings.map((s, i) => (
          <option key={s.id} value={s.id}>
            {following && i === 0 ? label : fmtOption(s, i)}
          </option>
        ))}
      </select>

      <button type="button" aria-label="Newer swing" disabled={!canNext} onClick={onNext}
        className="flex items-center justify-center w-10 min-h-[40px] rounded-lg border border-[#242C27] bg-[#121714] text-[#E7EEE9] disabled:opacity-35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60">›</button>
    </div>
  )
}

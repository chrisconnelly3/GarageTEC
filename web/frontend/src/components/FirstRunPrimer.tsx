import { X } from 'lucide-react'

interface FirstRunPrimerProps {
  onDismiss: () => void
}

export function FirstRunPrimer({ onDismiss }: FirstRunPrimerProps) {
  return (
    <div
      className="relative bg-[#121714] border border-[#242C27] rounded-[18px] px-5 py-4 flex items-start gap-4"
      data-testid="first-run-primer"
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-[#E7EEE9] mb-2">Reading your swing</p>
        <ul className="space-y-1.5">
          <li className="flex items-start gap-2 text-sm text-[#8B978F]">
            <span className="flex items-center gap-1 shrink-0 mt-0.5" aria-hidden>
              <span className="w-2.5 h-2.5 rounded-full bg-[#79BC30] inline-block" />
              <span className="w-2.5 h-2.5 rounded-full bg-[#E8B931] inline-block" />
              <span className="w-2.5 h-2.5 rounded-full bg-garage-red inline-block" />
            </span>
            Each card compares you to a Tour pro. Green is dialed in, yellow is close, red needs work.
          </li>
          <li className="flex items-start gap-2 text-sm text-[#8B978F]">
            <span className="w-2.5 h-2.5 rounded-full bg-[#242C27] border border-[#8B978F] inline-block shrink-0 mt-1" aria-hidden />
            Tap Address, Top, or Impact under the video to see that point in your swing.
          </li>
          <li className="flex items-start gap-2 text-sm text-[#8B978F]">
            <span className="w-2.5 h-2.5 rounded-full bg-[#242C27] border border-[#8B978F] inline-block shrink-0 mt-1" aria-hidden />
            "Needs 3D" unlocks once you calibrate the bay cameras (Connect screen).
          </li>
        </ul>
      </div>
      <button
        onClick={onDismiss}
        aria-label="Dismiss"
        className="shrink-0 text-[#8B978F] hover:text-[#E7EEE9] transition-colors p-1 rounded-full hover:bg-[#242C27] min-w-[36px] min-h-[36px] flex items-center justify-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}

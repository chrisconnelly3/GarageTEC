import { cn } from '../lib/utils'

export const PHASE_LABELS = [
  'Address', 'Takeaway', 'Lead-arm', 'Top',
  'Transition', 'Shaft par.', 'Impact', 'Follow-thru',
] as const

interface PhaseTimelineProps {
  present: Set<string>          // labels that have a moment (clickable)
  active: string                // currently active label
  onSeek: (label: string) => void
}

export function PhaseTimeline({ present, active, onSeek }: PhaseTimelineProps) {
  return (
    <div className="relative pt-4 pb-2 px-4">
      <div className="absolute top-6 left-8 right-8 h-0.5 bg-[#242C27]" />
      <div className="flex justify-between relative">
        {PHASE_LABELS.map((phase) => {
          const isActive = active === phase
          const exists = present.has(phase)
          return (
            <button
              key={phase}
              onClick={() => exists && onSeek(phase)}
              disabled={!exists}
              className="flex flex-col items-center space-y-3 group disabled:cursor-default"
            >
              <div className={cn(
                'w-4 h-4 rounded-full border-2 z-10 transition-all',
                isActive ? 'bg-garage-green border-garage-green shadow-glow-primary-sm scale-125'
                  : exists ? 'bg-[#121714] border-garage-green/60 group-hover:border-garage-green'
                    : 'bg-[#121714] border-[#4A554E]',
              )} />
              <span className={cn(
                'text-[10px] uppercase tracking-wider font-medium transition-colors',
                isActive ? 'text-garage-green' : exists ? 'text-[#8B978F] group-hover:text-[#E7EEE9]' : 'text-[#4A554E]',
              )}>{phase}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

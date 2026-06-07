import { Square, Play } from 'lucide-react'
import { cn } from '../lib/utils'
import { ClubSelector } from './ClubSelector'

interface TopbarPlayer { id: number; name: string }
interface TopbarProps {
  players: TopbarPlayer[]
  activePlayerId: number | null
  sessionActive: boolean
  sessionError: string | null
  r50Status: 'connected' | 'waiting' | 'paused' | 'error'
  activeClub: string | null
  onSelectClub: (club: string | null) => void
  onStartSession: () => void
  onEndSession: () => void
  onSelectPlayer: (p: TopbarPlayer) => void
}

// Shared control-shell styling so Who's-hitting + Club read as one row.
const SELECT_CLASS =
  'bg-[#1A211D] border border-[#242C27] rounded-xl px-4 py-2 text-[#E7EEE9] outline-none min-h-[44px] focus-visible:ring-2 focus-visible:ring-garage-green/60 focus-visible:border-garage-green'

export function Topbar({
  players,
  activePlayerId,
  sessionActive,
  sessionError,
  r50Status,
  activeClub,
  onSelectClub,
  onStartSession,
  onEndSession,
  onSelectPlayer,
}: TopbarProps) {
  const noPlayer = activePlayerId == null
  return (
    <header className="h-20 border-b border-[#242C27] bg-[#0A0D0B]/80 backdrop-blur-md flex items-center justify-between px-6 sticky top-0 z-10 gap-4">
      {/* The GarageTEC logo is rendered at the app-shell level (App.tsx) so it can
          sit dead-center of the viewport without the header's backdrop-filter
          turning it into the fixed-positioning containing block. */}
      <div className="flex items-center gap-4 min-w-0">
        <div className="flex items-center gap-2">
          <label className="text-[11px] uppercase tracking-widest text-[#8B978F] font-semibold">
            Who's Hitting
          </label>
          <select
            aria-label="Who's hitting"
            value={activePlayerId ?? ''}
            onChange={(e) => {
              const id = Number(e.target.value)
              const p = players.find((x) => x.id === id)
              if (p) onSelectPlayer(p)
            }}
            className={SELECT_CLASS}
          >
            {activePlayerId == null && <option value="">Select player…</option>}
            {players.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>

        <ClubSelector value={activeClub} onChange={onSelectClub} />
      </div>

      <div className="flex items-center gap-4 flex-shrink-0">
        {sessionError && (
          <span className="text-xs text-garage-red font-medium">{sessionError}</span>
        )}

        <button
          onClick={() => (sessionActive ? onEndSession() : onStartSession())}
          disabled={!sessionActive && noPlayer}
          title={!sessionActive && noPlayer ? 'Select a player first' : undefined}
          className={cn(
            'flex items-center space-x-2 px-6 py-2.5 rounded-full font-medium transition-all min-h-[44px] disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60',
            sessionActive
              ? 'bg-[#1A211D] text-[#E7EEE9] border border-[#242C27]'
              : 'bg-garage-green text-[#0A0D0B] shadow-glow-primary-sm hover:bg-garage-green-deep',
          )}
        >
          <span className={cn('w-2.5 h-2.5 rounded-full',
            r50Status === 'connected' ? 'bg-garage-green'
              : r50Status === 'waiting' ? 'bg-garage-amber'
                : r50Status === 'paused' ? 'bg-[#8B978F]' : 'bg-garage-red')}
            title={`R50: ${r50Status}`} />
          {sessionActive ? (
            <>
              <Square className="w-4 h-4 fill-current" />
              <span>End Session</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-current" />
              <span>Start Session</span>
            </>
          )}
        </button>
      </div>
    </header>
  )
}

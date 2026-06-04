import { useState } from 'react'
import { Plus, User } from 'lucide-react'
import { cn } from '../lib/utils'
import { Avatar, AvatarFallback } from '../components/Avatar'
import { useApi } from '../lib/useApi'
import { getPlayers, getSessions, createPlayer } from '../lib/api'
import { heightToFtIn } from '../lib/format'
import type { Player, Handedness } from '../lib/types'

interface PlayerVM extends Player {
  isActive: boolean
  sessions: number
  lastActive: string
}

const formatDate = (iso: string) => {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? '--'
    : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

interface PlayersScreenProps {
  activePlayerId: number | null
  onSetActive: (p: Player) => void
  onAdded: () => void
}

export function PlayersScreen({ activePlayerId, onSetActive, onAdded }: PlayersScreenProps) {
  const [showAdd, setShowAdd] = useState(false)
  const [name, setName] = useState('')
  const [ft, setFt] = useState('')
  const [inch, setInch] = useState('')
  const [hand, setHand] = useState<Handedness>('R')
  const [formError, setFormError] = useState<string | null>(null)

  const { data, loading, error, reload } = useApi<PlayerVM[]>(async () => {
    const players = await getPlayers()
    const sessionLists = await Promise.all(
      players.map((p) => getSessions(p.id).catch(() => [])),
    )
    return players.map((p, i) => {
      const sessions = sessionLists[i]
      return {
        ...p,
        isActive: p.id === activePlayerId,
        sessions: sessions.length,
        lastActive: sessions[0] ? formatDate(sessions[0].started_at) : '--',
      }
    })
  }, [activePlayerId])

  const resetForm = () => {
    setName(''); setFt(''); setInch(''); setHand('R'); setFormError(null)
  }

  const save = () => {
    if (!name.trim()) { setFormError('Name is required.'); return }
    const height_in = (parseInt(ft || '0', 10) || 0) * 12 + (parseInt(inch || '0', 10) || 0)
    createPlayer({ name: name.trim(), height_in, handedness: hand })
      .then(() => { resetForm(); setShowAdd(false); reload(); onAdded() })
      .catch((e) => setFormError(String(e)))
  }

  return (
    <div className="h-full flex flex-col p-6 space-y-6 overflow-y-auto relative">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-[#E7EEE9]">Players</h1>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="bg-garage-green text-[#0A0D0B] px-6 py-2.5 rounded-full text-sm font-medium hover:bg-garage-green-deep shadow-glow-primary-sm transition-all min-h-[44px] flex items-center"
        >
          <Plus className="w-4 h-4 mr-2" />
          Add Player
        </button>
      </div>

      {loading && <div className="text-[#8B978F]">Loading…</div>}
      {error && (
        <div className="rounded-[18px] border border-garage-red/40 bg-garage-red/10 px-6 py-4 text-sm text-garage-red">
          Failed to load players: {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {/* Add Player Card (Inline) */}
        {showAdd && (
          <div className="bg-[#121714] border border-garage-green shadow-glow-primary-sm rounded-[24px] p-6 flex flex-col space-y-5 animate-in fade-in zoom-in-95 duration-200">
            <h3 className="text-lg font-semibold text-[#E7EEE9]">New Player</h3>

            <div className="space-y-4">
              <div>
                <label className="text-xs uppercase tracking-wider text-[#8B978F] font-semibold mb-2 block">
                  Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Enter name"
                  className="w-full bg-[#1A211D] border border-[#242C27] rounded-xl px-4 py-3 text-[#E7EEE9] focus:border-garage-green focus:ring-1 focus:ring-garage-green outline-none transition-all min-h-[44px]"
                />
              </div>

              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="text-xs uppercase tracking-wider text-[#8B978F] font-semibold mb-2 block">
                    Height
                  </label>
                  <div className="flex space-x-2">
                    <input
                      type="number"
                      value={ft}
                      onChange={(e) => setFt(e.target.value)}
                      placeholder="Ft"
                      className="w-full bg-[#1A211D] border border-[#242C27] rounded-xl px-4 py-3 text-[#E7EEE9] focus:border-garage-green outline-none min-h-[44px]"
                    />
                    <input
                      type="number"
                      value={inch}
                      onChange={(e) => setInch(e.target.value)}
                      placeholder="In"
                      className="w-full bg-[#1A211D] border border-[#242C27] rounded-xl px-4 py-3 text-[#E7EEE9] focus:border-garage-green outline-none min-h-[44px]"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider text-[#8B978F] font-semibold mb-2 block">
                    Hand
                  </label>
                  <div className="flex bg-[#1A211D] border border-[#242C27] rounded-xl p-1 min-h-[44px]">
                    <button
                      onClick={() => setHand('R')}
                      className={cn(
                        'px-4 py-1 rounded-lg font-medium',
                        hand === 'R'
                          ? 'bg-[#242C27] text-[#E7EEE9]'
                          : 'text-[#8B978F] hover:text-[#E7EEE9]',
                      )}
                    >
                      R
                    </button>
                    <button
                      onClick={() => setHand('L')}
                      className={cn(
                        'px-4 py-1 rounded-lg font-medium',
                        hand === 'L'
                          ? 'bg-[#242C27] text-[#E7EEE9]'
                          : 'text-[#8B978F] hover:text-[#E7EEE9]',
                      )}
                    >
                      L
                    </button>
                  </div>
                </div>
              </div>
              {formError && (
                <p className="text-xs text-garage-red">{formError}</p>
              )}
            </div>

            <div className="flex space-x-3 mt-auto pt-4">
              <button
                onClick={() => { setShowAdd(false); resetForm() }}
                className="flex-1 bg-[#1A211D] text-[#E7EEE9] py-3 rounded-xl font-medium hover:bg-[#242C27] transition-colors min-h-[44px]"
              >
                Cancel
              </button>
              <button
                onClick={save}
                className="flex-1 bg-garage-green text-[#0A0D0B] py-3 rounded-xl font-medium hover:bg-garage-green-deep transition-colors min-h-[44px]"
              >
                Save
              </button>
            </div>
          </div>
        )}

        {/* Player Cards */}
        {(data ?? []).map((player) => (
          <div
            key={player.id}
            className={cn(
              'bg-[#121714] border rounded-[24px] p-6 flex flex-col relative overflow-hidden transition-all hover:border-[#4A554E]',
              player.isActive ? 'border-garage-green' : 'border-[#242C27]',
            )}
          >
            {player.isActive && (
              <div className="absolute top-0 left-0 w-full h-1 bg-garage-green shadow-glow-primary" />
            )}

            <div className="flex justify-between items-start mb-6">
              <Avatar
                className={cn(
                  'w-16 h-16',
                  player.isActive &&
                    'ring-2 ring-garage-green ring-offset-4 ring-offset-[#121714]',
                )}
              >
                <AvatarFallback className="bg-[#1A211D] text-xl">
                  <User className="w-8 h-8 text-[#8B978F]" />
                </AvatarFallback>
              </Avatar>

              {player.isActive && (
                <div className="bg-garage-green/10 text-garage-green px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider flex items-center">
                  <div className="w-1.5 h-1.5 rounded-full bg-garage-green mr-2 animate-pulse" />
                  Active
                </div>
              )}
            </div>

            <h3 className="text-xl font-semibold text-[#E7EEE9] mb-1">
              {player.name}
            </h3>
            <div className="flex items-center space-x-2 text-sm text-[#8B978F] mb-6">
              <span>{heightToFtIn(player.height_in)}</span>
              <span>•</span>
              <span>{player.handedness}H</span>
            </div>

            <div className="grid grid-cols-2 gap-4 mt-auto pt-4 border-t border-[#242C27]">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-[#8B978F] font-semibold mb-1">
                  Sessions
                </div>
                <div className="text-lg font-mono text-[#E7EEE9]">
                  {player.sessions}
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-[#8B978F] font-semibold mb-1">
                  Last Active
                </div>
                <div className="text-sm font-medium text-[#E7EEE9] mt-1">
                  {player.lastActive}
                </div>
              </div>
            </div>

            {!player.isActive && (
              <button
                onClick={() => onSetActive(player)}
                className="w-full mt-6 bg-[#1A211D] text-[#E7EEE9] py-3 rounded-xl font-medium hover:bg-[#242C27] transition-colors min-h-[44px]"
              >
                Set as Active
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

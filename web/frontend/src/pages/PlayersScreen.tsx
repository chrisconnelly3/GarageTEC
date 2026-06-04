import { useState } from 'react'
import { Plus, User } from 'lucide-react'
import { cn } from '../lib/utils'
import { Avatar, AvatarFallback, AvatarImage } from '../components/Avatar'
const players = [
  {
    id: '1',
    name: 'Alex M.',
    avatar: 'https://i.pravatar.cc/150?u=alex',
    height: '6\' 1"',
    handedness: 'R',
    swings: 1240,
    sessions: 24,
    lastActive: 'Right now',
    isActive: true,
  },
  {
    id: '2',
    name: 'Sarah T.',
    avatar: 'https://i.pravatar.cc/150?u=sarah',
    height: '5\' 6"',
    handedness: 'R',
    swings: 450,
    sessions: 8,
    lastActive: '3 days ago',
    isActive: false,
  },
  {
    id: '3',
    name: 'Guest',
    avatar: '',
    height: '--',
    handedness: 'R',
    swings: 12,
    sessions: 1,
    lastActive: '2 weeks ago',
    isActive: false,
  },
]
export function PlayersScreen() {
  const [showAdd, setShowAdd] = useState(false)
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
                      placeholder="Ft"
                      className="w-full bg-[#1A211D] border border-[#242C27] rounded-xl px-4 py-3 text-[#E7EEE9] focus:border-garage-green outline-none min-h-[44px]"
                    />
                    <input
                      type="number"
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
                    <button className="px-4 py-1 rounded-lg bg-[#242C27] text-[#E7EEE9] font-medium">
                      R
                    </button>
                    <button className="px-4 py-1 rounded-lg text-[#8B978F] hover:text-[#E7EEE9] font-medium">
                      L
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex space-x-3 mt-auto pt-4">
              <button
                onClick={() => setShowAdd(false)}
                className="flex-1 bg-[#1A211D] text-[#E7EEE9] py-3 rounded-xl font-medium hover:bg-[#242C27] transition-colors min-h-[44px]"
              >
                Cancel
              </button>
              <button className="flex-1 bg-garage-green text-[#0A0D0B] py-3 rounded-xl font-medium hover:bg-garage-green-deep transition-colors min-h-[44px]">
                Save
              </button>
            </div>
          </div>
        )}

        {/* Player Cards */}
        {players.map((player) => (
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
                <AvatarImage src={player.avatar} />
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
              <span>{player.height}</span>
              <span>•</span>
              <span>{player.handedness}H</span>
            </div>

            <div className="grid grid-cols-2 gap-4 mt-auto pt-4 border-t border-[#242C27]">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-[#8B978F] font-semibold mb-1">
                  Total Swings
                </div>
                <div className="text-lg font-mono text-[#E7EEE9]">
                  {player.swings.toLocaleString()}
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
              <button className="w-full mt-6 bg-[#1A211D] text-[#E7EEE9] py-3 rounded-xl font-medium hover:bg-[#242C27] transition-colors min-h-[44px]">
                Set as Active
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

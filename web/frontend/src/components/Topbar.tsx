import { Pause, Play, Wifi } from 'lucide-react'
import { cn } from '../lib/utils'
import { Avatar, AvatarFallback, AvatarImage } from './Avatar'
interface TopbarProps {
  isPaused: boolean
  setIsPaused: (paused: boolean) => void
  r50Status: 'connected' | 'waiting' | 'paused'
}
export function Topbar({ isPaused, setIsPaused, r50Status }: TopbarProps) {
  const players = [
    {
      id: '1',
      name: 'Alex M.',
      avatar: 'https://i.pravatar.cc/150?u=alex',
      active: true,
    },
    {
      id: '2',
      name: 'Sarah T.',
      avatar: 'https://i.pravatar.cc/150?u=sarah',
      active: false,
    },
    {
      id: '3',
      name: 'Guest',
      avatar: '',
      active: false,
    },
  ]
  return (
    <header className="h-20 border-b border-[#242C27] bg-[#0A0D0B]/80 backdrop-blur-md flex items-center justify-between px-8 sticky top-0 z-10">
      <div className="flex items-center space-x-4">
        <span className="text-[11px] uppercase tracking-widest text-[#8B978F] font-semibold mr-2">
          Who's Hitting
        </span>
        <div className="flex items-center space-x-2">
          {players.map((player) => (
            <button
              key={player.id}
              className={cn(
                'flex items-center space-x-2 px-1.5 py-1.5 pr-4 rounded-full transition-all min-h-[44px]',
                player.active
                  ? 'bg-[#1A211D] ring-1 ring-garage-green'
                  : 'hover:bg-[#1A211D]',
              )}
            >
              <Avatar
                className={cn(
                  'w-8 h-8',
                  player.active &&
                    'ring-2 ring-garage-green ring-offset-2 ring-offset-[#1A211D]',
                )}
              >
                <AvatarImage src={player.avatar} />
                <AvatarFallback className="bg-[#242C27] text-xs">
                  {player.name.charAt(0)}
                </AvatarFallback>
              </Avatar>
              <span
                className={cn(
                  'text-sm font-medium',
                  player.active ? 'text-[#E7EEE9]' : 'text-[#8B978F]',
                )}
              >
                {player.name}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-2 bg-[#121714] border border-[#242C27] rounded-full px-4 py-2 min-h-[44px]">
          <div className="relative flex h-3 w-3">
            {r50Status === 'connected' && (
              <>
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-garage-green opacity-40"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-garage-green"></span>
              </>
            )}
            {r50Status === 'waiting' && (
              <span className="relative inline-flex rounded-full h-3 w-3 bg-garage-amber"></span>
            )}
            {r50Status === 'paused' && (
              <span className="relative inline-flex rounded-full h-3 w-3 bg-[#8B978F]"></span>
            )}
          </div>
          <span className="text-sm font-medium text-[#E7EEE9]">
            {r50Status === 'connected'
              ? 'R50 Connected'
              : r50Status === 'waiting'
                ? 'Waiting for R50...'
                : 'R50 Paused'}
          </span>
          <Wifi className="w-4 h-4 text-[#8B978F] ml-2" />
        </div>

        <button
          onClick={() => setIsPaused(!isPaused)}
          className={cn(
            'flex items-center space-x-2 px-6 py-2.5 rounded-full font-medium transition-all min-h-[44px]',
            isPaused
              ? 'bg-[#1A211D] text-[#E7EEE9] border border-[#242C27]'
              : 'bg-garage-green text-[#0A0D0B] shadow-glow-primary-sm hover:bg-garage-green-deep',
          )}
        >
          {isPaused ? (
            <>
              <Play className="w-4 h-4 fill-current" />
              <span>Resume</span>
            </>
          ) : (
            <>
              <Pause className="w-4 h-4 fill-current" />
              <span>Pause</span>
            </>
          )}
        </button>
      </div>
    </header>
  )
}

import { Calendar, Video, ChevronRight, Activity } from 'lucide-react'
import { cn } from '../lib/utils'
import { Avatar, AvatarFallback, AvatarImage } from '../components/Avatar'
const sessions = [
  {
    id: 1,
    date: 'Today, 2:30 PM',
    player: 'Alex M.',
    avatar: 'https://i.pravatar.cc/150?u=alex',
    clubs: 'Driver, 7i',
    swings: 42,
    summary:
      'Focused on reducing hip sway. Consistent improvement in last 10 swings.',
    stats: ['Avg Hip Sway 2.1in', 'Best swing: #38'],
    isLive: true,
  },
  {
    id: 2,
    date: 'Oct 28, 4:15 PM',
    player: 'Alex M.',
    avatar: 'https://i.pravatar.cc/150?u=alex',
    clubs: 'Driver',
    swings: 15,
    summary: 'Quick speed training session. Club speed up +3mph.',
    stats: ['Max Speed 114mph', 'Avg Carry 285y'],
    isLive: false,
  },
  {
    id: 3,
    date: 'Oct 25, 1:00 PM',
    player: 'Sarah T.',
    avatar: 'https://i.pravatar.cc/150?u=sarah',
    clubs: 'PW, 8i, 6i',
    swings: 65,
    summary: 'Iron gapping and face control. Face angle improved to +/- 1.5°.',
    stats: ['Face to Path 1.2°', 'Consistent Contact'],
    isLive: false,
  },
]
export function SessionsScreen() {
  return (
    <div className="h-full flex flex-col p-6 space-y-6 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-[#E7EEE9]">Sessions</h1>
        <button className="bg-[#1A211D] border border-[#242C27] text-[#E7EEE9] px-5 py-2.5 rounded-full text-sm font-medium hover:bg-[#242C27] transition-colors min-h-[44px] flex items-center">
          <Calendar className="w-4 h-4 mr-2" />
          Filter by Date
        </button>
      </div>

      <div className="flex flex-col space-y-4">
        {sessions.map((session) => (
          <div
            key={session.id}
            className={cn(
              'bg-[#121714] border rounded-[24px] p-6 flex flex-col md:flex-row md:items-center gap-6 transition-all hover:bg-[#1A211D]/50 cursor-pointer group',
              session.isLive
                ? 'border-garage-green shadow-glow-primary-sm'
                : 'border-[#242C27]',
            )}
          >
            {/* Left Col: Meta */}
            <div className="flex flex-col space-y-3 min-w-[200px]">
              {session.isLive ? (
                <div className="flex items-center space-x-2 text-garage-green font-medium text-sm">
                  <div className="w-2 h-2 rounded-full bg-garage-green animate-pulse shadow-glow-primary-sm" />
                  <span>Recording Live</span>
                </div>
              ) : (
                <div className="text-[#8B978F] font-medium text-sm">
                  {session.date}
                </div>
              )}

              <div className="flex items-center space-x-3">
                <Avatar className="w-8 h-8 ring-1 ring-[#242C27]">
                  <AvatarImage src={session.avatar} />
                  <AvatarFallback>{session.player.charAt(0)}</AvatarFallback>
                </Avatar>
                <span className="text-[#E7EEE9] font-medium">
                  {session.player}
                </span>
              </div>
            </div>

            {/* Center Col: Details */}
            <div className="flex-1 flex flex-col space-y-3">
              <div className="flex flex-wrap gap-2">
                <div className="bg-[#1A211D] border border-[#242C27] px-3 py-1.5 rounded-full text-xs font-medium text-[#E7EEE9] flex items-center">
                  <Activity className="w-3.5 h-3.5 mr-1.5 text-[#8B978F]" />
                  {session.swings} Swings
                </div>
                <div className="bg-[#1A211D] border border-[#242C27] px-3 py-1.5 rounded-full text-xs font-medium text-[#E7EEE9]">
                  {session.clubs}
                </div>
                {session.stats.map((stat) => (
                  <div
                    key={stat}
                    className="bg-garage-green/10 text-garage-green px-3 py-1.5 rounded-full text-xs font-medium"
                  >
                    {stat}
                  </div>
                ))}
              </div>
              <p className="text-sm text-[#8B978F] leading-relaxed">
                <span className="text-[#E7EEE9] font-medium mr-1">
                  AI Summary:
                </span>
                {session.summary}
              </p>
            </div>

            {/* Right Col: Action */}
            <div className="flex items-center justify-end">
              <button className="flex items-center space-x-2 text-[#E7EEE9] bg-[#1A211D] group-hover:bg-garage-green group-hover:text-[#0A0D0B] px-5 py-3 rounded-full font-medium transition-all min-h-[44px]">
                <Video className="w-4 h-4" />
                <span>View Swings</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

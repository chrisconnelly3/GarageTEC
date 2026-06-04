import { Calendar, Video, ChevronRight, Activity } from 'lucide-react'
import { cn } from '../lib/utils'
import { Avatar, AvatarFallback } from '../components/Avatar'
import { useApi } from '../lib/useApi'
import { getSessions, getPlayers, getSession } from '../lib/api'

interface SessionVM {
  id: number
  date: string
  player: string
  clubs: string
  swings: number
  summary: string
  stats: string[]
  isLive: boolean
}

const formatDateTime = (iso: string) => {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  })
}

interface SessionsScreenProps {
  activeSessionId: number | null
}

export function SessionsScreen({ activeSessionId }: SessionsScreenProps) {
  const { data, loading, error } = useApi<SessionVM[]>(async () => {
    const [sessions, players] = await Promise.all([getSessions(), getPlayers()])
    const nameById = new Map(players.map((p) => [p.id, p.name]))
    // Lazily fetch details for the first ~10 sessions for swing count/summary.
    const top = sessions.slice(0, 10)
    const details = await Promise.all(
      top.map((s) => getSession(s.id).catch(() => null)),
    )
    return top.map((s, i) => {
      const d = details[i]
      const clubs = d
        ? Array.from(
            new Set(d.swings.map((sw) => sw.club).filter(Boolean) as string[]),
          ).join(', ')
        : ''
      return {
        id: s.id,
        date: formatDateTime(s.started_at),
        player: nameById.get(s.player_id) ?? `Player ${s.player_id}`,
        clubs: clubs || '—',
        swings: d?.swings.length ?? 0,
        summary: d?.coaching[0]?.content?.headline ?? 'No summary yet.',
        stats: [],
        isLive: s.ended_at === null || s.id === activeSessionId,
      }
    })
  }, [activeSessionId])

  return (
    <div className="h-full flex flex-col p-6 space-y-6 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-[#E7EEE9]">Sessions</h1>
        <button className="bg-[#1A211D] border border-[#242C27] text-[#E7EEE9] px-5 py-2.5 rounded-full text-sm font-medium hover:bg-[#242C27] transition-colors min-h-[44px] flex items-center">
          <Calendar className="w-4 h-4 mr-2" />
          Filter by Date
        </button>
      </div>

      {loading && <div className="text-[#8B978F]">Loading…</div>}
      {error && (
        <div className="rounded-[18px] border border-garage-red/40 bg-garage-red/10 px-6 py-4 text-sm text-garage-red">
          Failed to load sessions: {error}
        </div>
      )}
      {!loading && !error && (data?.length ?? 0) === 0 && (
        <div className="text-[#8B978F]">No sessions yet.</div>
      )}

      <div className="flex flex-col space-y-4">
        {(data ?? []).map((session) => (
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

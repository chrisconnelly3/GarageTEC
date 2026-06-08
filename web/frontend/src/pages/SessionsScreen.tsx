import { Video, ChevronRight, Activity, Target, Ruler } from 'lucide-react'
import { cn } from '../lib/utils'
import { Avatar, AvatarFallback } from '../components/Avatar'
import { useApi } from '../lib/useApi'
import { getSessions, getPlayers, getSessionStats } from '../lib/api'
import type { SessionStats } from '../lib/types'

interface SessionVM {
  id: number
  playerId: number
  player: string
  date: string
  isLive: boolean
  stats: SessionStats | null
}

const formatDateTime = (iso: string) => {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  })
}

interface SessionsScreenProps {
  activeSessionId: number | null
  onLoadSession: (sessionId: number, playerId: number) => void
}

export function SessionsScreen({ activeSessionId, onLoadSession }: SessionsScreenProps) {
  const { data, loading, error } = useApi<SessionVM[]>(async () => {
    const [sessions, players] = await Promise.all([getSessions(), getPlayers()])
    const nameById = new Map(players.map((p) => [p.id, p.name]))
    // Sessions arrive most-recent-first (live pinned to top) from the API.
    const top = sessions.slice(0, 12)
    const stats = await Promise.all(
      top.map((s) => getSessionStats(s.id).catch(() => null)),
    )
    return top.map((s, i) => ({
      id: s.id,
      playerId: s.player_id,
      player: nameById.get(s.player_id) ?? `Player ${s.player_id}`,
      date: formatDateTime(s.started_at),
      isLive: s.ended_at === null || s.id === activeSessionId,
      stats: stats[i],
    }))
  }, [activeSessionId])

  return (
    <div className="h-full flex flex-col p-6 space-y-6 overflow-y-auto">
      <h1 className="text-2xl font-semibold text-[#E7EEE9]">Sessions</h1>

      {loading && <div className="text-[#8B978F]">Loading…</div>}
      {error && (
        <div className="rounded-[18px] border border-garage-red/40 bg-garage-red/10 px-6 py-4 text-sm text-garage-red">
          Failed to load sessions: {error}
        </div>
      )}
      {!loading && !error && (data?.length ?? 0) === 0 && (
        <div className="text-[#8B978F]">No sessions yet. Start a session to begin tracking your swings.</div>
      )}

      <div className="flex flex-col space-y-4">
        {(data ?? []).map((session) => {
          const s = session.stats
          const swingCount = s?.swing_count ?? 0
          const canLoad = swingCount > 0
          const tr = s?.tour_range ?? null
          const ratio = tr && tr.total ? tr.in_range / tr.total : 0
          const trColor = ratio >= 0.6 ? 'green' : ratio >= 0.3 ? 'amber' : 'red'
          // Clubs, most-used first.
          const clubs = Object.entries(s?.club_counts ?? {}).sort((a, b) => b[1] - a[1])
          const load = () => canLoad && onLoadSession(session.id, session.playerId)
          return (
            <div
              key={session.id}
              role="button"
              tabIndex={canLoad ? 0 : -1}
              aria-disabled={!canLoad}
              onClick={load}
              onKeyDown={(e) => { if (canLoad && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); load() } }}
              className={cn(
                'bg-[#121714] border rounded-[24px] p-6 flex flex-col md:flex-row md:items-center gap-6 transition-all group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60',
                canLoad ? 'cursor-pointer hover:bg-[#1A211D]/50' : 'opacity-60',
                session.isLive
                  ? 'border-garage-green shadow-glow-primary-sm'
                  : 'border-[#242C27]',
              )}
            >
              {/* Left: when + who */}
              <div className="flex flex-col space-y-3 min-w-[180px]">
                {session.isLive ? (
                  <div className="flex items-center space-x-2 text-garage-green font-medium text-sm">
                    <div className="w-2 h-2 rounded-full bg-garage-green animate-pulse shadow-glow-primary-sm" />
                    <span>Recording Live</span>
                  </div>
                ) : null}
                <div className="text-[#8B978F] font-medium text-sm">{session.date}</div>
                <div className="flex items-center space-x-3">
                  <Avatar className="w-8 h-8 ring-1 ring-[#242C27]">
                    <AvatarFallback>{session.player.charAt(0)}</AvatarFallback>
                  </Avatar>
                  <span className="text-[#E7EEE9] font-medium">{session.player}</span>
                </div>
              </div>

              {/* Center: at-a-glance stats + optional AI takeaway */}
              <div className="flex-1 flex flex-col space-y-3 min-w-0">
                <div className="flex flex-wrap gap-2">
                  <span className="bg-[#1A211D] border border-[#242C27] px-3 py-1.5 rounded-full text-xs font-medium text-[#E7EEE9] flex items-center">
                    <Activity className="w-3.5 h-3.5 mr-1.5 text-[#8B978F]" />
                    {swingCount} {swingCount === 1 ? 'Swing' : 'Swings'}
                  </span>
                  {tr && (
                    <span className="bg-[#1A211D] border border-[#242C27] px-3 py-1.5 rounded-full text-xs font-medium text-[#E7EEE9] flex items-center">
                      <span className={cn('w-1.5 h-1.5 rounded-full mr-1.5',
                        trColor === 'green' ? 'bg-garage-green'
                          : trColor === 'amber' ? 'bg-garage-amber' : 'bg-garage-red')} />
                      {tr.in_range}/{tr.total} in tour range
                    </span>
                  )}
                  {s?.top_ball && (
                    <span className="bg-[#1A211D] border border-[#242C27] px-3 py-1.5 rounded-full text-xs font-medium text-[#E7EEE9] flex items-center">
                      <Ruler className="w-3.5 h-3.5 mr-1.5 text-[#8B978F]" />
                      {s.top_ball.label} {s.top_ball.value} {s.top_ball.unit}
                    </span>
                  )}
                  {clubs.map(([club, n]) => (
                    <span key={club} className="bg-[#1A211D] border border-[#242C27] px-3 py-1.5 rounded-full text-xs font-medium text-[#8B978F]">
                      {club}<span className="text-[#5b6b5f]"> ×{n}</span>
                    </span>
                  ))}
                </div>
                {s?.takeaway && (
                  <p className="text-sm text-[#8B978F] leading-relaxed flex items-start gap-1.5">
                    <Target className="w-3.5 h-3.5 mt-0.5 shrink-0 text-garage-green" />
                    <span>{s.takeaway}</span>
                  </p>
                )}
              </div>

              {/* Right: load into the Swing screen */}
              <div className="flex items-center justify-end">
                <span className={cn(
                  'flex items-center space-x-2 px-5 py-3 rounded-full font-medium transition-all min-h-[44px]',
                  canLoad
                    ? 'text-[#E7EEE9] bg-[#1A211D] group-hover:bg-garage-green group-hover:text-[#0A0D0B]'
                    : 'text-[#5b6b5f] bg-[#1A211D]',
                )}>
                  <Video className="w-4 h-4" />
                  <span>Load Session</span>
                  <ChevronRight className="w-4 h-4" />
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

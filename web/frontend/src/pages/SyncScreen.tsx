import { Link, Unlink, Check, AlertCircle, Video, Activity } from 'lucide-react'
import { cn } from '../lib/utils'
import { useApi } from '../lib/useApi'
import { getProposals, applyMatch, unlinkSwing } from '../lib/api'
import type { SyncProposals } from '../lib/types'

interface MatchRow {
  id: string
  swingId: number
  shotId: number | null
  time: string
  confidence: number
  status: 'matched' | 'review' | 'unmatched_swing'
  swingMetrics: string[]
  shot: { speed: string; carry: string } | null
}

const fmtTime = (iso: string) => {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit', second: '2-digit' })
}

function buildRows(data: SyncProposals): MatchRow[] {
  const swingById = new Map(data.unmatched_swings.map((s) => [s.id, s]))
  const shotById = new Map(data.unmatched_shots.map((s) => [s.id, s]))
  const rows: MatchRow[] = []
  const proposedSwings = new Set<number>()

  for (const p of data.proposals) {
    proposedSwings.add(p.swing_id)
    const sw = swingById.get(p.swing_id)
    const shot = shotById.get(p.shot_id)
    const confidence = Math.round(p.confidence * 100)
    rows.push({
      id: `p-${p.swing_id}-${p.shot_id}`,
      swingId: p.swing_id,
      shotId: p.shot_id,
      time: sw ? fmtTime(sw.created_at) : '',
      confidence,
      status: confidence >= 75 ? 'matched' : 'review',
      swingMetrics: [sw?.club ?? 'Swing', sw ? fmtTime(sw.created_at) : ''].filter(Boolean),
      shot: shot
        ? {
            speed: shot.ball_speed != null ? `${shot.ball_speed}mph` : '--',
            carry: shot.carry != null ? `${shot.carry}y` : '--',
          }
        : null,
    })
  }

  for (const sw of data.unmatched_swings) {
    if (proposedSwings.has(sw.id)) continue
    rows.push({
      id: `s-${sw.id}`,
      swingId: sw.id,
      shotId: null,
      time: fmtTime(sw.created_at),
      confidence: 0,
      status: 'unmatched_swing',
      swingMetrics: [sw.club ?? 'Swing'],
      shot: null,
    })
  }
  return rows
}

interface SyncScreenProps {
  sessionId: number | null
}

export function SyncScreen({ sessionId }: SyncScreenProps) {
  const { data, loading, error, reload } = useApi<SyncProposals | null>(
    () => (sessionId ? getProposals(sessionId) : Promise.resolve(null)),
    [sessionId],
  )

  const rows = data ? buildRows(data) : []
  const empty =
    data &&
    data.proposals.length === 0 &&
    data.unmatched_swings.length === 0

  return (
    <div className="h-full flex flex-col p-6 space-y-6 overflow-y-auto">
      <div className="flex flex-col space-y-2">
        <h1 className="text-2xl font-semibold text-[#E7EEE9]">Sync</h1>
        <p className="text-[#8B978F] flex items-center">
          Match camera swings to R50 launch data.{' '}
          {data && (
            <span className="text-[#E7EEE9] font-medium ml-2 bg-[#1A211D] px-2 py-0.5 rounded">
              {data.proposals.length} proposals — {data.unmatched_swings.length} unmatched
            </span>
          )}
        </p>
      </div>

      {loading && <div className="text-[#8B978F]">Loading…</div>}
      {error && (
        <div className="rounded-[18px] border border-garage-red/40 bg-garage-red/10 px-6 py-4 text-sm text-garage-red">
          Failed to load proposals: {error}
        </div>
      )}
      {!sessionId && !loading && (
        <div className="text-[#8B978F]">No active session.</div>
      )}
      {empty && <div className="text-[#8B978F]">All swings matched.</div>}

      <div className="flex flex-col space-y-4">
        {rows.map((match) => (
          <div
            key={match.id}
            className="bg-[#121714] border border-[#242C27] rounded-[24px] p-4 flex flex-col lg:flex-row items-center gap-4"
          >
            {/* Left: Camera Swing */}
            <div className="flex-1 w-full bg-[#1A211D] rounded-[18px] p-4 flex items-center space-x-4 border border-[#242C27]">
              <div className="w-16 h-12 bg-[#0A0D0B] rounded-lg flex items-center justify-center border border-[#242C27] relative overflow-hidden">
                <Video className="w-5 h-5 text-[#4A554E]" />
                <div className="absolute bottom-1 right-1 text-[9px] font-mono text-[#8B978F]">
                  {match.time}
                </div>
              </div>
              <div className="flex flex-col space-y-1.5">
                <span className="text-xs font-semibold uppercase tracking-wider text-[#8B978F]">
                  Camera Swing
                </span>
                <div className="flex gap-2">
                  {match.swingMetrics.map((m) => (
                    <span
                      key={m}
                      className="text-xs text-[#E7EEE9] bg-[#242C27] px-2 py-1 rounded-md"
                    >
                      {m}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Center: Connector */}
            <div className="flex flex-col items-center px-2 py-4 lg:py-0">
              {match.shot ? (
                <>
                  <div
                    className={cn(
                      'px-3 py-1.5 rounded-full text-xs font-bold flex items-center space-x-1.5',
                      match.confidence >= 75
                        ? 'bg-garage-green/10 text-garage-green'
                        : 'bg-garage-amber/10 text-garage-amber',
                    )}
                  >
                    <Link className="w-3.5 h-3.5" />
                    <span>{match.confidence}% Match</span>
                  </div>
                  <div className="w-px h-6 lg:w-6 lg:h-px bg-[#242C27] my-2 lg:my-0 lg:mx-2" />
                </>
              ) : (
                <div className="px-3 py-1.5 rounded-full text-xs font-bold bg-garage-red/10 text-garage-red flex items-center space-x-1.5">
                  <AlertCircle className="w-3.5 h-3.5" />
                  <span>No Match</span>
                </div>
              )}
            </div>

            {/* Right: R50 Shot */}
            <div
              className={cn(
                'flex-1 w-full rounded-[18px] p-4 flex items-center justify-between border border-[#242C27]',
                match.shot ? 'bg-[#1A211D]' : 'bg-[#0A0D0B] border-dashed',
              )}
            >
              {match.shot ? (
                <div className="flex items-center space-x-4">
                  <div className="w-12 h-12 bg-[#242C27] rounded-full flex items-center justify-center">
                    <Activity className="w-5 h-5 text-garage-green" />
                  </div>
                  <div className="flex flex-col space-y-1.5">
                    <span className="text-xs font-semibold uppercase tracking-wider text-[#8B978F]">
                      R50 Shot
                    </span>
                    <div className="flex gap-2">
                      <span className="text-xs font-mono text-[#E7EEE9] bg-[#242C27] px-2 py-1 rounded-md">
                        {match.shot.speed}
                      </span>
                      <span className="text-xs font-mono text-[#E7EEE9] bg-[#242C27] px-2 py-1 rounded-md">
                        {match.shot.carry}
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-[#8B978F] italic px-4">
                  Waiting for R50 data...
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center space-x-2 ml-4">
                {match.status === 'review' && match.shotId != null && (
                  <button
                    onClick={() =>
                      applyMatch(match.swingId, match.shotId!).then(reload)
                    }
                    className="bg-garage-green text-[#0A0D0B] p-3 rounded-full hover:bg-garage-green-deep transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                    title="Confirm Match"
                  >
                    <Check className="w-5 h-5" />
                  </button>
                )}
                {match.shot && (
                  <button
                    onClick={() => unlinkSwing(match.swingId).then(reload)}
                    className="bg-[#242C27] text-[#E7EEE9] p-3 rounded-full hover:bg-[#4A554E] transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                    title="Unlink"
                  >
                    <Unlink className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

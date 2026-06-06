import { useEffect, useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { LiveScreen } from './pages/LiveScreen'
import { ReviewScreen } from './pages/ReviewScreen'
import { HistoryScreen } from './pages/HistoryScreen'
import { SessionsScreen } from './pages/SessionsScreen'
import { PlayersScreen } from './pages/PlayersScreen'
import { SyncScreen } from './pages/SyncScreen'
import { ConnectScreen } from './pages/ConnectScreen'
import useEvents from './useEvents'
import useCapture from './useCapture'
import { useApi } from './lib/useApi'
import { getPlayers, getSessions, getLatestSwing } from './lib/api'
import type { Player } from './lib/types'

export default function App() {
  const [activeTab, setActiveTab] = useState('live')

  const { lastSwing, lastCapture } = useEvents()
  const capture = useCapture(lastCapture)
  const { data: players, reload: reloadPlayers } = useApi(getPlayers, [])

  const playerList: Player[] = players ?? []

  // Active player: server-side state if set, else fall back to first player
  // (read-only screens) so Live/History resolve on a fresh boot. See plan Risks.
  const serverActiveId = capture.status?.active_player_id ?? null
  const activePlayerId =
    serverActiveId ?? (playerList.length > 0 ? playerList[0].id : null)

  // Derive the active player's newest session.
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null)
  useEffect(() => {
    if (activePlayerId == null) {
      setActiveSessionId(null)
      return
    }
    let alive = true
    getSessions(activePlayerId)
      .then((s) => { if (alive) setActiveSessionId(s[0]?.id ?? null) })
      .catch(() => { if (alive) setActiveSessionId(null) })
    return () => { alive = false }
  }, [activePlayerId, lastSwing, lastCapture])

  // The latest ready swing id for Review (resolved from the active player).
  const [reviewSwingId, setReviewSwingId] = useState<number | null>(null)
  useEffect(() => {
    if (activePlayerId == null) {
      setReviewSwingId(null)
      return
    }
    let alive = true
    getLatestSwing(activePlayerId, activeSessionId ?? undefined)
      .then((d) => { if (alive) setReviewSwingId(d?.swing.id ?? null) })
      .catch(() => { if (alive) setReviewSwingId(null) })
    return () => { alive = false }
  }, [activePlayerId, activeSessionId, lastSwing])

  // Map capture status → Topbar union
  const st = capture.status?.status
  const r50Status: 'connected' | 'waiting' | 'paused' =
    st === 'connected' ? 'connected' : st === 'paused' ? 'paused' : 'waiting'
  const sessionActive = !!capture.status?.session_active

  // Inline message when Start Session is rejected (409 = no active player).
  const [sessionError, setSessionError] = useState<string | null>(null)
  const handleStartSession = () => {
    setSessionError(null)
    capture.startSession().catch((e: Error) => {
      setSessionError(
        e.message?.startsWith('409')
          ? 'Select a player first'
          : 'Could not start session',
      )
    })
  }
  const handleEndSession = () => {
    setSessionError(null)
    capture.endSession().catch(() => setSessionError('Could not end session'))
  }

  const selectPlayerById = (id: number) => {
    const p = playerList.find((x) => x.id === id)
    if (p) capture.selectPlayer({ name: p.name, height_in: p.height_in, handedness: p.handedness })
  }
  const setActivePlayer = (p: Player) => {
    capture.selectPlayer({ name: p.name, height_in: p.height_in, handedness: p.handedness })
      .then(() => capture.refresh())
  }

  return (
    <div className="flex h-screen w-full bg-[#0A0D0B] text-[#E7EEE9] overflow-hidden font-sans selection:bg-garage-green/30 selection:text-garage-green">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

      <div className="flex-1 flex flex-col min-w-0">
        <Topbar
          players={playerList.map((p) => ({ id: p.id, name: p.name }))}
          activePlayerId={activePlayerId}
          sessionActive={sessionActive}
          sessionError={sessionError}
          r50Status={r50Status}
          activeClub={capture.status?.active_club ?? null}
          onSelectClub={capture.selectClub}
          onStartSession={handleStartSession}
          onEndSession={handleEndSession}
          onSelectPlayer={(p) => selectPlayerById(p.id)}
        />

        <main className="flex-1 overflow-hidden relative">
          {activeTab === 'live' && (
            <LiveScreen
              playerId={activePlayerId}
              sessionId={activeSessionId}
              lastSwing={lastSwing}
              lastCapture={lastCapture}
              activeClub={capture.status?.active_club ?? null}
            />
          )}
          {activeTab === 'review' && (
            <ReviewScreen
              playerId={activePlayerId}
              sessionId={activeSessionId}
              defaultSwingId={reviewSwingId}
            />
          )}
          {activeTab === 'history' && <HistoryScreen playerId={activePlayerId} />}
          {activeTab === 'sessions' && (
            <SessionsScreen activeSessionId={activeSessionId} />
          )}
          {activeTab === 'players' && (
            <PlayersScreen
              activePlayerId={activePlayerId}
              onSetActive={setActivePlayer}
              onAdded={reloadPlayers}
            />
          )}
          {activeTab === 'sync' && <SyncScreen sessionId={activeSessionId} />}
          {activeTab === 'connect' && (
            <ConnectScreen captureStatus={capture.status} />
          )}
        </main>
      </div>
    </div>
  )
}

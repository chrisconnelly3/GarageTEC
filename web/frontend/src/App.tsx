import { useEffect, useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { SwingScreen } from './pages/SwingScreen'
import { HistoryScreen } from './pages/HistoryScreen'
import { SessionsScreen } from './pages/SessionsScreen'
import { PlayersScreen } from './pages/PlayersScreen'
import { ConnectScreen } from './pages/ConnectScreen'
import useEvents from './useEvents'
import useCapture from './useCapture'
import { useApi } from './lib/useApi'
import { getPlayers, getSessions } from './lib/api'
import type { Player } from './lib/types'

export default function App() {
  const [activeTab, setActiveTab] = useState('swing')

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

  const [pinnedSwingId, setPinnedSwingId] = useState<number | null>(null)
  // A past session the user chose to review ("Load Session"). When set, the Swing
  // screen scopes its swing selector to this session instead of the live one.
  const [loadedSessionId, setLoadedSessionId] = useState<number | null>(null)

  // Deep-link a single swing (from History). Operates on the live/all-swings
  // context, so clear any loaded past session.
  const openSwing = (id: number) => {
    setLoadedSessionId(null); setPinnedSwingId(id); setActiveTab('swing')
  }
  // "Load Session" from the Sessions list: switch to that session's player,
  // scope the Swing screen to that session, and land on its latest swing.
  const loadSession = (sessionId: number, playerId: number) => {
    if (playerId !== activePlayerId) selectPlayerById(playerId)
    setPinnedSwingId(null)
    setLoadedSessionId(sessionId)
    setActiveTab('swing')
  }
  // Sidebar navigation: clicking "Swing" returns to the live session, so clear
  // any loaded past session.
  const selectTab = (tab: string) => {
    if (tab === 'swing') setLoadedSessionId(null)
    setActiveTab(tab)
  }

  // Map capture status → 4-state R50 value
  const st = capture.status?.status
  const r50: 'connected' | 'waiting' | 'paused' | 'error' =
    st === 'connected' ? 'connected'
      : st === 'paused' ? 'paused'
        : (capture.status?.last_error || st === 'stopped') ? 'error'
          : 'waiting'
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
      {/* Brand logo — dead-center of the viewport, vertically centered in the
          80px header. Rendered here (not inside Topbar) so the header's
          backdrop-filter doesn't become its fixed-positioning containing block.
          Shrinks below 2xl so its centered footprint never overlaps the Topbar's
          player/club controls on narrower displays; full size at the 1920 bay. */}
      <img
        src="/garagetec-logo.png"
        alt="GarageTEC"
        className="fixed top-1.5 left-1/2 -translate-x-1/2 z-30 h-10 2xl:h-[68px] w-auto max-w-[240px] 2xl:max-w-[440px] object-contain pointer-events-none select-none"
      />

      <Sidebar activeTab={activeTab} setActiveTab={selectTab} r50Error={r50 === 'error'} />

      <div className="flex-1 flex flex-col min-w-0">
        <Topbar
          players={playerList.map((p) => ({ id: p.id, name: p.name }))}
          activePlayerId={activePlayerId}
          sessionActive={sessionActive}
          sessionError={sessionError}
          r50Status={r50}
          activeClub={capture.status?.active_club ?? null}
          onSelectClub={capture.selectClub}
          onStartSession={handleStartSession}
          onEndSession={handleEndSession}
          onSelectPlayer={(p) => selectPlayerById(p.id)}
        />

        <main className="flex-1 overflow-hidden relative">
          {activeTab === 'swing' && (
            <SwingScreen
              playerId={activePlayerId}
              sessionId={loadedSessionId ?? activeSessionId}
              lastSwing={lastSwing}
              activeClub={capture.status?.active_club ?? null}
              r50={r50}
              deepLinkSwingId={pinnedSwingId}
              onReconnect={() => setActiveTab('connect')}
            />
          )}
          {activeTab === 'history' && <HistoryScreen playerId={activePlayerId} onOpenSwing={openSwing} />}
          {activeTab === 'sessions' && (
            <SessionsScreen activeSessionId={activeSessionId} onLoadSession={loadSession} />
          )}
          {activeTab === 'players' && (
            <PlayersScreen
              activePlayerId={activePlayerId}
              onSetActive={setActivePlayer}
              onAdded={reloadPlayers}
            />
          )}
          {activeTab === 'connect' && (
            <ConnectScreen captureStatus={capture.status} />
          )}
        </main>
      </div>
    </div>
  )
}

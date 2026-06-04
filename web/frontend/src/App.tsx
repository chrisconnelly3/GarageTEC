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

export default function App() {
  const [activeTab, setActiveTab] = useState('live')
  const [isPaused, setIsPaused] = useState(false)
  const [r50Status, setR50Status] = useState<
    'connected' | 'waiting' | 'paused'
  >('connected')
  // Toggle R50 status based on pause state for demo purposes
  useEffect(() => {
    if (isPaused) setR50Status('paused')
    else setR50Status('connected')
  }, [isPaused])
  return (
    <div className="flex h-screen w-full bg-[#0A0D0B] text-[#E7EEE9] overflow-hidden font-sans selection:bg-garage-green/30 selection:text-garage-green">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

      <div className="flex-1 flex flex-col min-w-0">
        <Topbar
          isPaused={isPaused}
          setIsPaused={setIsPaused}
          r50Status={r50Status}
        />

        <main className="flex-1 overflow-hidden relative">
          {activeTab === 'live' && <LiveScreen />}
          {activeTab === 'review' && <ReviewScreen />}
          {activeTab === 'history' && <HistoryScreen />}
          {activeTab === 'sessions' && <SessionsScreen />}
          {activeTab === 'players' && <PlayersScreen />}
          {activeTab === 'sync' && <SyncScreen />}
          {activeTab === 'connect' && <ConnectScreen />}
        </main>
      </div>
    </div>
  )
}

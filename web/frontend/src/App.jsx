import { useEffect, useState } from "react";
import { Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import GlobalBar from "./components/GlobalBar";
import useEvents from "./useEvents";
import useCapture from "./useCapture";
import { getPlayers } from "./api";
import Live from "./pages/Live";
import SwingReview from "./pages/SwingReview";
import Session from "./pages/Session";
import History from "./pages/History";
import SyncFix from "./pages/SyncFix";
import Players from "./pages/Players";
import Connect from "./pages/Connect";

export default function App() {
  const { lastSwing, lastCapture } = useEvents();
  const cap = useCapture(lastCapture);
  const [players, setPlayers] = useState([]);

  useEffect(() => { getPlayers().then(setPlayers); }, [lastCapture]);

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        <GlobalBar players={players} status={cap.status}
          onSelectPlayer={(p) => cap.selectPlayer({
            name: p.name, height_in: p.height_in, handedness: p.handedness })}
          onPause={cap.pause} onResume={cap.resume} />
        <Routes>
          <Route path="/" element={<Live lastSwing={lastSwing} />} />
          <Route path="/swing/:id" element={<SwingReview />} />
          <Route path="/review" element={<SwingReview />} />
          <Route path="/sessions" element={<Session />} />
          <Route path="/session/:id" element={<Session />} />
          <Route path="/history" element={<History />} />
          <Route path="/sync" element={<SyncFix />} />
          <Route path="/players" element={<Players />} />
          <Route path="/connect" element={<Connect lastCapture={lastCapture} />} />
        </Routes>
      </div>
    </div>
  );
}

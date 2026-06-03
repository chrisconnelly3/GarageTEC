import { Routes, Route, Link } from "react-router-dom";
import Live from "./pages/Live";
import SwingReview from "./pages/SwingReview";
import Session from "./pages/Session";
import History from "./pages/History";
import SyncFix from "./pages/SyncFix";
import Players from "./pages/Players";

export default function App() {
  return (
    <>
      <nav>
        <Link to="/">Live</Link>
        <Link to="/history">History</Link>
        <Link to="/sync">Sync fix</Link>
        <Link to="/players">Players</Link>
      </nav>
      <Routes>
        <Route path="/" element={<Live />} />
        <Route path="/swing/:id" element={<SwingReview />} />
        <Route path="/session/:id" element={<Session />} />
        <Route path="/history" element={<History />} />
        <Route path="/sync" element={<SyncFix />} />
        <Route path="/players" element={<Players />} />
      </Routes>
    </>
  );
}

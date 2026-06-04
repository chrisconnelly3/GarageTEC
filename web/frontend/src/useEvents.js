import { useEffect, useState } from "react";

// Returns { lastSwing, lastCapture } where lastCapture is the most recent
// capture event: { type, data } for shot_received|capture_status|active_player_changed.
export default function useEvents() {
  const [lastSwing, setLastSwing] = useState(null);
  const [lastCapture, setLastCapture] = useState(null);

  useEffect(() => {
    const es = new EventSource("/events");
    const onSwing = (e) => {
      try { setLastSwing(JSON.parse(e.data)); } catch { /* ignore */ }
    };
    const onCapture = (type) => (e) => {
      try { setLastCapture({ type, data: JSON.parse(e.data) }); } catch { /* ignore */ }
    };
    es.addEventListener("swing_ready", onSwing);
    es.addEventListener("shot_received", onCapture("shot_received"));
    es.addEventListener("capture_status", onCapture("capture_status"));
    es.addEventListener("active_player_changed", onCapture("active_player_changed"));
    return () => es.close();
  }, []);

  return { lastSwing, lastCapture };
}

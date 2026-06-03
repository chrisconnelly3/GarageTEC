import { useEffect, useState } from "react";

// Subscribes to the SSE stream; returns the latest swing_ready payload
// ({ swing_id, session_id, player_id }) or null before the first event.
export default function useEvents() {
  const [lastSwing, setLastSwing] = useState(null);

  useEffect(() => {
    const es = new EventSource("/events");
    es.addEventListener("swing_ready", (e) => {
      try {
        setLastSwing(JSON.parse(e.data));
      } catch {
        /* ignore malformed frame */
      }
    });
    return () => es.close();
  }, []);

  return lastSwing;
}

import { useState } from "react";
import { useSse } from "./lib/useSse";

type SwingReady = { swing_id: number; session_id: number; player_id: number };
type CaptureEvt = { type: string; data: any };

export default function useEvents() {
  const [lastSwing, setLastSwing] = useState<SwingReady | null>(null);
  const [lastCapture, setLastCapture] = useState<CaptureEvt | null>(null);
  useSse({
    swing_ready: (d) => setLastSwing(d),
    shot_received: (d) => setLastCapture({ type: "shot_received", data: d }),
    capture_status: (d) => setLastCapture({ type: "capture_status", data: d }),
    active_player_changed: (d) => setLastCapture({ type: "active_player_changed", data: d }),
  });
  return { lastSwing, lastCapture };
}

import { useEffect, useState } from "react";
import {
  getCaptureStatus, pauseCapture, resumeCapture, restartCapture, setActivePlayer,
} from "./api";

// Holds capture status; refreshes on mount and whenever a capture SSE event
// arrives (passed in from useEvents). Exposes the control actions.
export default function useCapture(lastCapture) {
  const [status, setStatus] = useState(null);

  const refresh = () => getCaptureStatus().then(setStatus);
  useEffect(() => { refresh(); }, []);
  useEffect(() => { if (lastCapture) refresh(); }, [lastCapture]);

  return {
    status,
    pause: () => pauseCapture().then(setStatus),
    resume: () => resumeCapture().then(setStatus),
    restart: () => restartCapture().then(refresh),
    selectPlayer: (p) => setActivePlayer(p).then(setStatus),
    refresh,
  };
}

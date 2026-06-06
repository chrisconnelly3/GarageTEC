import { useEffect, useState } from "react";
import { getCaptureStatus, pauseCapture, resumeCapture, restartCapture, setActivePlayer, setActiveClub, startSession, endSession } from "./lib/api";
import type { CaptureStatus, ActivePlayerIn } from "./lib/types";

export default function useCapture(lastCapture: unknown) {
  const [status, setStatus] = useState<CaptureStatus | null>(null);
  const refresh = () => getCaptureStatus().then(setStatus).catch(() => {});
  useEffect(() => { refresh(); }, []);
  useEffect(() => { if (lastCapture) refresh(); }, [lastCapture]);
  return {
    status,
    pause: () => pauseCapture().then(setStatus),
    resume: () => resumeCapture().then(setStatus),
    restart: () => restartCapture().then(refresh),
    selectPlayer: (p: ActivePlayerIn) => setActivePlayer(p).then(setStatus),
    selectClub: (club: string | null) => setActiveClub(club).then(setStatus),
    // Returns the new status on success. On 409 (no active player) the promise
    // rejects with an Error whose message starts with "409"; callers surface a
    // small inline message instead of crashing.
    startSession: () => startSession().then((s) => { setStatus(s); return s; }),
    endSession: () => endSession().then((s) => { setStatus(s); return s; }),
    refresh,
  };
}

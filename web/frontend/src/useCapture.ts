import { useEffect, useState } from "react";
import { getCaptureStatus, pauseCapture, resumeCapture, restartCapture, setActivePlayer, setActiveClub } from "./lib/api";
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
    refresh,
  };
}

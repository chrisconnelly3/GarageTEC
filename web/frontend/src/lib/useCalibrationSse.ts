import { useEffect, useRef } from "react";

type Handlers = Record<string, (data: any) => void>;

/** Dedicated SSE for calibration; only open while `active` (card mounted). */
export function useCalibrationSse(active: boolean, handlers: Handlers) {
  const ref = useRef(handlers); ref.current = handlers;
  useEffect(() => {
    if (!active) return;
    const es = new EventSource("/api/calibration/stream");
    const names = ["calibration_status", "calibration_done"];
    const ls = names.map((n) => {
      const fn = (e: MessageEvent) => {
        try { ref.current[n]?.(JSON.parse(e.data)); } catch { /* ignore */ }
      };
      es.addEventListener(n, fn as EventListener);
      return [n, fn] as const;
    });
    return () => { ls.forEach(([n, fn]) => es.removeEventListener(n, fn as EventListener)); es.close(); };
  }, [active]);
}

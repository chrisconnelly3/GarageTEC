import { useEffect, useRef } from "react";

type Handlers = Record<string, (data: any) => void>;

/** Dedicated SSE for live swing capture; only open while `active` (card mounted).
 *  Events: live_capture_status (full status), live_swing_captured ({swing_id,...}). */
export function useLiveCaptureSse(active: boolean, handlers: Handlers) {
  const ref = useRef(handlers); ref.current = handlers;
  useEffect(() => {
    if (!active) return;
    const es = new EventSource("/api/live-capture/stream");
    const names = ["live_capture_status", "live_swing_captured"];
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

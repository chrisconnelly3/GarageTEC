import { useEffect, useRef } from "react";

type Handlers = Record<string, (data: any) => void>;

export function useSse(handlers: Handlers) {
  const ref = useRef(handlers);
  ref.current = handlers;
  useEffect(() => {
    const es = new EventSource("/events");
    const names = ["swing_ready", "shot_received", "capture_status", "active_player_changed"];
    const listeners = names.map((name) => {
      const fn = (e: MessageEvent) => {
        try { ref.current[name]?.(JSON.parse(e.data)); } catch { /* ignore */ }
      };
      es.addEventListener(name, fn as EventListener);
      return [name, fn] as const;
    });
    return () => { listeners.forEach(([n, fn]) => es.removeEventListener(n, fn as EventListener)); es.close(); };
  }, []);
}

import { useCallback, useEffect, useRef, useState } from "react";

export function useApi<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Generation counter: each load() call increments it; only the latest
  // generation is allowed to commit its result, so stale out-of-order
  // responses from rapid reload() calls are silently discarded.
  const genRef = useRef(0);
  const load = useCallback(() => {
    const gen = ++genRef.current;
    setLoading(true); setError(null);
    fn().then((d) => { if (gen === genRef.current) { setData(d); setLoading(false); } })
        .catch((e) => { if (gen === genRef.current) { setError(String(e)); setLoading(false); } });
    return () => { genRef.current++; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => load(), [load]);
  return { data, loading, error, reload: load };
}

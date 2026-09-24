import { useCallback, useEffect, useRef, useState } from "react";

interface PollingState<T> {
  data: T | null;
  error: string | null;
  lastSuccess: number | null;
  refresh: () => void;
}

/**
 * Calls `fetcher` every `intervalMs`. Keeps the last good data when a request fails,
 * so a short network blip never blanks the screen — it only shows a warning.
 */
export function usePolling<T>(fetcher: (() => Promise<T>) | null, intervalMs: number): PollingState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastSuccess, setLastSuccess] = useState<number | null>(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const inFlight = useRef(false);

  const run = useCallback(async () => {
    const fn = fetcherRef.current;
    if (!fn || inFlight.current) return;
    inFlight.current = true;
    try {
      const result = await fn();
      setData(result);
      setError(null);
      setLastSuccess(Date.now());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    setData(null);
    if (!fetcher) return;
    run();
    const id = window.setInterval(run, intervalMs);
    return () => window.clearInterval(id);
    // Re-subscribe when the fetcher identity changes (e.g. a different zone is selected).
  }, [fetcher, intervalMs, run]);

  return { data, error, lastSuccess, refresh: run };
}

/** Current time, updated every second — for "updated 3 s ago" labels. */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}

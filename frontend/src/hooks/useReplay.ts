import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../services/api";
import type { CityState, ReplayMeta } from "../types";

export interface ReplayControls {
  active: boolean;
  preparing: boolean;
  error: string | null;
  meta: ReplayMeta | null;
  index: number;
  playing: boolean;
  speed: number; // frames (recorded minutes) per second
  state: CityState | null;
  start: (at?: number, autoplay?: boolean) => void;
  exit: () => void;
  setIndex: (i: number) => void;
  setPlaying: (p: boolean) => void;
  setSpeed: (s: number) => void;
}

/**
 * Historical replay playhead. The server computes every frame once; the browser owns the
 * playhead and asks for frame i, caching frames so scrubbing back and forth is instant.
 */
export function useReplay(autoStartAt: number | null = null): ReplayControls {
  const [meta, setMeta] = useState<ReplayMeta | null>(null);
  const [active, setActive] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndexRaw] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(2);
  const [state, setState] = useState<CityState | null>(null);
  const cache = useRef(new Map<number, CityState>());

  const last = meta ? meta.frames.length - 1 : 0;
  const setIndex = useCallback((i: number) => setIndexRaw(Math.max(0, Math.min(i, last))), [last]);

  const start = useCallback(async (at = 0, autoplay = true) => {
    setActive(true);
    setError(null);
    setPreparing(true);
    try {
      const m = meta ?? (await api.replayMeta());
      setMeta(m);
      setIndexRaw(Math.max(0, Math.min(at, m.frames.length - 1)));
      setPlaying(autoplay);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Replay unavailable");
      setActive(false);
    } finally {
      setPreparing(false);
    }
  }, [meta]);

  const exit = useCallback(() => {
    setActive(false);
    setPlaying(false);
    setState(null);
  }, []);

  // Deep link (?replay=1&frame=N): open paused at that frame.
  const autoStarted = useRef(false);
  useEffect(() => {
    if (autoStartAt === null || autoStarted.current) return;
    autoStarted.current = true;
    start(autoStartAt, false);
  }, [autoStartAt, start]);

  // Load the current frame (and prefetch the next few).
  useEffect(() => {
    if (!active || !meta) return;
    let cancelled = false;
    const load = async (i: number) => {
      if (cache.current.has(i) || i > last) return cache.current.get(i);
      const frame = await api.replayFrame(i);
      cache.current.set(i, frame);
      return frame;
    };
    load(index)
      .then((f) => !cancelled && f && setState(f))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Frame failed to load"));
    for (let k = 1; k <= 4; k++) load(index + k).catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [active, meta, index, last]);

  // Playback clock.
  useEffect(() => {
    if (!active || !playing || !meta) return;
    const id = window.setInterval(() => {
      setIndexRaw((i) => {
        if (i >= last) {
          setPlaying(false);
          return i;
        }
        return i + 1;
      });
    }, 1000 / speed);
    return () => window.clearInterval(id);
  }, [active, playing, speed, meta, last]);

  return { active, preparing, error, meta, index, playing, speed, state, start, exit, setIndex, setPlaying, setSpeed };
}

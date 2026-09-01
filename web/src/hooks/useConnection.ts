import { useCallback, useEffect, useRef, useState } from "react";
import { checkHealth, type ConnectionState } from "@/api/health";

const POLL_MS = 20_000;

/**
 * Polls GET /health so the sidebar can show a live connection indicator.
 * `baseUrlKey` changes whenever the user edits the API URL in Settings,
 * forcing an immediate re-check.
 */
export function useConnection(baseUrlKey: string) {
  const [state, setState] = useState<ConnectionState>("checking");
  const timer = useRef<number>();

  const runCheck = useCallback(async () => {
    setState((prev) => (prev === "online" ? prev : "checking"));
    const ok = await checkHealth();
    setState(ok ? "online" : "offline");
  }, []);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      const ok = await checkHealth();
      if (!cancelled) setState(ok ? "online" : "offline");
    };
    setState("checking");
    void tick();
    timer.current = window.setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer.current);
    };
  }, [baseUrlKey]);

  return { state, refresh: runCheck };
}

import type { ConnectionState } from "@/api/health";

const MAP: Record<ConnectionState, { label: string; dot: string; text: string }> = {
  online: { label: "Connected", dot: "bg-positive", text: "text-muted" },
  offline: { label: "Backend offline", dot: "bg-danger", text: "text-danger" },
  checking: { label: "Checking…", dot: "bg-warning animate-pulse", text: "text-muted" },
};

export function StatusDot({ state, showLabel = true }: { state: ConnectionState; showLabel?: boolean }) {
  const cfg = MAP[state];
  return (
    <span className={`inline-flex items-center gap-2 text-xs ${cfg.text}`}>
      <span className={`h-2 w-2 shrink-0 rounded-full ${cfg.dot}`} aria-hidden />
      {showLabel && <span>{cfg.label}</span>}
      {!showLabel && <span className="sr-only">{cfg.label}</span>}
    </span>
  );
}

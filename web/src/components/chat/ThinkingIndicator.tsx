import { useEffect, useState } from "react";
import { Search, BookOpen, PenLine } from "lucide-react";
import type { ThinkingStage } from "@/types";

const STAGES: Record<ThinkingStage, { label: string; Icon: typeof Search }> = {
  searching: { label: "Searching the document…", Icon: Search },
  reading: { label: "Reading relevant passages…", Icon: BookOpen },
  generating: { label: "Generating answer…", Icon: PenLine },
};

const ORDER: ThinkingStage[] = ["searching", "reading", "generating"];

export function ThinkingIndicator({ stage }: { stage: ThinkingStage }) {
  // Small mount animation so it doesn't pop in abruptly.
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const t = window.setTimeout(() => setShown(true), 10);
    return () => window.clearTimeout(t);
  }, []);

  return (
    <div
      className={`flex items-center gap-3 transition-opacity duration-200 ${shown ? "opacity-100" : "opacity-0"}`}
      role="status"
      aria-live="polite"
    >
      <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent/10 text-accent">
        <span className="block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
      </span>
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-1.5">
          {ORDER.map((s) => {
            const { Icon } = STAGES[s];
            const active = s === stage;
            const done = ORDER.indexOf(s) < ORDER.indexOf(stage);
            return (
              <Icon
                key={s}
                className={`h-3.5 w-3.5 transition-colors ${
                  active ? "text-accent" : done ? "text-muted" : "text-faint"
                }`}
                aria-hidden
              />
            );
          })}
        </div>
        <span className="text-[13px] text-muted">{STAGES[stage].label}</span>
      </div>
    </div>
  );
}

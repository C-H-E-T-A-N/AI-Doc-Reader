import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { X } from "lucide-react";

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  side?: "left" | "right";
  title?: string;
  children: ReactNode;
  /** Width utility class for the panel. */
  widthClass?: string;
}

export function Drawer({
  open,
  onClose,
  side = "left",
  title,
  children,
  widthClass = "max-w-[19rem]",
}: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    window.setTimeout(() => panelRef.current?.focus(), 0);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-black/50 animate-fade-in" onClick={onClose} aria-hidden />
      <div
        ref={panelRef}
        tabIndex={-1}
        className={`absolute inset-y-0 ${
          side === "left" ? "left-0" : "right-0"
        } w-full ${widthClass} bg-surface outline-none animate-slide-in-left ${
          side === "right" ? "border-l" : "border-r"
        } border-border`}
      >
        {title && (
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">{title}</h2>
            <button onClick={onClose} className="btn btn-ghost h-8 w-8 p-0" aria-label="Close">
              <X className="h-4 w-4" aria-hidden />
            </button>
          </div>
        )}
        <div className="h-full overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}

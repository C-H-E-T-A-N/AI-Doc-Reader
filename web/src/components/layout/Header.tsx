import { FileText, Menu, Settings } from "lucide-react";
import { ThemeToggle } from "@/components/common/ThemeToggle";
import type { Theme } from "@/types";

interface HeaderProps {
  theme: Theme;
  onToggleTheme: () => void;
  onOpenSettings: () => void;
  onOpenSidebar: () => void;
}

export function Header({ theme, onToggleTheme, onOpenSettings, onOpenSidebar }: HeaderProps) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-canvas px-3 sm:px-4">
      <div className="flex items-center gap-2">
        <button
          onClick={onOpenSidebar}
          className="btn btn-ghost h-9 w-9 p-0 lg:hidden"
          aria-label="Open documents"
        >
          <Menu className="h-4 w-4" aria-hidden />
        </button>
        <div className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent/10 text-accent">
            <FileText className="h-4 w-4" aria-hidden />
          </span>
          <div className="leading-tight">
            <span className="block text-sm font-semibold tracking-tight text-content">AI Doc Reader</span>
            <span className="hidden text-[11px] text-faint sm:block">Retrieval-augmented document Q&amp;A</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-1">
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        <button
          onClick={onOpenSettings}
          className="btn btn-ghost h-9 w-9 p-0"
          aria-label="Open settings"
          title="Settings"
        >
          <Settings className="h-4 w-4" aria-hidden />
        </button>
      </div>
    </header>
  );
}

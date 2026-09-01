import { Moon, Sun } from "lucide-react";
import type { Theme } from "@/types";

export function ThemeToggle({ theme, onToggle }: { theme: Theme; onToggle: () => void }) {
  const nextLabel = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
  return (
    <button onClick={onToggle} className="btn btn-ghost h-9 w-9 p-0" aria-label={nextLabel} title={nextLabel}>
      {theme === "dark" ? <Sun className="h-4 w-4" aria-hidden /> : <Moon className="h-4 w-4" aria-hidden />}
    </button>
  );
}

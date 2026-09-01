import { useState } from "react";
import { RotateCcw } from "lucide-react";
import { Modal } from "./Modal";
import { Button } from "./Button";
import { ThemeToggle } from "./ThemeToggle";
import { getBaseUrl, normalizeBaseUrl, resetBaseUrl, setBaseUrl } from "@/api/client";
import type { Theme } from "@/types";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  theme: Theme;
  onToggleTheme: () => void;
  onBaseUrlChange: (next: string) => void;
}

export function SettingsModal({ open, onClose, theme, onToggleTheme, onBaseUrlChange }: SettingsModalProps) {
  const [value, setValue] = useState(getBaseUrl());
  const [saved, setSaved] = useState(false);

  const commit = (next: string) => {
    const clean = normalizeBaseUrl(next);
    setBaseUrl(clean);
    setValue(clean);
    onBaseUrlChange(clean);
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1600);
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Settings"
      description="Connection and appearance. No credentials are stored in the browser."
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
          <Button size="sm" onClick={() => commit(value)}>
            {saved ? "Saved" : "Save"}
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        <div>
          <label htmlFor="api-url" className="text-xs font-medium text-content">
            Backend API URL
          </label>
          <div className="mt-1.5 flex gap-2">
            <input
              id="api-url"
              type="url"
              inputMode="url"
              spellCheck={false}
              className="field font-mono text-[13px]"
              placeholder="http://127.0.0.1:8000"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") commit(value);
              }}
            />
            <Button
              variant="outline"
              size="md"
              className="shrink-0 px-2.5"
              title="Reset to default"
              onClick={() => {
                const def = resetBaseUrl();
                setValue(def);
                onBaseUrlChange(def);
              }}
            >
              <RotateCcw className="h-4 w-4" aria-hidden />
            </Button>
          </div>
          <p className="mt-1.5 text-xs text-muted">
            The FastAPI server. Run it locally with{" "}
            <code className="rounded bg-surface-hover px-1 py-0.5 font-mono text-[11px]">
              uvicorn app.main:app
            </code>{" "}
            and keep this at <span className="font-mono">http://127.0.0.1:8000</span>.
          </p>
        </div>

        <div className="flex items-center justify-between border-t border-border pt-4">
          <div>
            <p className="text-xs font-medium text-content">Theme</p>
            <p className="mt-0.5 text-xs text-muted capitalize">{theme}</p>
          </div>
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      </div>
    </Modal>
  );
}

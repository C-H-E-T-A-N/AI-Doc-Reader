import type { ReactNode } from "react";

interface AppLayoutProps {
  header: ReactNode;
  sidebar: ReactNode;
  main: ReactNode;
  details?: ReactNode;
}

/**
 * Desktop:  header on top; sidebar | chat | (optional) details below.
 * < lg:     sidebar and details collapse to drawers (rendered by the caller);
 *           only the chat column shows here.
 */
export function AppLayout({ header, sidebar, main, details }: AppLayoutProps) {
  return (
    <div className="flex h-full flex-col">
      {header}
      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-[19rem] shrink-0 border-r border-border lg:block">{sidebar}</aside>
        <main className="flex min-w-0 flex-1">{main}</main>
        {details && (
          <aside className="hidden w-[18rem] shrink-0 border-l border-border xl:block">{details}</aside>
        )}
      </div>
    </div>
  );
}

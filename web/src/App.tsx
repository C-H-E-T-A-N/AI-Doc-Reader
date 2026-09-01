import { useCallback, useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { UploadModal } from "@/components/documents/UploadModal";
import { DocumentDetails } from "@/components/documents/DocumentDetails";
import { SettingsModal } from "@/components/common/SettingsModal";
import { Drawer } from "@/components/common/Drawer";
import { useTheme } from "@/hooks/useTheme";
import { useDocuments } from "@/hooks/useDocuments";
import { useConnection } from "@/hooks/useConnection";
import { getBaseUrl } from "@/api/client";

export default function App() {
  const { theme, toggle: toggleTheme } = useTheme();
  const [baseUrlKey, setBaseUrlKey] = useState(getBaseUrl());
  const { state: connection, refresh: refreshConnection } = useConnection(baseUrlKey);

  const {
    documents,
    selectedId,
    selected,
    loading,
    loadError,
    upload,
    select,
    refresh,
    uploadFile,
    clearUpload,
    remove,
    deletingId,
  } = useDocuments();

  const [uploadOpen, setUploadOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);

  const openUpload = useCallback(() => {
    clearUpload();
    setUploadOpen(true);
  }, [clearUpload]);

  const closeUpload = useCallback(() => {
    setUploadOpen(false);
    clearUpload();
  }, [clearUpload]);

  const handleBaseUrlChange = useCallback(
    (next: string) => {
      setBaseUrlKey(next);
      refreshConnection();
      void refresh();
    },
    [refresh, refreshConnection],
  );

  const handleSelect = useCallback(
    (id: string) => {
      select(id);
      setSidebarOpen(false);
    },
    [select],
  );

  const sidebar = (
    <Sidebar
      documents={documents}
      selectedId={selectedId}
      loading={loading}
      error={loadError}
      deletingId={deletingId}
      connection={connection}
      onSelect={handleSelect}
      onDelete={remove}
      onUploadClick={() => {
        setSidebarOpen(false);
        openUpload();
      }}
      onRefresh={() => {
        void refresh();
        refreshConnection();
      }}
      onOpenDetails={() => setDetailsOpen(true)}
      hasSelection={!!selected}
    />
  );

  return (
    <div className="h-full">
      <AppLayout
        header={
          <Header
            theme={theme}
            onToggleTheme={toggleTheme}
            onOpenSettings={() => setSettingsOpen(true)}
            onOpenSidebar={() => setSidebarOpen(true)}
          />
        }
        sidebar={sidebar}
        main={
          <ChatWindow
            document={selected}
            onUploadClick={openUpload}
            onOpenDetails={() => setDetailsOpen(true)}
            showDetailsButton={!!selected}
          />
        }
        details={selected ? <DocumentDetails doc={selected} /> : undefined}
      />

      {/* Mobile drawers */}
      <Drawer open={sidebarOpen} onClose={() => setSidebarOpen(false)} title="Documents">
        {sidebar}
      </Drawer>
      <Drawer
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        side="right"
        title="Document details"
      >
        {selected ? (
          <DocumentDetails doc={selected} />
        ) : (
          <p className="p-4 text-sm text-muted">No document selected.</p>
        )}
      </Drawer>

      <UploadModal
        open={uploadOpen}
        progress={upload}
        onClose={closeUpload}
        onUpload={(file) => void uploadFile(file)}
        onDone={closeUpload}
      />

      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        theme={theme}
        onToggleTheme={toggleTheme}
        onBaseUrlChange={handleBaseUrlChange}
      />
    </div>
  );
}

import { useState } from "react";
import { FileLibrary } from "./components/FileLibrary";
import { GeneratePanel } from "./components/GeneratePanel";
import { Sidebar } from "./components/Sidebar";
import { StatusBar } from "./components/StatusBar";
import { TasksPanel } from "./components/TasksPanel";
import { TaskProvider } from "./context/TaskContext";
import type { AppView } from "./types";

function AppContent() {
  const [activeView, setActiveView] = useState<AppView>("generate");
  const [refreshToken, setRefreshToken] = useState(0);

  const bumpRefresh = () => setRefreshToken((value) => value + 1);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <StatusBar />
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-6 overflow-hidden p-6 max-md:px-4 md:grid-cols-[240px_minmax(0,1fr)]">
        <Sidebar activeView={activeView} onChange={setActiveView} />
        <main className="flex min-h-0 min-w-0 flex-col overflow-hidden">
          {activeView === "generate" && (
            <GeneratePanel
              refreshToken={refreshToken}
              onViewTasks={() => setActiveView("tasks")}
            />
          )}
          {activeView === "tasks" && <TasksPanel onGenerated={bumpRefresh} />}
          {activeView === "transcripts" && (
            <FileLibrary
              kind="transcripts"
              refreshToken={refreshToken}
              onFilesChanged={bumpRefresh}
              onViewTasks={() => setActiveView("tasks")}
            />
          )}
          {activeView === "templates" && (
            <FileLibrary
              kind="templates"
              refreshToken={refreshToken}
              onFilesChanged={bumpRefresh}
              onViewTasks={() => setActiveView("tasks")}
            />
          )}
          {activeView === "minutes" && (
            <FileLibrary kind="minutes" refreshToken={refreshToken} />
          )}
        </main>
      </div>
    </div>
  );
}

function App() {
  return (
    <TaskProvider>
      <AppContent />
    </TaskProvider>
  );
}

export default App;

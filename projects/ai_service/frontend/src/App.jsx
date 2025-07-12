import React, { useState } from "react";
import "./theme.css";
import Sidebar from "./componens/ModelManager";
import ChatBox from "./componens/ChatBox";
import InputArea from "./componens/InputArea";
import QuickActionsDropdown from "./componens/modals/QuickActionsDropdown";

function App() {
  // Example state for models and selected model
  const [models, setModels] = useState([
    {
      id: "mistral-7b-v1",
      name: "Mistral 7B",
      icon: "🤖",
      state: "online",
      version: "v1.2.3",
    },
    {
      id: "phi-2",
      name: "Phi-2",
      icon: "🧠",
      state: "busy",
      version: "v0.9.1",
    },
  ]);
  const [selectedModel, setSelectedModel] = useState(models[0].id);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [quickActionsOpen, setQuickActionsOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null); // {action, onConfirm}

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--chat-bg)" }}>
      {/* Sidebar */}
      {sidebarOpen && (
        <Sidebar
          models={models}
          selectedModel={selectedModel}
          setSelectedModel={setSelectedModel}
          setModels={setModels}
          onCollapse={() => setSidebarOpen(false)}
        />
      )}
      {/* Main area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        {/* Top bar */}
        <div style={{ background: "var(--topbar-bg)", color: "var(--modal-header-text)", height: 48, display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid var(--border)", padding: "0 16px" }}>
          <div style={{ display: "flex", alignItems: "center" }}>
            {!sidebarOpen && (
              <button onClick={() => setSidebarOpen(true)} style={{ marginRight: 12, background: "none", border: "none", color: "var(--sidebar-text)", fontSize: 18, cursor: "pointer", verticalAlign: "middle" }}>⏵</button>
            )}
            <span style={{ fontWeight: 600 }}>{models.find((m) => m.id === selectedModel)?.name}</span>
            <span style={{ marginLeft: 12, fontSize: 12, color: "#aaa" }}>{models.find((m) => m.id === selectedModel)?.version}</span>
          </div>
          {/* Quick Actions Dropdown */}
          <div style={{ position: "relative" }}>
            {quickActionsOpen && (
              <div
                style={{
                  position: "fixed",
                  top: 0,
                  left: 0,
                  width: "100vw",
                  height: "100vh",
                  zIndex: 99,
                  background: "transparent",
                }}
                onClick={() => setQuickActionsOpen(false)}
              />
            )}
            <span
              style={{ cursor: "pointer", padding: "4px 12px", background: "var(--quickaction-bg)", borderRadius: 4, position: "relative", zIndex: 100 }}
              onClick={() => setQuickActionsOpen((v) => !v)}
            >
              Quick Actions ▼
            </span>
            {quickActionsOpen && (
              <QuickActionsDropdown
                onClose={() => setQuickActionsOpen(false)}
                onAction={(action) => {
                  if (["restart", "reboot"].includes(action)) {
                    setConfirmAction({
                      action,
                      onConfirm: () => {
                        setConfirmAction(null);
                        setQuickActionsOpen(false);
                        alert(action + " confirmed!");
                      },
                    });
                  } else {
                    setQuickActionsOpen(false);
                    alert(action + " triggered!");
                  }
                }}
              />
            )}
            {confirmAction && (
              <div style={{
                position: "fixed",
                top: 0,
                left: 0,
                width: "100vw",
                height: "100vh",
                background: "rgba(0,0,0,0.4)",
                zIndex: 200,
                display: "flex",
                alignItems: "center",
                justifyContent: "center"
              }}>
                <div style={{ background: "var(--modal-bg)", border: "1px solid var(--modal-border)", borderRadius: 8, padding: 24, minWidth: 320, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                  <div style={{ marginBottom: 12, textAlign: "center" }}>Are you sure you want to {confirmAction.action}?</div>
                  <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
                    <button onClick={confirmAction.onConfirm} style={{ background: "var(--sidebar-icon)", color: "#fff", border: "none", borderRadius: 4, padding: "6px 16px" }}>Yes</button>
                    <button onClick={() => setConfirmAction(null)} style={{ background: "#444", color: "#fff", border: "none", borderRadius: 4, padding: "6px 16px" }}>Cancel</button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
        {/* Chat area */}
        <div style={{ flex: 1, overflow: "auto", display: "flex", flexDirection: "column" }}>
          <ChatBox modelId={selectedModel} />
        </div>
        {/* Input area */}
        <InputArea modelId={selectedModel} />
      </div>
      {/* Sidebar collapsed arrow */}
      {!sidebarOpen && (
        <div style={{ width: 32, background: "var(--sidebar-bg)", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", borderRight: "1px solid var(--border)" }} onClick={() => setSidebarOpen(true)}>
          <span style={{ color: "var(--sidebar-text)", fontSize: 18 }}>⏴</span>
        </div>
      )}
    </div>
  );
}

export default App;

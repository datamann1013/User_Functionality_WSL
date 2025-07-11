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
          <div>
            <button onClick={() => setSidebarOpen((v) => !v)} style={{ marginRight: 12 }}>
              {sidebarOpen ? "⏴" : "⏵"}
            </button>
            <span style={{ fontWeight: 600 }}>{models.find((m) => m.id === selectedModel)?.name}</span>
            <span style={{ marginLeft: 12, fontSize: 12, color: "#aaa" }}>{models.find((m) => m.id === selectedModel)?.version}</span>
          </div>
          {/* Quick Actions Dropdown */}
          <div style={{ position: "relative" }}>
            <span
              style={{ cursor: "pointer", padding: "4px 12px", background: "var(--quickaction-bg)", borderRadius: 4 }}
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
              <div style={{ position: "absolute", right: 0, top: 40, background: "var(--modal-bg)", border: "1px solid var(--modal-border)", borderRadius: 8, padding: 16, zIndex: 100 }}>
                <div style={{ marginBottom: 12 }}>Are you sure you want to {confirmAction.action}?</div>
                <button onClick={confirmAction.onConfirm} style={{ background: "var(--sidebar-icon)", color: "#fff", border: "none", borderRadius: 4, padding: "6px 16px", marginRight: 8 }}>Yes</button>
                <button onClick={() => setConfirmAction(null)} style={{ background: "#444", color: "#fff", border: "none", borderRadius: 4, padding: "6px 16px" }}>Cancel</button>
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
    </div>
  );
}

export default App;

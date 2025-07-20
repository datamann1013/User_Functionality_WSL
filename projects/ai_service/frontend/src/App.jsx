import React, { useState, useEffect } from "react";
import "./theme.css";
import Sidebar from "./componens/ModelManager";
import QuickActionsDropdown from "./componens/modals/QuickActionsDropdown";
import InputArea from "./componens/InputArea";

function App() {
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
  const [confirmAction, setConfirmAction] = useState(null);
  const [messages, setMessages] = useState([]);
  const [modalContent, setModalContent] = useState(null);
  const [connecting, setConnecting] = useState(true);
  const [thinking, setThinking] = useState(false);

  // On mount, check backend connection
  useEffect(() => {
    async function checkBackend() {
      try {
        await fetch("/health");
        setConnecting(false);
      } catch {
        setConnecting(true);
      }
    }
    checkBackend();
  }, []);

  async function handleSend(msg) {
    if (connecting) return;
    setThinking(true);
    setMessages((prev) => [...prev, { ...msg, sender: "user", id: Date.now() + Math.random() }]);
    setMessages((prev) => [...prev, { sender: "ai", text: "[thinking]", id: Date.now() + Math.random() }]);
    try {
      const res = await fetch("/api/inference/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: msg.text, modelId: selectedModel }),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev.slice(0, -1), // Remove the last [thinking] message
        { sender: "ai", text: data.result, id: Date.now() + Math.random() },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { sender: "ai", text: "[Error: Could not reach backend]", id: Date.now() + Math.random() },
      ]);
    }
    setThinking(false);
  }

  function renderBubble(msg) {
    const isUser = msg.sender === "user";
    const bubbleStyle = {
      background: isUser ? "var(--chat-user-bg)" : "var(--chat-ai-bg)",
      color: "var(--chat-text)",
      alignSelf: isUser ? "flex-end" : "flex-start",
      borderRadius: 12,
      padding: "10px 16px",
      margin: "6px 0",
      maxWidth: "70%",
      whiteSpace: "pre-wrap",
      wordBreak: "break-word",
      position: "relative",
      cursor: msg.type === "code" && msg.text && msg.text.split("\n").length > 20 ? "pointer" : "default",
    };
    if (msg.file) {
      return (
        <div style={bubbleStyle}>
          <span style={{ marginRight: 8, color: "var(--file-attachment-icon)" }}>📄</span>
          <span>{msg.file.name || msg.file}</span>
          {msg.file.type && <span style={{ marginLeft: 8, fontSize: 12, color: "#aaa" }}>{msg.file.type}</span>}
          {msg.metadata && Object.keys(msg.metadata).length > 0 && (
            <span style={{ marginLeft: 12, fontSize: 12, color: "#43b581", background: "#23272a", borderRadius: 4, padding: "2px 6px" }}>
              {Object.entries(msg.metadata).map(([k, v]) => `${k}: ${v}`).join(", ")}
            </span>
          )}
        </div>
      );
    }
    if (msg.type === "code") {
      const lines = msg.text.split("\n").length;
      if (lines > 20) {
        return (
          <div style={bubbleStyle} onClick={() => setModalContent(msg)}>
            <span style={{ fontStyle: "italic", color: "#aaa" }}>[Long code block, click to expand]</span>
          </div>
        );
      }
      return (
        <pre style={{ ...bubbleStyle, fontFamily: "monospace", background: "#18191c" }}>{msg.text}</pre>
      );
    }
    if (msg.type === "markdown") {
      return (
        <div style={bubbleStyle}>{msg.text}</div>
      );
    }
    return (
      <div style={bubbleStyle}>
        {msg.text}
        {msg.metadata && Object.keys(msg.metadata).length > 0 && (
          <span style={{ marginLeft: 12, fontSize: 12, color: "#43b581", background: "#23272a", borderRadius: 4, padding: "2px 6px" }}>
            {Object.entries(msg.metadata).map(([k, v]) => `${k}: ${v}`).join(", ")}
          </span>
        )}
      </div>
    );
  }

  function Modal() {
    if (!modalContent) return null;
    return (
      <div style={{ position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh", background: "rgba(0,0,0,0.4)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }} onClick={() => setModalContent(null)}>
        <div style={{ background: "var(--modal-bg)", border: "1px solid var(--modal-border)", borderRadius: 8, padding: 24, minWidth: 400, maxWidth: 800, maxHeight: "80vh", overflow: "auto" }} onClick={e => e.stopPropagation()}>
          {modalContent.type === "file" ? (
            <div>
              <h3>{modalContent.filename}</h3>
              <pre style={{ background: "#18191c", color: "#fff", padding: 12 }}>{modalContent.text || "[File content preview here]"}</pre>
            </div>
          ) : (
            <pre style={{ background: "#18191c", color: "#fff", padding: 12 }}>{modalContent.text}</pre>
          )}
          <button onClick={() => setModalContent(null)} style={{ marginTop: 16, background: "var(--sidebar-icon)", color: "#fff", border: "none", borderRadius: 4, padding: "6px 16px" }}>Close</button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--chat-bg)", width: "100vw", minHeight: 0, minWidth: 0, boxSizing: 'border-box' }}>
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
        <div style={{ flex: 1, overflow: "auto", display: "flex", flexDirection: "column", padding: 24 }}>
          {connecting ? (
            <div style={{ color: "#aaa", textAlign: "center", marginTop: 40, fontSize: 18 }}>Connecting...</div>
          ) : (
            messages.map((msg) => (
              <div key={msg.id} style={{ display: "flex", flexDirection: "column", alignItems: msg.sender === "user" ? "flex-end" : "flex-start" }}>
                {renderBubble(msg)}
              </div>
            ))
          )}
          <Modal />
        </div>
        {/* Input area at the bottom */}
        <InputArea modelId={selectedModel} onSend={handleSend} disabled={connecting || thinking} />
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

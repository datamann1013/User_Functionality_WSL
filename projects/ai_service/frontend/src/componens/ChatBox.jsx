import React, { useState } from "react";
import InputArea from "./InputArea";
// For markdown rendering, you can use 'react-markdown' and 'react-syntax-highlighter' if available
// import ReactMarkdown from 'react-markdown';
// import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';

// Dummy chat data for demonstration
const initialMessages = [
  { id: 1, sender: "user", text: "Hello!", type: "text" },
  { id: 2, sender: "ai", text: "Hi! How can I help you?", type: "text" },
  { id: 3, sender: "user", text: "```js\nconsole.log('test');\n```", type: "code", language: "js" },
  { id: 4, sender: "ai", text: "Here is a markdown example:\n\n**Bold** and _italic_!", type: "markdown" },
  { id: 5, sender: "user", text: "file.md", type: "file", filetype: "md", filename: "file.md" },
];

function ChatBox({ modelId }) {
  const [messages, setMessages] = useState([]);
  const [modalContent, setModalContent] = useState(null);

  async function handleSend(msg) {
    // Add user message
    const userMsg = { ...msg, sender: "user", id: Date.now() + Math.random() };
    setMessages((prev) => [...prev, userMsg]);
    // Call backend for AI response
    try {
      const res = await fetch("/api/inference/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: msg.text, modelId }),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { sender: "ai", text: data.result, id: Date.now() + Math.random() },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { sender: "ai", text: "[Error: Could not reach backend]", id: Date.now() + Math.random() },
      ]);
    }
  }

  // Render a chat bubble
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
    // File reference
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
    // Code block (show modal if >20 lines)
    if (msg.type === "code") {
      const lines = msg.text.split("\n").length;
      if (lines > 20) {
        return (
          <div style={bubbleStyle} onClick={() => setModalContent(msg)}>
            <span style={{ fontStyle: "italic", color: "#aaa" }}>[Long code block, click to expand]</span>
          </div>
        );
      }
      // For real use, render with syntax highlighting
      return (
        <pre style={{ ...bubbleStyle, fontFamily: "monospace", background: "#18191c" }}>{msg.text}</pre>
      );
    }
    // Markdown
    if (msg.type === "markdown") {
      // For real use, render with ReactMarkdown
      return (
        <div style={bubbleStyle}>{msg.text}</div>
      );
    }
    // Plain text
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

  // Modal for long code or file
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
    <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: 24, overflowY: "auto" }}>
      {messages.map((msg) => (
        <div key={msg.id} style={{ display: "flex", flexDirection: "column", alignItems: msg.sender === "user" ? "flex-end" : "flex-start" }}>
          {renderBubble(msg)}
        </div>
      ))}
      <Modal />
      {/* Input area at the bottom */}
      <div style={{ marginTop: 16 }}>
        <InputArea modelId={modelId} onSend={handleSend} />
      </div>
    </div>
  );
}

export default ChatBox;

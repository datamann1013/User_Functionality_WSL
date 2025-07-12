import React, { useRef, useState } from "react";

const SLASH_COMMANDS = [
  "/reset",
  "/info",
  "/reboot",
  "/help",
  "/explain",
  "/test",
  "/dev",
  "/assist",
  "/locate",
];

function InputArea({ modelId, onSend }) {
  const [value, setValue] = useState("");
  const [showCommands, setShowCommands] = useState(false);
  const [filteredCommands, setFilteredCommands] = useState(SLASH_COMMANDS);
  const [fileDrag, setFileDrag] = useState(false);
  const [file, setFile] = useState(null);
  const [metadata, setMetadata] = useState("");
  const textareaRef = useRef();

  // Handle input change and slash command logic
  function handleChange(e) {
    const val = e.target.value;
    setValue(val);
    if (val.startsWith("/")) {
      setShowCommands(true);
      setFilteredCommands(SLASH_COMMANDS.filter(cmd => cmd.startsWith(val)));
    } else {
      setShowCommands(false);
    }
  }

  // Handle file drop
  function handleDrop(e) {
    e.preventDefault();
    setFileDrag(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      setFile(files[0]);
    }
  }

  // Handle file picker
  function handleFileChange(e) {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
      setFile(files[0]);
    }
  }

  // Handle send
  async function handleSend() {
    if (!value.trim() && !file) return;
    let fileRef = null;
    if (file) {
      // Simulate upload, in real app upload to server and get URL/ID
      fileRef = { name: file.name, type: file.type, size: file.size };
    }
    const metaObj = metadata ? { tag: metadata } : {};
    if (onSend) {
      onSend({ text: value, file: fileRef, metadata: metaObj });
    }
    setValue("");
    setFile(null);
    setMetadata("");
  }

  // Multiline auto-expand (up to 3 lines)
  function handleInput(e) {
    const textarea = textareaRef.current;
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 60) + "px";
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        placeholder="Type a message..."
        style={{ resize: "none", width: "100%", minHeight: 40, background: "var(--input-bg)", color: "var(--input-text)", border: "1px solid var(--input-border)", borderRadius: 4, padding: "8px 10px" }}
        onDrop={handleDrop}
        onDragOver={e => { e.preventDefault(); setFileDrag(true); }}
        onDragLeave={e => { e.preventDefault(); setFileDrag(false); }}
      />
      {file && (
        <div style={{ color: "var(--file-attachment-icon)", fontSize: 14 }}>
          Attached: {file.name} <button onClick={() => setFile(null)} style={{ marginLeft: 8 }}>Remove</button>
        </div>
      )}
      <input
        type="text"
        value={metadata}
        onChange={e => setMetadata(e.target.value)}
        placeholder="Add a tag or metadata (optional)"
        style={{ width: "100%", background: "var(--input-bg)", color: "var(--input-text)", border: "1px solid var(--input-border)", borderRadius: 4, padding: "6px 10px" }}
      />
      <div style={{ display: "flex", gap: 8 }}>
        <input type="file" style={{ display: "none" }} id="file-upload" onChange={handleFileChange} />
        <label htmlFor="file-upload" style={{ background: "var(--file-attachment-bg)", color: "var(--file-attachment-icon)", borderRadius: 4, padding: "6px 12px", cursor: "pointer" }}>Attach File</label>
        <button onClick={handleSend} style={{ background: "var(--sidebar-icon)", color: "#fff", border: "none", borderRadius: 4, padding: "8px 20px", fontWeight: 600 }}>Send</button>
      </div>
      {/* Slash command suggestion box */}
      {showCommands && filteredCommands.length > 0 && (
        <div style={{
          position: "absolute",
          left: 12,
          bottom: 48,
          background: "var(--modal-bg)",
          color: "var(--modal-header-text)",
          border: "1px solid var(--modal-border)",
          borderRadius: 6,
          boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
          zIndex: 10,
          minWidth: 180,
        }}>
          {filteredCommands.map(cmd => (
            <div key={cmd} style={{ padding: "8px 12px", cursor: "pointer" }} onClick={() => { setValue(cmd + " "); setShowCommands(false); }}>
              {cmd}
            </div>
          ))}
        </div>
      )}
      {/* Drag overlay */}
      {fileDrag && (
        <div style={{ position: "absolute", left: 0, top: 0, width: "100%", height: "100%", background: "rgba(114,137,218,0.15)", border: "2px dashed var(--sidebar-icon)", borderRadius: 8, zIndex: 20, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--sidebar-icon)", fontSize: 20 }}>
          Drop files to upload
        </div>
      )}
    </div>
  );
}

export default InputArea;

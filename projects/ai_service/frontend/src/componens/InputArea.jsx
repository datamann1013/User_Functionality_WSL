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

function InputArea({ modelId }) {
  const [value, setValue] = useState("");
  const [showCommands, setShowCommands] = useState(false);
  const [filteredCommands, setFilteredCommands] = useState(SLASH_COMMANDS);
  const [fileDrag, setFileDrag] = useState(false);
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
    // TODO: handle file upload logic
    alert("File(s) uploaded: " + files.map(f => f.name).join(", "));
  }

  // Handle file picker
  function handleFileChange(e) {
    const files = Array.from(e.target.files);
    // TODO: handle file upload logic
    alert("File(s) uploaded: " + files.map(f => f.name).join(", "));
  }

  // Multiline auto-expand (up to 3 lines)
  function handleInput(e) {
    const textarea = textareaRef.current;
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 60) + "px";
  }

  return (
    <div
      style={{
        background: "var(--input-bg)",
        borderTop: "1px solid var(--input-border)",
        padding: 12,
        display: "flex",
        alignItems: "flex-end",
        position: "relative",
      }}
      onDragOver={e => { e.preventDefault(); setFileDrag(true); }}
      onDragLeave={e => { e.preventDefault(); setFileDrag(false); }}
      onDrop={handleDrop}
    >
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onInput={handleInput}
        rows={1}
        style={{
          flex: 1,
          resize: "none",
          minHeight: 32,
          maxHeight: 60,
          background: "var(--input-bg)",
          color: "var(--input-text)",
          border: "none",
          outline: "none",
          fontSize: 16,
          borderRadius: 6,
          padding: "8px 12px",
        }}
        placeholder="Type a message or / for commands..."
      />
      <input
        type="file"
        style={{ display: "none" }}
        id="file-upload"
        multiple
        onChange={handleFileChange}
      />
      <label htmlFor="file-upload" style={{ marginLeft: 8, cursor: "pointer", color: "var(--sidebar-icon)", fontSize: 22 }} title="Attach file">
        📎
      </label>
      <button
        style={{ marginLeft: 8, background: "var(--sidebar-icon)", color: "#fff", border: "none", borderRadius: 4, padding: "8px 18px", fontWeight: 600, fontSize: 16, cursor: "pointer" }}
        onClick={() => { setValue(""); }}
      >
        Send
      </button>
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


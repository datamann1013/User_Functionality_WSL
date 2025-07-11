import React from "react";

const actions = [
  { key: "restart", label: "Restart" },
  { key: "reboot", label: "Reboot" },
  { key: "info", label: "Info" },
  { key: "version", label: "Choose Version" },
];

function QuickActionsDropdown({ onClose, onAction }) {
  return (
    <div style={{
      position: "absolute",
      right: 0,
      top: 36,
      background: "var(--modal-bg)",
      color: "var(--modal-header-text)",
      border: "1px solid var(--modal-border)",
      borderRadius: 8,
      boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
      zIndex: 100,
      minWidth: 180,
    }}>
      {actions.map(a => (
        <div
          key={a.key}
          style={{ padding: "10px 16px", cursor: "pointer", borderBottom: a.key !== "version" ? "1px solid var(--border)" : "none" }}
          onClick={() => { onAction(a.key); onClose(); }}
        >
          {a.label}
        </div>
      ))}
    </div>
  );
}

export default QuickActionsDropdown;


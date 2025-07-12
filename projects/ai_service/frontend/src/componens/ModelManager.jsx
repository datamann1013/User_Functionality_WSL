import React, { useState } from "react";
import EditModelsModal from "./modals/EditModelsModal";

const stateColors = {
  online: "var(--sidebar-state-online)",
  busy: "var(--sidebar-state-busy)",
  error: "var(--sidebar-state-error)",
  offline: "var(--sidebar-state-offline)",
};

function ModelManager({ models, selectedModel, setSelectedModel, setModels, onCollapse }) {
  const [editModalOpen, setEditModalOpen] = useState(false);

  return (
    <div style={{ width: 260, background: "var(--sidebar-bg)", color: "var(--sidebar-text)", display: "flex", flexDirection: "column", height: "100vh", borderRight: "1px solid var(--border)" }}>
      <div style={{ height: 48, padding: 16, borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", boxSizing: "border-box" }}>
        <span style={{ fontWeight: 700, fontSize: 16 }}>Models</span>
        <button onClick={onCollapse} style={{ background: "none", border: "none", color: "var(--sidebar-text)", fontSize: 18, cursor: "pointer" }}>⏴</button>
      </div>
      <button style={{ margin: 12, padding: "8px 0", background: "var(--sidebar-icon)", color: "#fff", border: "none", borderRadius: 4, fontWeight: 600, cursor: "pointer" }} onClick={() => setEditModalOpen(true)}>
        Edit Models
      </button>
      <div style={{ flex: 1, overflowY: "auto" }}>
        {models.map((model, idx) => (
          <React.Fragment key={model.id}>
            <div
              onClick={() => setSelectedModel(model.id)}
              style={{
                display: "flex",
                alignItems: "center",
                padding: "10px 16px",
                background: selectedModel === model.id ? "rgba(114,137,218,0.15)" : "none",
                cursor: "pointer",
                borderRadius: 4,
                margin: "2px 8px",
              }}
            >
              <span style={{ fontSize: 22, marginRight: 10 }}>{model.icon}</span>
              <span style={{ fontWeight: 500, flex: 1 }}>{model.name}</span>
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: stateColors[model.state] || stateColors.offline, marginRight: 6, display: "inline-block" }}></span>
              <span style={{ fontSize: 12, color: "#bbb" }}>{model.state.charAt(0).toUpperCase() + model.state.slice(1)}</span>
            </div>
            {idx < models.length - 1 && <div style={{ height: 1, background: "var(--border)", margin: "0 16px" }} />}
          </React.Fragment>
        ))}
      </div>
      {editModalOpen && <EditModelsModal models={models} setModels={setModels} onClose={() => setEditModalOpen(false)} />}
    </div>
  );
}

export default ModelManager;

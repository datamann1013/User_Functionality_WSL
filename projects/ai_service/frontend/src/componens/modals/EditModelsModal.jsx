import React, { useState } from "react";

function EditModelsModal({ models, setModels, onClose }) {
  const [mode, setMode] = useState(null); // 'edit' or 'create'
  const [selected, setSelected] = useState(null);

  // Modal for editing/creating a model
  function ModelOptionsModal({ model, onSave, onCancel }) {
    const [form, setForm] = useState(model || { name: "", icon: "", state: "offline", version: "v1.0.0" });
    return (
      <div style={{ background: "var(--modal-bg)", border: "1px solid var(--modal-border)", borderRadius: 8, padding: 24, minWidth: 320 }}>
        <h3 style={{ marginTop: 0 }}>{model ? "Edit Model" : "Create Model"}</h3>
        <label>Name:<input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} style={{ width: "100%" }} /></label><br />
        <label>Icon:<input value={form.icon} onChange={e => setForm({ ...form, icon: e.target.value })} style={{ width: "100%" }} /></label><br />
        <label>State:
          <select value={form.state} onChange={e => setForm({ ...form, state: e.target.value })}>
            <option value="online">Online</option>
            <option value="busy">Busy</option>
            <option value="error">Error</option>
            <option value="offline">Offline</option>
          </select>
        </label><br />
        <label>Version:<input value={form.version} onChange={e => setForm({ ...form, version: e.target.value })} style={{ width: "100%" }} /></label><br />
        <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
          <button onClick={() => onSave(form)} style={{ background: "var(--sidebar-icon)", color: "#fff", border: "none", borderRadius: 4, padding: "6px 16px" }}>Save</button>
          <button onClick={onCancel} style={{ background: "#444", color: "#fff", border: "none", borderRadius: 4, padding: "6px 16px" }}>Cancel</button>
        </div>
      </div>
    );
  }

  // Modal for selecting a model to edit
  function SelectModelModal({ models, onSelect, onCancel }) {
    return (
      <div style={{ background: "var(--modal-bg)", border: "1px solid var(--modal-border)", borderRadius: 8, padding: 24, minWidth: 320 }}>
        <h3 style={{ marginTop: 0 }}>Select Model to Edit</h3>
        {models.map(m => (
          <div key={m.id} style={{ display: "flex", alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontSize: 22, marginRight: 10 }}>{m.icon}</span>
            <span style={{ flex: 1 }}>{m.name}</span>
            <button onClick={() => onSelect(m)} style={{ background: "var(--sidebar-icon)", color: "#fff", border: "none", borderRadius: 4, padding: "4px 12px" }}>Edit</button>
          </div>
        ))}
        <button onClick={onCancel} style={{ marginTop: 16, background: "#444", color: "#fff", border: "none", borderRadius: 4, padding: "6px 16px" }}>Back</button>
      </div>
    );
  }

  // Modal root
  return (
    <div style={{ position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh", background: "rgba(0,0,0,0.4)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div>
        {!mode && (
          <div style={{ background: "var(--modal-bg)", border: "1px solid var(--modal-border)", borderRadius: 8, padding: 24, minWidth: 320 }}>
            <h2>Edit Models</h2>
            <button onClick={() => setMode("edit")} style={{ margin: 8, background: "var(--sidebar-icon)", color: "#fff", border: "none", borderRadius: 4, padding: "8px 16px" }}>Edit Existing</button>
            <button onClick={() => setMode("create")} style={{ margin: 8, background: "var(--sidebar-icon)", color: "#fff", border: "none", borderRadius: 4, padding: "8px 16px" }}>Create New</button>
            <button onClick={onClose} style={{ margin: 8, background: "#444", color: "#fff", border: "none", borderRadius: 4, padding: "8px 16px" }}>Close</button>
          </div>
        )}
        {mode === "edit" && !selected && (
          <SelectModelModal models={models} onSelect={m => { setSelected(m); }} onCancel={() => setMode(null)} />
        )}
        {((mode === "edit" && selected) || mode === "create") && (
          <ModelOptionsModal
            model={mode === "edit" ? selected : null}
            onSave={form => {
              if (mode === "edit") {
                setModels(models.map(m => m.id === selected.id ? { ...m, ...form } : m));
              } else {
                setModels([...models, { ...form, id: form.name.toLowerCase().replace(/\s+/g, "-") }]);
              }
              setMode(null); setSelected(null); onClose();
            }}
            onCancel={() => { setMode(null); setSelected(null); }}
          />
        )}
      </div>
    </div>
  );
}

export default EditModelsModal;


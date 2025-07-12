import React, { useState } from "react";

function EditModelsModal({ models, setModels, onClose }) {
  const [mode, setMode] = useState(null); // 'edit' or 'create'
  const [selected, setSelected] = useState(null);

  // Modal for editing/creating a model
  function ModelOptionsModal({ model, onSave, onCancel }) {
    const [form, setForm] = useState(model || {
      name: "",
      type: "assistant",
      icon: "",
      tags: [],
      special_slash: [],
      state: "offline",
      version: "v1.0.0",
      versions: [],
    });
    const [newVersion, setNewVersion] = useState({ version: '', notes: '' });
    return (
      <div style={{ background: "var(--modal-bg)", border: "1px solid var(--modal-border)", borderRadius: 8, padding: 24, minWidth: 320 }}>
        <h3 style={{ marginTop: 0, color: "var(--modal-header-text)", textAlign: "center" }}>{model ? "Edit Model" : "Create Model"}</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <label style={{ color: "var(--modal-header-text)", fontWeight: 500 }}>Name:
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
              style={{ width: "100%", minWidth: 0, boxSizing: 'border-box', background: "var(--input-bg)", color: "var(--input-text)", border: "1px solid var(--input-border)", borderRadius: 4, padding: "8px 10px", marginTop: 4 }} />
          </label>
          <label style={{ color: "var(--modal-header-text)", fontWeight: 500 }}>Type:
            <select value={form.type} onChange={e => setForm({ ...form, type: e.target.value })}
              style={{ width: "100%", minWidth: 0, boxSizing: 'border-box', background: "var(--input-bg)", color: "var(--input-text)", border: "1px solid var(--input-border)", borderRadius: 4, padding: "8px 10px", marginTop: 4 }}>
              <option value="assistant">Assistant</option>
              <option value="trainer">Trainer</option>
              <option value="custom">Custom</option>
            </select>
          </label>
          <label style={{ color: "var(--modal-header-text)", fontWeight: 500 }}>Icon:
            <input value={form.icon} onChange={e => setForm({ ...form, icon: e.target.value })}
              style={{ width: "100%", minWidth: 0, boxSizing: 'border-box', background: "var(--input-bg)", color: "var(--input-text)", border: "1px solid var(--input-border)", borderRadius: 4, padding: "8px 10px", marginTop: 4 }} />
          </label>
          <label style={{ color: "var(--modal-header-text)", fontWeight: 500 }}>Tags:
            <input value={(form.tags || []).join(", ")} onChange={e => setForm({ ...form, tags: e.target.value.split(/,\s*/) })}
              style={{ width: "100%", minWidth: 0, boxSizing: 'border-box', background: "var(--input-bg)", color: "var(--input-text)", border: "1px solid var(--input-border)", borderRadius: 4, padding: "8px 10px", marginTop: 4 }} placeholder="comma separated" />
          </label>
          <label style={{ color: "var(--modal-header-text)", fontWeight: 500 }}>Special Slash Commands:
            <input value={(form.special_slash || []).join(", ")} onChange={e => setForm({ ...form, special_slash: e.target.value.split(/,\s*/) })}
              style={{ width: "100%", minWidth: 0, boxSizing: 'border-box', background: "var(--input-bg)", color: "var(--input-text)", border: "1px solid var(--input-border)", borderRadius: 4, padding: "8px 10px", marginTop: 4 }} placeholder="comma separated" />
          </label>
          <label style={{ color: "var(--modal-header-text)", fontWeight: 500 }}>State:
            <select value={form.state} onChange={e => setForm({ ...form, state: e.target.value })}
              style={{ width: "100%", minWidth: 0, boxSizing: 'border-box', background: "var(--input-bg)", color: "var(--input-text)", border: "1px solid var(--input-border)", borderRadius: 4, padding: "8px 10px", marginTop: 4 }}>
              <option value="online">Online</option>
              <option value="busy">Busy</option>
              <option value="error">Error</option>
              <option value="offline">Offline</option>
            </select>
          </label>
          <label style={{ color: "var(--modal-header-text)", fontWeight: 500 }}>Version:
            <select value={form.version} onChange={e => setForm({ ...form, version: e.target.value })}
              style={{ width: "100%", minWidth: 0, boxSizing: 'border-box', background: "var(--input-bg)", color: "var(--input-text)", border: "1px solid var(--input-border)", borderRadius: 4, padding: "8px 10px", marginTop: 4 }}>
              {(form.versions || []).map((v, i) => (
                <option key={i} value={v.version}>{v.version} {v.notes ? `- ${v.notes}` : ''}</option>
              ))}
              {/* Allow custom version entry if not in list */}
              {form.version && !(form.versions || []).some(v => v.version === form.version) && (
                <option value={form.version}>{form.version} (custom)</option>
              )}
            </select>
          </label>
        </div>
        {/* Versions list */}
        <div style={{ margin: "18px 0 0 0" }}>
          <b style={{ color: "var(--modal-header-text)" }}>Versions:</b>
          <ul style={{ paddingLeft: 18, color: "var(--modal-header-text)" }}>
            {(form.versions || []).map((v, i) => (
              <li key={i}><b>{v.version}</b>: {v.notes}</li>
            ))}
          </ul>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input placeholder="New version" value={newVersion.version} onChange={e => setNewVersion({ ...newVersion, version: e.target.value })}
              style={{ width: 90, background: "var(--input-bg)", color: "var(--input-text)", border: "1px solid var(--input-border)", borderRadius: 4, padding: "6px 8px" }} />
            <input placeholder="Notes" value={newVersion.notes} onChange={e => setNewVersion({ ...newVersion, notes: e.target.value })}
              style={{ flex: 1, background: "var(--input-bg)", color: "var(--input-text)", border: "1px solid var(--input-border)", borderRadius: 4, padding: "6px 8px" }} />
            <button onClick={() => {
              if (newVersion.version) {
                setForm({ ...form, versions: [...(form.versions || []), { ...newVersion }] });
                setNewVersion({ version: '', notes: '' });
              }
            }} style={{ background: "var(--sidebar-icon)", color: "#fff", border: "none", borderRadius: 4, padding: "4px 10px" }}>New Version</button>
          </div>
        </div>
        <div style={{ marginTop: 20, display: "flex", gap: 8, justifyContent: "center" }}>
          <button onClick={() => onSave(form)} style={{ background: "var(--sidebar-icon)", color: "#fff", border: "none", borderRadius: 4, padding: "8px 20px", fontWeight: 600 }}>Save</button>
          <button onClick={onCancel} style={{ background: "#444", color: "#fff", border: "none", borderRadius: 4, padding: "8px 20px", fontWeight: 600 }}>Cancel</button>
        </div>
      </div>
    );
  }

  // Modal for selecting a model to edit
  function SelectModelModal({ models, onSelect, onCancel }) {
    return (
      <div style={{ background: "var(--modal-bg)", border: "1px solid var(--modal-border)", borderRadius: 8, padding: 24, minWidth: 320 }}>
        <h3 style={{ marginTop: 0, color: "var(--modal-header-text)", textAlign: "center" }}>Select Model to Edit</h3>
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
            <h2 style={{ margin: 0, color: "var(--modal-header-text)", textAlign: "center" }}>Edit Models</h2>
            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 16 }}>
              <button onClick={() => setMode("edit")} style={{ background: "var(--sidebar-icon)", color: "#fff", border: "none", borderRadius: 4, padding: "8px 16px", fontWeight: 500 }}>Edit Existing</button>
              <button onClick={() => setMode("create")} style={{ background: "var(--sidebar-icon)", color: "#fff", border: "none", borderRadius: 4, padding: "8px 16px", fontWeight: 500 }}>Create New</button>
              <button onClick={onClose} style={{ background: "#444", color: "#fff", border: "none", borderRadius: 4, padding: "8px 16px", fontWeight: 500 }}>Close</button>
            </div>
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

import React, { useEffect, useState } from "react";

function SavepointTagger({ modelId }) {
  const [savepoints, setSavepoints] = useState([]);
  const [loading, setLoading] = useState(false);
  const [newTag, setNewTag] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!modelId) return;
    setLoading(true);
    fetch(`/api/registry/models/${modelId}/savepoints`)
      .then(r => r.json())
      .then(data => { setSavepoints(data); setLoading(false); })
      .catch(() => { setError("Failed to load savepoints"); setLoading(false); });
  }, [modelId]);

  const createSavepoint = async () => {
    setLoading(true);
    setError("");
    const payload = {
      version: newTag,
      notes,
      created: new Date().toISOString(),
      training_diff: {},
      metadata: {},
    };
    const res = await fetch(`/api/registry/models/${modelId}/savepoint`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      setNewTag("");
      setNotes("");
      // Refresh savepoints
      fetch(`/api/registry/models/${modelId}/savepoints`).then(r => r.json()).then(setSavepoints);
    } else {
      setError("Failed to create savepoint");
    }
    setLoading(false);
  };

  const rollback = async (version) => {
    setLoading(true);
    setError("");
    const res = await fetch(`/api/registry/models/${modelId}/rollback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version }),
    });
    if (!res.ok) setError("Failed to rollback");
    setLoading(false);
  };

  const archive = async (version) => {
    setLoading(true);
    setError("");
    const res = await fetch(`/api/registry/models/${modelId}/savepoint/${version}/archive`, {
      method: "POST" });
    if (!res.ok) setError("Failed to archive");
    // Refresh savepoints
    fetch(`/api/registry/models/${modelId}/savepoints`).then(r => r.json()).then(setSavepoints);
    setLoading(false);
  };

  return (
    <div style={{ padding: 16 }}>
      <h3>Model Savepoints</h3>
      {error && <div style={{ color: "#f04747" }}>{error}</div>}
      <div style={{ marginBottom: 16 }}>
        <input
          value={newTag}
          onChange={e => setNewTag(e.target.value)}
          placeholder="New version tag"
          style={{ marginRight: 8, padding: 4 }}
        />
        <input
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder="Notes (optional)"
          style={{ marginRight: 8, padding: 4 }}
        />
        <button onClick={createSavepoint} disabled={loading || !newTag}>Tag Savepoint</button>
      </div>
      {loading ? <div>Loading...</div> : (
        <ul>
          {savepoints.map(sp => (
            <li key={sp.version} style={{ marginBottom: 8 }}>
              <b>{sp.version}</b> ({sp.created?.slice(0, 19).replace('T', ' ')})
              {sp.notes && <> - <i>{sp.notes}</i></>}
              <button onClick={() => rollback(sp.version)} style={{ marginLeft: 8 }}>Rollback</button>
              <button onClick={() => archive(sp.version)} style={{ marginLeft: 8 }}>Archive</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default SavepointTagger;

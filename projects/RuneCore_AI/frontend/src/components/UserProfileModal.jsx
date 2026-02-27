import React, { useState, useEffect } from "react";

const API_BASE = process.env.REACT_APP_API_URL || "";

const UserProfileModal = ({ isOpen, onClose }) => {
  const [profile, setProfile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Local form state
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [projects, setProjects] = useState("");
  const [systemContext, setSystemContext] = useState("");
  const [responseStyle, setResponseStyle] = useState("balanced");

  useEffect(() => {
    if (isOpen) {
      fetchProfile();
    }
  }, [isOpen]);

  const fetchProfile = async () => {
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/user/profile`);
      if (res.ok) {
        const data = await res.json();
        setProfile(data);
        setName(data.name || "");
        setRole(data.role || "");
        setProjects((data.projects || []).join(", "));
        setSystemContext(data.system_context || "");
        setResponseStyle(data.preferences?.response_style || "balanced");
      } else {
        setError("Failed to load profile.");
      }
    } catch {
      setError("Cannot connect to backend.");
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        name: name.trim(),
        role: role.trim(),
        projects: projects.split(",").map((p) => p.trim()).filter(Boolean),
        system_context: systemContext.trim(),
        preferences: { response_style: responseStyle },
      };
      const res = await fetch(`${API_BASE}/api/user/profile`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setSuccess("Profile saved.");
        setTimeout(() => setSuccess(""), 3000);
      } else {
        const d = await res.json().catch(() => ({}));
        setError(d.error || "Save failed.");
      }
    } catch {
      setError("Cannot connect to backend.");
    } finally {
      setSaving(false);
    }
  };

  const handleClearFacts = async () => {
    setError("");
    try {
      await fetch(`${API_BASE}/api/user/profile`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ facts: [] }),
      });
      setProfile((prev) => prev ? { ...prev, facts: [] } : prev);
      setSuccess("Facts cleared.");
      setTimeout(() => setSuccess(""), 3000);
    } catch {
      setError("Cannot connect to backend.");
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>User Profile</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        {error && <div className="error-message">{error}</div>}
        {success && <div className="success-message">{success}</div>}

        <div className="agent-form">
          <div className="form-group">
            <label>Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
            />
          </div>

          <div className="form-group">
            <label>Role</label>
            <input
              type="text"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="e.g. developer, student, researcher"
            />
          </div>

          <div className="form-group">
            <label>Active Projects <span className="param-hint">comma-separated</span></label>
            <input
              type="text"
              value={projects}
              onChange={(e) => setProjects(e.target.value)}
              placeholder="e.g. RuneCore, StudyBuddy"
            />
          </div>

          <div className="form-group">
            <label>Response Style</label>
            <select
              value={responseStyle}
              onChange={(e) => setResponseStyle(e.target.value)}
            >
              <option value="concise">Concise</option>
              <option value="balanced">Balanced</option>
              <option value="detailed">Detailed</option>
              <option value="technical">Technical</option>
            </select>
          </div>

          <div className="form-group">
            <label>Extra Context <span className="param-hint">freeform — agents will see this</span></label>
            <textarea
              value={systemContext}
              onChange={(e) => setSystemContext(e.target.value)}
              rows={4}
              placeholder="Anything agents should always know about you..."
            />
          </div>

          {profile?.facts?.length > 0 && (
            <div className="form-group">
              <label>
                Auto-extracted Facts ({profile.facts.length})
                <span className="param-hint"> — written by the profile curator</span>
              </label>
              <div className="facts-list">
                {profile.facts.slice(0, 15).map((f, i) => (
                  <div key={i} className="fact-item">— {f}</div>
                ))}
                {profile.facts.length > 15 && (
                  <div className="fact-item fact-more">
                    +{profile.facts.length - 15} more...
                  </div>
                )}
              </div>
              <button
                className="cancel-btn"
                style={{ marginTop: "8px", fontSize: "10px" }}
                onClick={handleClearFacts}
              >
                Clear Facts
              </button>
            </div>
          )}
        </div>

        <div className="modal-actions">
          <div className="actions-left" />
          <div className="actions-right">
            <button className="cancel-btn" onClick={onClose}>Cancel</button>
            <button className="save-btn" onClick={handleSave} disabled={saving}>
              {saving ? "Saving..." : "Save Profile"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UserProfileModal;

import React, { useState, useEffect } from "react";
import ErrorBoundary from "./ErrorBoundary";

const API_BASE = process.env.REACT_APP_API_URL || "";

const DEVICE_LABELS = {
  cpu:  "CPU",
  dgpu: "dGPU",
  igpu: "iGPU",
  npu:  "NPU / ONNX",
};

const DEVICE_COLORS = {
  cpu:  "#6b7280",
  dgpu: "#f97316",
  igpu: "#3b82f6",
  npu:  "#22c55e",
};

function DeviceRow({ device }) {
  const type = device?.type || "";
  const color = DEVICE_COLORS[type] || "#6b7280";
  const label = DEVICE_LABELS[type] || (type ? type.toUpperCase() : "UNKNOWN");
  const vramGb = typeof device?.vram_gb === "number" ? device.vram_gb : 0;

  return (
    <div className="hw-device-row">
      <div className="hw-device-indicator" style={{ backgroundColor: color }} />
      <div className="hw-device-info">
        <span className="hw-device-label">{label}</span>
        <span className="hw-device-name">{device?.name || "Unknown"}</span>
        {vramGb > 0 && (
          <span className="hw-device-meta">{vramGb.toFixed(1)} GB VRAM</span>
        )}
      </div>
      <div className="hw-device-status">
        {device?.verified !== undefined ? (
          device.verified
            ? <span className="hw-status-ok">✓ Verified</span>
            : <span className="hw-status-err" title={device.error || ""}>✗ {device.error ? "Error" : "Unavailable"}</span>
        ) : device?.available
          ? <span className="hw-status-ok">● Available</span>
          : <span className="hw-status-warn">○ Not started</span>
        }
      </div>
    </div>
  );
}

export default function HardwarePanel({ isOpen, onClose, devices, setDevices, optimised, setOptimised }) {
  const [state, setState] = useState("idle"); // idle | running | done | error
  const [actionLog, setActionLog] = useState([]);
  const [resultDevices, setResultDevices] = useState([]);
  const [errorMsg, setErrorMsg] = useState("");

  // Reset panel state when closed
  useEffect(() => {
    if (!isOpen) {
      setState("idle");
      setActionLog([]);
      setResultDevices([]);
      setErrorMsg("");
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleOptimise = async () => {
    setState("running");
    setActionLog(["Fetching hardware profile..."]);
    setResultDevices([]);
    setErrorMsg("");

    try {
      const r = await fetch(`${API_BASE}/api/hardware/optimise`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const data = await r.json();

      if (!r.ok) {
        setState("error");
        setErrorMsg(data.error || `HTTP ${r.status}`);
        return;
      }

      setActionLog(data.actions_taken || []);
      setResultDevices(data.devices || []);

      // Update parent device list with fresh data
      if (data.devices && data.devices.length > 0) {
        // Re-fetch status to get the full device list (optimise returns verification data)
        try {
          const sr = await fetch(`${API_BASE}/api/hardware/status`);
          if (sr.ok) {
            const sd = await sr.json();
            setDevices(sd.devices || []);
          }
        } catch (_) {}
      }

      setOptimised(true);
      setState("done");
    } catch (e) {
      setState("error");
      setErrorMsg(String(e));
    }
  };

  const displayDevices = state === "done" ? resultDevices : devices;
  const verifiedCount = resultDevices.filter((d) => d.verified).length;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <ErrorBoundary onClose={onClose}>
      <div className="modal-container hw-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Hardware Optimisation</h2>
          <button className="modal-close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="hw-panel-body">
          {/* Detected hardware section */}
          <div className="hw-section">
            <div className="hw-section-title">
              {state === "done" ? "Verified Services" : "Detected Hardware"}
            </div>
            {displayDevices.length === 0 ? (
              <div className="hw-empty">
                {state === "running"
                  ? "Scanning hardware..."
                  : "No hardware profile available. Ensure Sentinel is running."}
              </div>
            ) : (
              <div className="hw-device-list">
                {displayDevices.map((d, i) => <DeviceRow key={i} device={d} />)}
              </div>
            )}
          </div>

          {/* Action log */}
          {actionLog.length > 0 && (
            <div className="hw-section">
              <div className="hw-section-title">Actions</div>
              <div className="hw-log">
                {actionLog.map((line, i) => (
                  <div key={i} className="hw-log-line">› {typeof line === "string" ? line : JSON.stringify(line)}</div>
                ))}
              </div>
            </div>
          )}

          {/* Result banner */}
          {state === "done" && (
            <div className="hw-result-banner">
              Hardware optimised — {verifiedCount} of {resultDevices.length} endpoint{resultDevices.length !== 1 ? "s" : ""} verified.
            </div>
          )}

          {state === "error" && (
            <div className="hw-error-banner">
              Error: {errorMsg}
            </div>
          )}

          {/* Description */}
          {state === "idle" && (
            <div className="hw-description">
              Reads your hardware profile, starts the required inference services via Marshal,
              and verifies each endpoint. After optimisation, agents set to <strong>Auto</strong> will
              automatically route to the best device based on model size.
            </div>
          )}
        </div>

        <div className="hw-panel-footer">
          {state === "idle" || state === "error" ? (
            <button className="hw-optimise-btn" onClick={handleOptimise}>
              ⚡ Optimise for this hardware
            </button>
          ) : state === "running" ? (
            <button className="hw-optimise-btn" disabled>
              Running...
            </button>
          ) : (
            <button className="hw-optimise-btn hw-optimise-btn--rerun" onClick={handleOptimise}>
              ↺ Re-run optimisation
            </button>
          )}
          <button className="cancel-btn" onClick={onClose}>Close</button>
        </div>
      </div>
      </ErrorBoundary>
    </div>
  );
}

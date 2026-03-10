import React from "react";
import ErrorBoundary from "./ErrorBoundary";

const TYPE_COLOR = {
  cpu:  "#6b7280",
  dgpu: "#f97316",
  igpu: "#3b82f6",
  npu:  "#22c55e",
};

const TYPE_LABEL = {
  cpu:  "CPU",
  dgpu: "dGPU",
  igpu: "iGPU",
  npu:  "NPU",
};

// Which section does a step belong to?
function stepSection(id) {
  if (id === "profile") return "hardware";
  if (id.startsWith("svc_") || id === "no_marshal") return "services";
  return "endpoints";
}

function StepIcon({ status }) {
  if (status === "running") return <span className="hw-step-spinner" aria-label="running" />;
  if (status === "done")    return <span className="hw-step-ok">✓</span>;
  if (status === "error")   return <span className="hw-step-err">✗</span>;
  if (status === "warn")    return <span className="hw-step-warn">⚠</span>;
  return <span className="hw-step-pending">○</span>;
}

function StepRow({ step }) {
  return (
    <div className={`hw-step-row hw-step-row--${step.status}`}>
      <StepIcon status={step.status} />
      <span className="hw-step-label">{step.label}</span>
      {step.message && <span className="hw-step-msg">{step.message}</span>}
    </div>
  );
}

function DeviceRow({ device }) {
  const color = TYPE_COLOR[device.type] || "#6b7280";
  const label = TYPE_LABEL[device.type] || (device.type || "").toUpperCase();
  return (
    <div className="hw-device-row">
      <div className="hw-device-indicator" style={{ backgroundColor: color }} />
      <div className="hw-device-info">
        <span className="hw-device-label">{label}</span>
        <span className="hw-device-name">{device.name || device.endpoint}</span>
      </div>
      <div className="hw-device-status">
        {device.verified
          ? <span className="hw-status-ok">✓ Verified</span>
          : <span className="hw-status-err" title={device.error || ""}>
              {device.error ? `✗ ${device.error}` : "✗ Unverified"}
            </span>}
      </div>
    </div>
  );
}

export default function HardwarePanel({
  isOpen, onClose,
  hwStatus, hwSteps, hwDevices,
  onStart,
  devices,   // detected hardware from /status (shown before optimise)
}) {
  if (!isOpen) return null;

  const running  = hwStatus === "running";
  const done     = hwStatus === "done";
  const hasError = hwStatus === "error";
  const active   = running || done || hasError;

  const hwStepsSection = hwSteps.filter(s => stepSection(s.id) === "hardware");
  const svcSteps       = hwSteps.filter(s => stepSection(s.id) === "services");
  const verifySteps    = hwSteps.filter(s => stepSection(s.id) === "endpoints");
  const verifiedCount  = hwDevices.filter(d => d.verified).length;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <ErrorBoundary onClose={onClose}>
      <div className="modal-content hw-panel" onClick={e => e.stopPropagation()}>

        <div className="modal-header">
          <h2>Hardware Optimisation</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="hw-panel-body">

          {/* Idle: show detected hardware + description */}
          {!active && (
            <>
              {devices && devices.length > 0 && (
                <div className="hw-section">
                  <div className="hw-section-title">Detected Hardware</div>
                  <div className="hw-device-list">
                    {devices.map((d, i) => (
                      <div key={i} className="hw-device-row">
                        <div className="hw-device-indicator"
                             style={{ backgroundColor: TYPE_COLOR[d.type] || "#6b7280" }} />
                        <div className="hw-device-info">
                          <span className="hw-device-label">{TYPE_LABEL[d.type] || d.type}</span>
                          <span className="hw-device-name">{d.name || "Unknown"}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <div className="hw-description">
                Reads your hardware profile, starts the required inference services,
                and verifies each endpoint. Agents set to <strong>Auto</strong> will
                route to the best device for each request.
              </div>
            </>
          )}

          {/* Progress steps */}
          {active && (
            <>
              {hwStepsSection.length > 0 && (
                <div className="hw-section">
                  <div className="hw-section-title">Hardware</div>
                  <div className="hw-steps">
                    {hwStepsSection.map(s => <StepRow key={s.id} step={s} />)}
                  </div>
                </div>
              )}

              {svcSteps.length > 0 && (
                <div className="hw-section">
                  <div className="hw-section-title">Services</div>
                  <div className="hw-steps">
                    {svcSteps.map(s => <StepRow key={s.id} step={s} />)}
                  </div>
                </div>
              )}

              {verifySteps.length > 0 && (
                <div className="hw-section">
                  <div className="hw-section-title">Endpoints</div>
                  <div className="hw-steps">
                    {verifySteps.map(s => <StepRow key={s.id} step={s} />)}
                  </div>
                </div>
              )}
            </>
          )}

          {/* Final verified device list */}
          {done && hwDevices.length > 0 && (
            <div className="hw-section">
              <div className="hw-section-title">Ready</div>
              <div className="hw-device-list">
                {hwDevices.map((d, i) => <DeviceRow key={i} device={d} />)}
              </div>
              <div className="hw-result-banner">
                {verifiedCount} of {hwDevices.length} endpoint{hwDevices.length !== 1 ? "s" : ""} verified.
              </div>
            </div>
          )}

          {hasError && (
            <div className="hw-error-banner">Optimisation failed — check service logs.</div>
          )}

        </div>

        <div className="hw-panel-footer">
          {!running && !done ? (
            <button className="hw-optimise-btn" onClick={onStart}>
              ⚡ Optimise for this hardware
            </button>
          ) : running ? (
            <button className="hw-optimise-btn" disabled>Running...</button>
          ) : (
            <button className="hw-optimise-btn hw-optimise-btn--rerun" onClick={onStart}>
              ↺ Re-run
            </button>
          )}
          <button className="cancel-btn" onClick={onClose}>Close</button>
        </div>

      </div>
      </ErrorBoundary>
    </div>
  );
}

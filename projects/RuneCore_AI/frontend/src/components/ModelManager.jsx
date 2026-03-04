import React, { useState, useEffect, useRef } from "react";
import ErrorBoundary from "./ErrorBoundary";

const MAX_POLL_ITERATIONS = 150; // 150 × 2s = 5 min max

const ModelManager = ({ isOpen, onClose }) => {
  const [availableModels, setAvailableModels] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  // Map of modelName -> { progress: number (0-100), status: 'running'|'failed' }
  // 'failed' stays in map so UI can show retry button
  const [downloadingModels, setDownloadingModels] = useState({});
  const [newModelName, setNewModelName] = useState("");
  // Track active poll loops so we can break them on cancel
  const pollAbortRef = useRef({});

  const API_BASE = process.env.REACT_APP_API_URL || "";

  const popularModels = [
    { name: "llama3.2:1b", description: "Fast 1B parameter model (currently default)", size: "1.3GB" },
    { name: "llama3.2:3b", description: "Balanced 3B parameter model", size: "2.0GB" },
    { name: "llama3.1:8b", description: "High quality 8B parameter model", size: "4.7GB" },
    { name: "codellama:7b", description: "Code-focused model", size: "3.8GB" },
    { name: "mistral:7b", description: "Fast and efficient model", size: "4.1GB" },
    { name: "phi3:mini", description: "Compact high-performance model", size: "2.3GB" },
    { name: "qwen2:0.5b", description: "Ultra-fast small model", size: "0.4GB" },
    { name: "gemma:2b", description: "Google's Gemma 2B model", size: "1.4GB" },
  ];

  useEffect(() => {
    if (isOpen) {
      fetchAvailableModels();
    }
  }, [isOpen]);

  // Clear abort flags for finished models on unmount
  useEffect(() => {
    return () => {
      Object.keys(pollAbortRef.current).forEach((k) => {
        pollAbortRef.current[k] = true;
      });
    };
  }, []);

  const fetchAvailableModels = async () => {
    setIsLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/models`);
      if (response.ok) {
        const data = await response.json();
        // Backend may return objects {name, size, ...} or plain strings — normalize to strings
        const raw = data.models || [];
        const models = raw.map((m) => (typeof m === "string" ? m : m?.name || null)).filter(Boolean);
        setAvailableModels(models);
      } else {
        const errorData = await response.json().catch(() => ({}));
        if (response.status === 503) {
          setError("AI service is not available. Please make sure the AI service is running and try again.");
        } else {
          setError(errorData.error || "Unable to load AI models. Please check your connection and try again.");
        }
      }
    } catch (err) {
      if (err.name === "TypeError" && err.message.includes("fetch")) {
        setError("Cannot connect to AI service. Please make sure the service is running.");
      } else {
        setError("Connection error: Unable to fetch available models. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const cancelDownload = (modelName) => {
    // Signal the poll loop to stop
    pollAbortRef.current[modelName] = true;
    setDownloadingModels((prev) => {
      const copy = { ...prev };
      delete copy[modelName];
      return copy;
    });
  };

  const downloadModel = async (modelName) => {
    const entry = downloadingModels[modelName];
    if (entry && entry.status === "running") return;

    // Reset abort flag for this model
    pollAbortRef.current[modelName] = false;

    setSuccessMessage("");
    setError("");
    setDownloadingModels((prev) => ({ ...prev, [modelName]: { progress: 0, status: "running" } }));

    try {
      const response = await fetch(`${API_BASE}/api/models/pull`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: modelName }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        let msg;
        if (response.status === 404) {
          msg = `Model "${modelName}" not found. Please check the model name and try again.`;
        } else if (response.status === 507) {
          msg = `Not enough disk space to download "${modelName}". Please free up space and try again.`;
        } else if (response.status === 503) {
          msg = "AI service is not available. Please make sure Ollama is running and try again.";
        } else {
          msg = errorData.error || `Failed to download "${modelName}". Please check your internet connection and try again.`;
        }
        setDownloadingModels((prev) => ({ ...prev, [modelName]: { progress: 0, status: "failed" } }));
        setError(msg);
        return;
      }

      // Pull started — begin polling status
      pollModelStatus(modelName);
    } catch (err) {
      if (err.name === "TypeError" && err.message.includes("fetch")) {
        setError("Cannot connect to AI service. Please make sure the service is running.");
      } else {
        setError(`Connection error while downloading "${modelName}". Please check your internet connection and try again.`);
      }
      setDownloadingModels((prev) => ({ ...prev, [modelName]: { progress: 0, status: "failed" } }));
    }
  };

  const pollModelStatus = async (modelName) => {
    let iterations = 0;

    while (iterations < MAX_POLL_ITERATIONS) {
      // Cancelled by user
      if (pollAbortRef.current[modelName]) {
        return;
      }

      await new Promise((res) => setTimeout(res, 2000));
      iterations++;

      if (pollAbortRef.current[modelName]) return;

      try {
        // Check if model now appears in the available list.
        // The /api/models endpoint may return objects {name, size, ...} or strings
        // depending on whether model_manager is active — normalize to strings.
        const modelsResp = await fetch(`${API_BASE}/api/models`);
        if (modelsResp.ok) {
          const mdata = await modelsResp.json().catch(() => ({}));
          const availableNames = (mdata.models || []).map((m) =>
            typeof m === "string" ? m : m?.name || null
          ).filter(Boolean);
          if (availableNames.includes(modelName)) {
            setDownloadingModels((prev) => {
              const copy = { ...prev };
              delete copy[modelName];
              return copy;
            });
            setSuccessMessage(`${modelName} downloaded successfully.`);
            await fetchAvailableModels();
            return;
          }
        }

        // Query pull status by model name
        const pullResp = await fetch(`${API_BASE}/api/models/pull/${encodeURIComponent(modelName)}/status`);
        if (pullResp.ok) {
          const pullData = await pullResp.json().catch(() => ({}));
          const prog = typeof pullData.progress === "number" ? pullData.progress : 0;
          const status = pullData.status || "running";

          if (status === "completed") {
            setDownloadingModels((prev) => {
              const copy = { ...prev };
              delete copy[modelName];
              return copy;
            });
            setSuccessMessage(`${modelName} downloaded successfully.`);
            await fetchAvailableModels();
            return;
          }

          if (status === "failed") {
            setDownloadingModels((prev) => ({ ...prev, [modelName]: { progress: prog, status: "failed" } }));
            setError(`Download failed for "${modelName}". ${pullData.error || "See logs for details."}`);
            return;
          }

          if (status === "cancelled") {
            setDownloadingModels((prev) => {
              const copy = { ...prev };
              delete copy[modelName];
              return copy;
            });
            return;
          }

          // Still running — update progress
          setDownloadingModels((prev) => ({
            ...prev,
            [modelName]: { progress: prog, status: "running" },
          }));
        }
        // 404 just means model_manager doesn't have a status entry yet — keep polling
      } catch (_err) {
        // Transient error — keep polling
      }
    }

    // Poll timeout
    setDownloadingModels((prev) => ({ ...prev, [modelName]: { progress: 0, status: "failed" } }));
    setError(`Download of "${modelName}" timed out (5 minutes). The pull may still be running in the background. Refresh to check.`);
  };

  const downloadCustomModel = async () => {
    const name = newModelName.trim();
    if (!name) {
      setError('Please enter a model name (e.g., "llama3.1:8b" or "mistral:7b")');
      return;
    }
    setNewModelName("");
    await downloadModel(name);
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter") downloadCustomModel();
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <ErrorBoundary onClose={onClose}>
      <div className="modal-content large-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Model Management</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        {successMessage && (
          <div className="success-message">{successMessage}</div>
        )}
        {error && (
          <div className="error-message">{error}</div>
        )}

        <div className="model-manager-content">
          {/* Downloaded Models */}
          <div className="models-section">
            <h3>Downloaded Models ({availableModels.length})</h3>
            {isLoading ? (
              <div className="loading-indicator">Loading models...</div>
            ) : availableModels.length > 0 ? (
              <div className="models-grid">
                {availableModels.map((model) => (
                  <div key={model} className="model-card downloaded">
                    <div className="model-info">
                      <div className="model-name">{model}</div>
                      <div className="model-status">✅ Ready to use</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                No models downloaded yet. Download some models below to get started.
              </div>
            )}
          </div>

          {/* Popular Models */}
          <div className="models-section">
            <h3>Popular Models</h3>
            <div className="models-grid">
              {popularModels.map((model) => {
                const isDownloaded = availableModels.includes(model.name);
                const entry = downloadingModels[model.name];
                const isRunning = entry && entry.status === "running";
                const isFailed = entry && entry.status === "failed";
                const progress = entry ? entry.progress || 0 : 0;

                return (
                  <div
                    key={model.name}
                    className={`model-card ${isDownloaded ? "downloaded" : "available"}`}
                  >
                    <div className="model-info">
                      <div className="model-name">{model.name}</div>
                      <div className="model-description">{model.description}</div>
                      <div className="model-size">Size: {model.size}</div>
                    </div>
                    <div className="model-actions">
                      {isDownloaded ? (
                        <span className="status-badge downloaded">✅ Downloaded</span>
                      ) : isRunning ? (
                        <div className="download-progress">
                          <div className="progress-bar-track">
                            <div className="progress-bar" style={{ width: `${progress}%` }} />
                          </div>
                          <div className="progress-label">{progress}%</div>
                          <button
                            onClick={() => cancelDownload(model.name)}
                            className="cancel-download-btn"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : isFailed ? (
                        <button
                          onClick={() => downloadModel(model.name)}
                          className="retry-btn"
                        >
                          ↺ Retry
                        </button>
                      ) : (
                        <button
                          onClick={() => downloadModel(model.name)}
                          className="download-btn"
                        >
                          📥 Download
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Custom Model Download */}
          <div className="models-section">
            <h3>Download Custom Model</h3>
            <div className="custom-download">
              <input
                type="text"
                value={newModelName}
                onChange={(e) => setNewModelName(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Enter model name (e.g., llama3.1:70b)"
                className="model-input"
              />
              <button
                onClick={downloadCustomModel}
                disabled={!newModelName.trim() || (downloadingModels[newModelName.trim()] && downloadingModels[newModelName.trim()].status === "running")}
                className="download-btn"
              >
                Download
              </button>
            </div>
            {/* Show inline status for custom model if downloading/failed */}
            {newModelName.trim() && downloadingModels[newModelName.trim()] && (
              <div className="custom-download-status">
                {downloadingModels[newModelName.trim()].status === "running"
                  ? `Downloading... ${downloadingModels[newModelName.trim()].progress}%`
                  : "Download failed — check error above and retry."}
              </div>
            )}
            <div className="download-hint">
              Find more models at{" "}
              <a href="https://ollama.ai/library" target="_blank" rel="noopener noreferrer">
                ollama.ai/library
              </a>
            </div>
          </div>
        </div>

        <div className="modal-actions">
          <button onClick={onClose} className="cancel-btn">Close</button>
        </div>
      </div>
      </ErrorBoundary>
    </div>
  );
};

export default ModelManager;

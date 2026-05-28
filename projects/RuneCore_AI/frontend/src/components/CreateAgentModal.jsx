import React, { useState, useEffect } from "react";
import { logFrontendError } from "../utils/errorLogger";
import ErrorBoundary from "./ErrorBoundary";

const CreateAgentModal = ({ isOpen, onClose, onAgentCreated, availableDevices = [] }) => {
  const [formData, setFormData] = useState({
    name: "",
    avatar_image: null,
    model_name: "llama3.2:1b",
    placement: "auto",
    temperature: 70,
    top_p: 90,
    system_prompt: "You are a helpful AI assistant.",
    max_tokens: 2048,
  });

  const [availableModels, setAvailableModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const [avatarPreview, setAvatarPreview] = useState(null);
  const [modelDownloading, setModelDownloading] = useState(null);
  const [onnxDownloadStatus, setOnnxDownloadStatus] = useState(null); // null | "downloading" | "done" | "error"

  // Suggested ONNX models for NPU inference (small, DirectML-compatible)
  const SUGGESTED_ONNX_MODELS = [
    { model_id: "microsoft/Phi-3-mini-4k-instruct-onnx", local_name: "phi3-mini-onnx", label: "Phi-3 Mini 3.8B (recommended)" },
    { model_id: "Qwen/Qwen2.5-0.5B-Instruct-ONNX", local_name: "qwen2.5-0.5b-onnx", label: "Qwen 2.5 0.5B (fastest)" },
  ];

  // Common model options (will be supplemented by API)
  const commonModels = [
    "llama3.2:1b",
    "llama3.2:3b",
    "llama3.1:8b",
    "codellama:7b",
    "mistral:7b",
    "gemma:2b",
    "phi3:mini",
  ];

  useEffect(() => {
    if (isOpen) {
      fetchAvailableModels();
    }
  }, [isOpen]);

  const API_BASE = process.env.REACT_APP_API_URL || "";

  const fetchAvailableModels = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/models`);
      if (response.ok) {
        const data = await response.json();
        const raw = data.models || [];
        // Preserve backend field — needed to filter by placement
        const models = raw
          .map((m) =>
            typeof m === "string"
              ? { name: m, backend: "ollama" }
              : { name: m?.name, backend: m?.backend || "ollama" }
          )
          .filter((m) => m.name);
        setAvailableModels(models);
      }
    } catch (error) {
      logFrontendError("FRONTEND_MODEL_ERROR", "Failed to fetch models", error);
      setAvailableModels(commonModels.map((name) => ({ name, backend: "ollama" })));
    }
  };

  const handleInputChange = (field, value) => {
    setFormData((prev) => {
      const next = { ...prev, [field]: value };
      if (field === "placement") {
        const goingNPU = value === "npu";
        const wasNPU = prev.placement === "npu";
        if (goingNPU !== wasNPU) {
          const curIsOnnx = availableModels.some(
            (m) => m.name === prev.model_name && m.backend === "onnx"
          );
          if (goingNPU && !curIsOnnx) next.model_name = "";
          if (!goingNPU && curIsOnnx) next.model_name = "";
        }
      }
      return next;
    });

    // Clear field error when user starts typing
    if (errors[field]) {
      setErrors((prev) => ({
        ...prev,
        [field]: null,
      }));
    }
  };

  const handleAvatarUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      // Validate file type
      if (!file.type.startsWith("image/")) {
        setErrors((prev) => ({
          ...prev,
          avatar_image: "Please select an image file (JPG, PNG, GIF, or WebP)",
        }));
        return;
      }

      // Validate file size (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        setErrors((prev) => ({
          ...prev,
          avatar_image:
            "Image file must be smaller than 5MB. Try compressing the image or choose a different one.",
        }));
        return;
      }

      // Create preview
      const reader = new FileReader();
      reader.onload = (e) => {
        setAvatarPreview(e.target.result);
        setFormData((prev) => ({ ...prev, avatar_image: file }));
        setErrors((prev) => ({ ...prev, avatar_image: null }));
      };
      reader.readAsDataURL(file);
    }
  };

  const checkModelAvailability = async (modelName) => {
    try {
      const response = await fetch(
        `${API_BASE}/api/models/check/${encodeURIComponent(modelName)}`
      );
      if (response.ok) {
        const data = await response.json();
        return data.available;
      }
      return false;
    } catch (error) {
      logFrontendError(
        "FRONTEND_MODEL_ERROR",
        "Failed to check model availability",
        error,
        { modelName }
      );
      return false;
    }
  };

  const handleModelDownload = async (modelName) => {
    try {
      setModelDownloading(modelName);

      const response = await fetch(
        `${API_BASE}/api/models/download/${encodeURIComponent(modelName)}`,
        {
          method: "POST",
        }
      );

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          // Refresh available models
          await fetchAvailableModels();
          logFrontendError(
            "FRONTEND_MODEL_INFO",
            `Model ${modelName} download completed successfully`,
            null,
            { modelName }
          );
        } else {
          logFrontendError(
            "FRONTEND_MODEL_ERROR",
            `Model ${modelName} download failed`,
            new Error(data.error),
            { modelName }
          );
          throw new Error(data.error || "Download failed");
        }
      } else {
        logFrontendError(
          "FRONTEND_MODEL_ERROR",
          `Failed to start download for ${modelName}`,
          null,
          { modelName }
        );
        throw new Error("Failed to start download");
      }
    } catch (error) {
      logFrontendError(
        "FRONTEND_MODEL_ERROR",
        `Model download error for ${modelName}`,
        error,
        { modelName }
      );
      // Only set errors if this is a foreground download (user initiated from model list)
      if (modelDownloading === modelName) {
        setErrors((prev) => ({
          ...prev,
          model_download: error.message || "Network error during download",
        }));
      }
      throw error; // Re-throw for background download handling
    } finally {
      setModelDownloading(null);
    }
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.name.trim()) {
      newErrors.name = "Please enter a name for your AI agent";
    }

    if (!formData.model_name) {
      newErrors.model_name = "Please select an AI model for your agent";
    }

    if (formData.temperature < 0 || formData.temperature > 100) {
      newErrors.temperature =
        "Temperature should be between 0 (focused) and 100 (creative)";
    }

    if (formData.top_p < 0 || formData.top_p > 100) {
      newErrors.top_p =
        "Top P should be between 0 and 100 (controls response variety)";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setLoading(true);

    try {
      // Check if model is available
      const modelAvailable = await checkModelAvailability(formData.model_name);

      let downloadInProgress = false;

      if (!modelAvailable) {
        const shouldDownload = window.confirm(
          `The model "${formData.model_name}" is not available locally. Would you like to download it?\n\nThe agent will be created immediately but will show as "offline" until the download completes. This may take several minutes.`
        );

        if (shouldDownload) {
          downloadInProgress = true;
          // Start download in background - don't wait for it
          handleModelDownload(formData.model_name).catch((error) => {
            logFrontendError(
              "FRONTEND_MODEL_ERROR",
              "Background model download failed",
              error,
              { modelName: formData.model_name }
            );
          });
        }
      }

      // Prepare data for submission
      let requestBody;
      let requestHeaders = {};

      // Use FormData only if we have a file to upload
      if (formData.avatar_image) {
        const submitData = new FormData();
        submitData.append("name", formData.name);
        submitData.append("model_name", formData.model_name);
        submitData.append("temperature", formData.temperature / 100); // Convert to 0-1 range for backend
        submitData.append("top_p", formData.top_p / 100); // Convert to 0-1 range for backend
        submitData.append("system_prompt", formData.system_prompt);
        submitData.append("max_tokens", formData.max_tokens);

        // Add download status to metadata
        if (downloadInProgress) {
          submitData.append(
            "metadata",
            JSON.stringify({
              model_downloading: true,
              download_started: new Date().toISOString(),
            })
          );
        }

        submitData.append("avatar_image", formData.avatar_image);
        requestBody = submitData;
        // Don't set Content-Type for FormData - browser will set it with boundary
      } else {
        // Use JSON for cleaner requests when no file upload is needed
        const jsonData = {
          name: formData.name,
          model_name: formData.model_name,
          temperature: formData.temperature / 100,
          top_p: formData.top_p / 100,
          system_prompt: formData.system_prompt,
          max_tokens: formData.max_tokens,
          avatar_image: "🤖", // Use emoji avatar as default when no file uploaded
        };

        // Add download status to metadata
        if (downloadInProgress) {
          jsonData.metadata = {
            model_downloading: true,
            download_started: new Date().toISOString(),
          };
        }

        requestBody = JSON.stringify(jsonData);
        requestHeaders["Content-Type"] = "application/json";
      }

  const response = await fetch(`${API_BASE}/api/agents`, {
        method: "POST",
        headers: requestHeaders,
        body: requestBody,
      });

      if (response.ok) {
        const newAgent = await response.json();

        // Show success message with download info if applicable
        if (downloadInProgress) {
          alert(
            `Agent "${newAgent.name}" created successfully!\n\nThe model "${formData.model_name}" is downloading in the background. The agent will appear offline until the download completes.`
          );
        }

        onAgentCreated(newAgent);
        onClose();

        // Reset form
        setFormData({
          name: "",
          avatar_image: null,
          model_name: "llama3.2:1b",
          temperature: 70,
          top_p: 90,
          system_prompt: "You are a helpful AI assistant.",
          max_tokens: 2048,
        });
        setAvatarPreview(null);
      } else {
        const errorData = await response.json();
        // Use the improved error message from the backend
        const errorMessage =
          errorData.message || errorData.error || "Failed to create agent";

        // Handle technical errors with error codes
        if (errorData.error_code) {
          setErrors({
            submit: `${errorMessage} (Error Code: ${errorData.error_code})`,
            details: errorData.action_required
              ? [errorData.action_required]
              : errorData.suggestions || [],
            technical: true,
            errorCode: errorData.error_code,
          });
        } else {
          setErrors({
            submit: errorMessage,
            details: errorData.suggestions || [],
          });
        }
      }
    } catch (error) {
      logFrontendError("FRONTEND_API_ERROR", "Agent creation error", error, {
        formData,
      });
      setErrors({
        submit:
          "Unable to create agent. Please check your internet connection and try again.",
        details: [
          "Make sure you're connected to the internet",
          "Try refreshing the page",
          "Contact support if the problem continues",
        ],
      });
    }

    setLoading(false);
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <ErrorBoundary onClose={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Create New Agent</h2>
          <button className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="agent-form">
          {/* Agent Name */}
          <div className="form-group">
            <label htmlFor="name">Agent Name *</label>
            <input
              id="name"
              type="text"
              value={formData.name}
              onChange={(e) => handleInputChange("name", e.target.value)}
              placeholder="Enter agent name"
              className={errors.name ? "error" : ""}
            />
            {errors.name && <span className="error-text">{errors.name}</span>}
          </div>

          {/* Avatar Upload */}
          <div className="form-group">
            <label htmlFor="avatar">Avatar Image</label>
            <div className="avatar-upload-container">
              <input
                id="avatar"
                type="file"
                accept="image/*"
                onChange={handleAvatarUpload}
                style={{ display: "none" }}
              />
              <label htmlFor="avatar" className="avatar-upload-button">
                {avatarPreview ? (
                  <img
                    src={avatarPreview}
                    alt="Avatar preview"
                    className="avatar-preview"
                  />
                ) : (
                  <div className="avatar-upload-placeholder">
                    <span>📁</span>
                    <span>Choose Image</span>
                  </div>
                )}
              </label>
              <div className="avatar-upload-info">
                <small>
                  Upload an image (max 5MB). JPG, PNG, GIF supported.
                </small>
              </div>
            </div>
            {errors.avatar_image && (
              <span className="error-text">{errors.avatar_image}</span>
            )}
          </div>

          {/* Model Selection — options filtered by placement */}
          <div className="form-group">
            <label htmlFor="model">AI Model *</label>
            <select
              id="model"
              value={formData.model_name}
              onChange={(e) => handleInputChange("model_name", e.target.value)}
              className={errors.model_name ? "error" : ""}
            >
              <option value="">Select a model</option>
              {formData.placement === "npu" ? (
                availableModels.filter((m) => m.backend === "onnx").length > 0 ? (
                  availableModels
                    .filter((m) => m.backend === "onnx")
                    .map((m) => (
                      <option key={m.name} value={m.name}>{m.name} ✓</option>
                    ))
                ) : (
                  <option disabled value="">No ONNX models — download one in Model Manager</option>
                )
              ) : (
                [
                  ...new Set([
                    ...commonModels,
                    ...availableModels.filter((m) => m.backend !== "onnx").map((m) => m.name),
                  ]),
                ].map((name) => {
                  const local = availableModels.some((m) => m.name === name && m.backend !== "onnx");
                  return (
                    <option key={name} value={name}>
                      {name} {local ? "✓" : "⬇️"}
                    </option>
                  );
                })
              )}
            </select>
            <small>
              {formData.placement === "npu"
                ? availableModels.filter((m) => m.backend === "onnx").length === 0
                  ? "No ONNX models available. Download one from Model Manager first."
                  : "✓ = Available locally (ONNX format)"
                : "✓ = Available locally, ⬇️ = Needs download"}
            </small>
            {errors.model_name && (
              <span className="error-text">{errors.model_name}</span>
            )}
            {errors.model_download && (
              <span className="error-text">{errors.model_download}</span>
            )}
          </div>

          {/* Hardware Placement */}
          <div className="form-group">
            <label htmlFor="placement">Hardware Placement</label>
            <select
              id="placement"
              value={formData.placement}
              onChange={(e) => handleInputChange("placement", e.target.value)}
            >
              <option value="auto">Auto (smart: small→NPU, fits→GPU, rest→CPU)</option>
              <option value="cpu">CPU</option>
              {availableDevices.includes("dgpu") && (
                <option value="dgpu">dGPU — Discrete GPU</option>
              )}
              {availableDevices.includes("igpu") && (
                <option value="igpu">iGPU — Integrated GPU (DirectML)</option>
              )}
              {availableDevices.includes("npu") && (
                <option value="npu">NPU — ONNX / DirectML</option>
              )}
            </select>
            <small>
              Where to run inference for this agent.
              {availableDevices.length === 0 && " Run Hardware Optimisation to unlock GPU/NPU options."}
            </small>
          </div>

          {/* System Prompt */}
          <div className="form-group">
            <label htmlFor="system_prompt">System Prompt</label>
            <textarea
              id="system_prompt"
              value={formData.system_prompt}
              onChange={(e) =>
                handleInputChange("system_prompt", e.target.value)
              }
              placeholder="Describe the agent's personality and behavior"
              rows={3}
            />
          </div>

          {/* Advanced Settings */}
          <div className="form-group">
            <label className="section-label">Advanced Settings</label>

            <div className="form-row">
              <div className="form-col">
                <label htmlFor="temperature">
                  Temperature: {formData.temperature}
                </label>
                <input
                  id="temperature"
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  value={formData.temperature}
                  onChange={(e) =>
                    handleInputChange("temperature", parseInt(e.target.value))
                  }
                />
                <small>Controls randomness (0 = focused, 100 = creative)</small>
                {errors.temperature && (
                  <span className="error-text">{errors.temperature}</span>
                )}
              </div>

              <div className="form-col">
                <label htmlFor="top_p">Top P: {formData.top_p}</label>
                <input
                  id="top_p"
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  value={formData.top_p}
                  onChange={(e) =>
                    handleInputChange("top_p", parseInt(e.target.value))
                  }
                />
                <small>Controls diversity (0 = narrow, 100 = diverse)</small>
                {errors.top_p && (
                  <span className="error-text">{errors.top_p}</span>
                )}
              </div>
            </div>

            <div className="form-col">
              <label htmlFor="max_tokens">Max Tokens</label>
              <input
                id="max_tokens"
                type="number"
                min="128"
                max="8192"
                value={formData.max_tokens}
                onChange={(e) =>
                  handleInputChange("max_tokens", parseInt(e.target.value))
                }
              />
              <small>Maximum response length</small>
            </div>
          </div>

          {errors.submit && (
            <div
              className={`error-message ${errors.technical ? "technical-error" : ""}`}
            >
              <div className="error-text">{errors.submit}</div>
              {errors.technical && errors.errorCode && (
                <div className="technical-error-info">
                  <strong>⚠️ Technical Error</strong>
                  <p>
                    This appears to be a technical issue that you cannot fix
                    yourself.
                  </p>
                </div>
              )}
              {errors.details && errors.details.length > 0 && (
                <div className="error-suggestions">
                  <strong>
                    {errors.technical ? "Action Required:" : "Suggestions:"}
                  </strong>
                  <ul>
                    {errors.details.map((suggestion, index) => (
                      <li key={index}>{suggestion}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          <div className="form-actions">
            <button type="button" onClick={onClose} disabled={loading}>
              Cancel
            </button>
            <button type="submit" disabled={loading} className="primary">
              {loading ? "Creating..." : "Create Agent"}
            </button>
          </div>
        </form>
      </div>
      </ErrorBoundary>
    </div>
  );
};

export default CreateAgentModal;

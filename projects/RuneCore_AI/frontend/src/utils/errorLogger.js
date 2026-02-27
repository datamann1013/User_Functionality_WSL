/**
 * Frontend Error Logger
 * Sends errors to backend which forwards to ErrorLogger service
 */

// Use REACT_APP_API_URL when provided by the environment (works for dev and prod).
// Fallback to empty string so requests become relative and go through the router.
const API_BASE = process.env.REACT_APP_API_URL || "";

export const logFrontendError = async (
  errorCode,
  message,
  exception = null,
  extra = {}
) => {
  try {
    const payload = {
      error_code: errorCode,
      message: message,
      exception: exception ? exception.toString() : null,
      extra: {
        ...extra,
        timestamp: new Date().toISOString(),
        url: window.location.href,
        userAgent: navigator.userAgent,
      },
    };

    await fetch(`${API_BASE}/api/log-frontend-error`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    // If logging fails, silently fail to avoid infinite loops
    // In production, this would be handled by monitoring systems
  }
};

export const getErrorExplanation = (errorCode) => {
  /**
   * Error codes follow RuneGuard convention:
   * [Type][Origin][Component][Subcomponent][Number]
   * Type: E(rror), W(arning), I(nfo)
   * Origin: A (AI Service)
   * Component: F (Frontend)
   * Subcomponent: X (General), C (Chat), M (Modal), A (Agent)
   */
  const errorExplanations = {
    // Frontend - General (AFX)
    IAFX01: "Frontend application initialized",
    EAFX01: "Frontend rendering error",
    EAFX02: "Frontend API call failed",
    EAFX03: "Frontend state error",
    // Frontend - Chat (AFC)
    IAFC01: "Chat message sent",
    EAFC01: "Chat request failed",
    EAFC02: "Chat connection error",
    WAFC01: "Chat response delayed",
    // Frontend - Agent (AFA)
    IAFA01: "Agent created",
    IAFA02: "Agent updated",
    IAFA03: "Agent deleted",
    EAFA01: "Agent operation failed",
    // Frontend - Model (AFM)
    IAFM01: "Model list loaded",
    IAFM02: "Model download started",
    EAFM01: "Model operation failed",
    // Legacy codes (for backward compatibility)
    FRONTEND_INIT: "Frontend application initialized",
    FRONTEND_API_ERROR: "API request failed",
    FRONTEND_RENDER_ERROR: "Component render error",
    FRONTEND_CHAT_ERROR: "Chat functionality error",
    FRONTEND_MODEL_ERROR: "Model management error",
    FRONTEND_CONNECTION_ERROR: "Backend connection error",
  };

  return errorExplanations[errorCode] || `Error: ${errorCode}`;
};

// Global error handler for unhandled errors
window.addEventListener("error", (event) => {
  logFrontendError(
    "FRONTEND_UNHANDLED_ERROR",
    `Unhandled error: ${event.message}`,
    event.error,
    {
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
    }
  );
});

// Global handler for unhandled promise rejections
window.addEventListener("unhandledrejection", (event) => {
  logFrontendError(
    "FRONTEND_UNHANDLED_PROMISE",
    `Unhandled promise rejection: ${event.reason}`,
    event.reason,
    {
      type: "promise_rejection",
    }
  );
});

export default logFrontendError;

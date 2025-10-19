/**
 * Frontend Error Logger
 * Sends errors to backend which forwards to ErrorLogger service
 */

const API_BASE =
  process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5000';

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
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    // If logging fails, log to console as fallback
    console.error('Failed to log to ErrorLogger service:', err);
    console.error('Original error:', { errorCode, message, exception, extra });
  }
};

export const getErrorExplanation = errorCode => {
  const errorExplanations = {
    FRONTEND_INIT: 'Frontend application initialized',
    FRONTEND_API_ERROR: 'API request failed',
    FRONTEND_RENDER_ERROR: 'Component render error',
    FRONTEND_CHAT_ERROR: 'Chat functionality error',
    FRONTEND_MODEL_ERROR: 'Model management error',
    FRONTEND_CONNECTION_ERROR: 'Backend connection error',
  };

  return errorExplanations[errorCode] || 'Frontend error occurred';
};

// Global error handler for unhandled errors
window.addEventListener('error', event => {
  logFrontendError(
    'FRONTEND_UNHANDLED_ERROR',
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
window.addEventListener('unhandledrejection', event => {
  logFrontendError(
    'FRONTEND_UNHANDLED_PROMISE',
    `Unhandled promise rejection: ${event.reason}`,
    event.reason,
    {
      type: 'promise_rejection',
    }
  );
});

export default logFrontendError;

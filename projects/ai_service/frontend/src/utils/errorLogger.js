// Import error code definitions from the backend (via static file or hardcoded for frontend)
export const ERROR_CODE_DEFINITIONS = {
  IAFX1: "Frontend transmission received.",
  IAFX2: "Frontend transmission sent.",
  EAFX1: "Frontend error occurred.",
  E00001: "React exception occurred.",
  // Add more as needed
};

export function getErrorExplanation(error_code) {
  return ERROR_CODE_DEFINITIONS[error_code] || "No explanation provided";
}

// Utility to send error logs to the ErrorLogger service
export async function logFrontendError({ error, info, extra, error_code = "EAFX1" }) {
  try {
    await fetch('http://localhost:5001/log', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        error_code,
        message: info || getErrorExplanation(error_code),
        exception: error ? error.toString() : '',
        extra: extra || null,
      }),
    });
  } catch (e) {
    // Optionally, fallback to local logging or ignore
    // console.error('Failed to log error to ErrorLogger service', e);
  }
}

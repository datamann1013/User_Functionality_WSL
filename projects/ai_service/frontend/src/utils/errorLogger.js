// Utility to send error logs to the ErrorLogger service
export async function logFrontendError({ error, info, extra }) {
  try {
    await fetch('http://localhost:5001/log', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        error_code: 'FE001',
        message: info || '',
        exception: error ? error.toString() : '',
        extra: extra || null,
      }),
    });
  } catch (e) {
    // Optionally, fallback to local logging or ignore
    // console.error('Failed to log error to ErrorLogger service', e);
  }
}


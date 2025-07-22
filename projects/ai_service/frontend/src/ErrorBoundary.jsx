import React from "react";
import { logFrontendError, getErrorExplanation } from "./utils/errorLogger";

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // Log React error to ErrorLogger with code E00001
    logFrontendError({
      error,
      info: getErrorExplanation("E00001"),
      extra: errorInfo,
      error_code: "E00001",
    });
  }

  render() {
    if (this.state.hasError) {
      // Gently handle error: show fallback UI
      return (
        <div style={{ color: "red", padding: 24 }}>
          <h2>Something went wrong.</h2>
          <pre>{this.state.error && this.state.error.toString()}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;

import React from "react";

/**
 * ErrorBoundary — wraps any modal's inner content.
 * When a child component throws during render, this catches it and shows a
 * friendly error panel instead of leaving the user with a blank dark overlay.
 *
 * Usage:
 *   <ErrorBoundary onClose={onClose}>
 *     <div className="modal-content"> ... </div>
 *   </ErrorBoundary>
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: error?.message || String(error) };
  }

  componentDidCatch(error, info) {
    console.error("[ErrorBoundary] Caught render error:", error, info);
  }

  handleClose = () => {
    this.setState({ hasError: false, message: "" });
    if (this.props.onClose) this.props.onClose();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="modal-content error-boundary-fallback">
          <div className="modal-header">
            <h2>Something went wrong</h2>
            <button className="modal-close" onClick={this.handleClose}>×</button>
          </div>
          <div className="error-boundary-body">
            <p>A display error occurred in this panel.</p>
            {this.state.message && (
              <pre className="error-boundary-detail">{this.state.message}</pre>
            )}
          </div>
          <div className="modal-actions">
            <div className="actions-right">
              <button className="cancel-btn" onClick={this.handleClose}>Close</button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;

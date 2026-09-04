import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = {
  children: ReactNode;
  label?: string;
};

type State = {
  hasError: boolean;
  message: string;
};

class ErrorBoundary extends Component<Props, State> {
  state: State = {
    hasError: false,
    message: "",
  };

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      message: error?.message || "Something went wrong.",
    };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info);
  }

  handleReset = () => {
    this.setState({ hasError: false, message: "" });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            minHeight: "100vh",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "#f8fafc",
            color: "#0f172a",
            padding: "24px",
            boxSizing: "border-box",
          }}
        >
          <div
            style={{
              maxWidth: "480px",
              width: "100%",
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "18px",
              padding: "36px",
              textAlign: "center",
              boxShadow: "0 10px 30px rgba(15,23,42,0.06)",
            }}
          >
            <div style={{ fontSize: "40px", marginBottom: "10px" }}>
              ⚠️
            </div>

            <p
              style={{
                fontSize: "12px",
                fontWeight: 700,
                letterSpacing: "0.08em",
                color: "#2563eb",
                textTransform: "uppercase",
                margin: "0 0 8px",
              }}
            >
              {this.props.label || "Unexpected Error"}
            </p>

            <h1
              style={{
                fontSize: "24px",
                fontWeight: 800,
                margin: "0 0 10px",
              }}
            >
              This section hit a problem.
            </h1>

            <p
              style={{
                color: "#64748b",
                fontSize: "14px",
                margin: "0 0 20px",
              }}
            >
              {this.state.message}
            </p>

            <button
              onClick={this.handleReset}
              style={{
                border: "none",
                borderRadius: "10px",
                padding: "13px 24px",
                background: "#2563eb",
                color: "#ffffff",
                fontSize: "15px",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;

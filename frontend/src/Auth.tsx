import { useState } from "react";
import "./Auth.css";

const API_URL = "http://127.0.0.1:8000";

type AuthMode = "login" | "register";

type Props = {
  onBack: () => void;
  onAuthed: (
    token: string,
    user: { id: string; email: string; full_name?: string }
  ) => void;
};

function Auth({ onBack, onAuthed }: Props) {
  const [mode, setMode] = useState<AuthMode>("login");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const toggleMode = () => {
    setMode(mode === "login" ? "register" : "login");
    setError("");
    setNotice("");
  };

  const submit = async () => {
    setError("");
    setNotice("");
    setLoading(true);

    try {
      const endpoint =
        mode === "login" ? "/login" : "/register";

      const payload =
        mode === "login"
          ? { email, password }
          : { email, password, full_name: fullName };

      const response = await fetch(
        `${API_URL}/api/auth${endpoint}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        const detail =
          typeof data?.detail === "string"
            ? data?.detail
            : data?.detail?.[0]?.msg ||
              "Authentication failed.";

        throw new Error(detail);
      }

      // Registration may succeed without an
      // immediate session (email verification).
      if (!data.access_token) {
        setNotice(
          data.detail ||
            "Account created. Please verify your email."
        );
        return;
      }

      onAuthed(data.access_token, data.user);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to authenticate."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-app">
      <header className="auth-navbar">
        <button
          className="auth-back"
          onClick={onBack}
        >
          ←
        </button>

        <div className="auth-logo">
          Device<span>Value</span>
        </div>

        <div />
      </header>

      <main className="auth-page">
        <div className="auth-card">
          <div className="auth-icon">
            {mode === "login" ? "🔐" : "✨"}
          </div>

          <p className="auth-eyebrow">
            {mode === "login"
              ? "WELCOME BACK"
              : "CREATE ACCOUNT"}
          </p>

          <h1>
            {mode === "login"
              ? "Sign in to your account."
              : "Create your account."}
          </h1>

          <p className="auth-sub">
            {mode === "login"
              ? "Access your device valuations and inspections."
              : "Save and track every valuation you run."}
          </p>

          <div className="auth-fields">
            {mode === "register" && (
              <input
                className="auth-input"
                type="text"
                placeholder="Full name (optional)"
                value={fullName}
                onChange={(e) =>
                  setFullName(e.target.value)
                }
              />
            )}

            <input
              className="auth-input"
              type="email"
              placeholder="Email address"
              value={email}
              onChange={(e) =>
                setEmail(e.target.value)
              }
            />

            <input
              className="auth-input"
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) =>
                setPassword(e.target.value)
              }
              onKeyDown={(e) => {
                if (e.key === "Enter") submit();
              }}
            />
          </div>

          {error && (
            <div className="auth-error">{error}</div>
          )}

          {notice && (
            <div className="auth-notice">{notice}</div>
          )}

          <button
            className="auth-submit"
            onClick={submit}
            disabled={loading}
          >
            {loading
              ? "Processing..."
              : mode === "login"
              ? "Sign In"
              : "Create Account"}
          </button>

          <button
            className="auth-toggle"
            onClick={toggleMode}
          >
            {mode === "login"
              ? "New here? Create an account"
              : "Already have an account? Sign in"}
          </button>
        </div>
      </main>
    </div>
  );
}

export default Auth;

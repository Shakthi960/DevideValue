import { useEffect, useRef, useState } from "react";
import "./Auth.css";
import LoadingSpinner from "./components/LoadingSpinner";
import { getApiUrl } from "./config";
import { supabase, googleAuthEnabled } from "./lib/supabase";
import logo from "./logo.png";

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

  const googleChecked = useRef(false);

  useEffect(() => {
    if (!supabase || googleChecked.current) return;
    googleChecked.current = true;

    const completeGoogle = async (accessToken: string) => {
      try {
        const response = await fetch(
          getApiUrl("/api/auth/me"),
          {
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            typeof data?.detail === "string"
              ? data.detail
              : "Unable to load your account."
          );
        }

        onAuthed(accessToken, data);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load your account."
        );
        setLoading(false);
      }
    };

    supabase.auth.getSession().then(({ data }) => {
      if (data.session) {
        setLoading(true);
        completeGoogle(data.session.access_token);
      }
    });
  }, [onAuthed]);

  const signInWithGoogle = async () => {
    if (!supabase) return;

    setError("");
    setNotice("");
    setLoading(true);

    try {
      const { error: authError } =
        await supabase.auth.signInWithOAuth({
          provider: "google",
          options: {
            redirectTo: window.location.origin,
          },
        });

      if (authError) {
        throw new Error(authError.message);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to start Google sign-in."
      );
      setLoading(false);
    }
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
        getApiUrl(`/api/auth${endpoint}`),
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
          <img src={logo} alt="DeviceValue" className="brand-logo" />
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

          {googleAuthEnabled && (
            <>
              <button
                className="auth-google"
                onClick={signInWithGoogle}
                disabled={loading}
                type="button"
              >
                <svg
                  viewBox="0 0 48 48"
                  className="auth-google-icon"
                  aria-hidden="true"
                >
                  <path
                    fill="#EA4335"
                    d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
                  />
                  <path
                    fill="#4285F4"
                    d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
                  />
                  <path
                    fill="#34A853"
                    d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
                  />
                </svg>
                Continue with Google
              </button>

              <div className="auth-divider">
                <span>or</span>
              </div>
            </>
          )}

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

      {loading && (
        <LoadingSpinner
          overlay
          label={
            mode === "login"
              ? "Signing you in..."
              : "Creating your account..."
          }
        />
      )}
    </div>
  );
}

export default Auth;

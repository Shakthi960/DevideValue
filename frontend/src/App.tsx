import { useEffect, useState } from "react";
import "./App.css";
import FullInspection from "./FullInspection";
import JoinInspection from "./JoinInspection";
import Auth from "./Auth";
import ErrorBoundary from "./ErrorBoundary";
import { getApiUrl } from "./config";
import { supabase } from "./lib/supabase";
import logo from "./logo.png";

function App() {
  const [showFullInspection, setShowFullInspection] =
    useState(false);

  const [showJoinInspection, setShowJoinInspection] =
    useState(false);

  const [showAuth, setShowAuth] = useState(false);

  const [user, setUser] = useState<{
    id: string;
    email: string;
    full_name?: string;
  } | null>(null);

  const openAuth = () => setShowAuth(true);

  const closeAuth = () => setShowAuth(false);

  const handleAuthed = (
    _token: string,
    authedUser: {
      id: string;
      email: string;
      full_name?: string;
    }
  ) => {
    setUser(authedUser);
    setShowAuth(false);
  };

  const handleLogout = async () => {
    if (supabase) {
      await supabase.auth.signOut().catch(() => undefined);
    }
    setUser(null);
  };

  useEffect(() => {
    if (!supabase) return;

    supabase.auth.getSession().then(async ({ data }) => {
      if (!data.session) return;

      try {
        const response = await fetch(
          getApiUrl("/api/auth/me"),
          {
            headers: {
              Authorization: `Bearer ${data.session.access_token}`,
            },
          }
        );

        const user = await response.json();

        if (response.ok) {
          setUser(user);
        }
      } catch {
        /* ignore transient restore failures */
      }
    });
  }, []);

  const goHome = () => {
    setShowFullInspection(false);
    setShowJoinInspection(false);
  };

  // -----------------------------------------------------------------
  // AUTH
  // -----------------------------------------------------------------

  if (showAuth && !user) {
    return (
      <ErrorBoundary label="Authentication Error">
        <Auth
          onBack={closeAuth}
          onAuthed={handleAuthed}
        />
      </ErrorBoundary>
    );
  }

  // -----------------------------------------------------------------
  // FLOW PAGES
  // -----------------------------------------------------------------

  if (showFullInspection) {
    return (
      <ErrorBoundary label="Full Inspection Error">
        <FullInspection onBack={goHome} />
      </ErrorBoundary>
    );
  }

  if (showJoinInspection) {
    return (
      <ErrorBoundary label="Join Inspection Error">
        <JoinInspection onBack={goHome} />
      </ErrorBoundary>
    );
  }

  // -----------------------------------------------------------------
  // HOME PAGE
  // -----------------------------------------------------------------

  return (
    <div className="app">

      <header className="navbar">

        <div className="logo">
          <img src={logo} alt="DeviceValue" className="brand-logo" />
          Device<span>Value</span>
        </div>

        <nav>
          <a href="#home">Home</a>
          <a href="#how-it-works">How it works</a>
          <a href="#about">About</a>
        </nav>

        {user ? (
          <div className="user-menu">
            <span className="user-chip">
              {user.full_name || user.email.split("@")[0]}
            </span>
            <button className="login-btn" onClick={handleLogout}>
              Logout
            </button>
          </div>
        ) : (
          <button className="login-btn" onClick={openAuth}>
            Login
          </button>
        )}

      </header>

      <main>

        {/* ---- HERO ---- */}

        <section className="hero" id="home">

          <div className="hero-content">

            <div className="badge">AI-Powered Device Valuation</div>

            <h1>
              Know what your
              <br />
              <span>phone is worth.</span>
            </h1>

            <p>
              Get a full inspection: answer questions, take AI photos,
              run diagnostics, and get a single exchange + resale value.
              You'll need two phones — a phone can't photograph itself.
            </p>

            <div className="hero-buttons">
              <button
                className="primary-btn"
                onClick={() => setShowFullInspection(true)}
              >
                Phone Resale Value →
              </button>
              <button
                className="secondary-btn"
                onClick={() => setShowJoinInspection(true)}
              >
                Continue with a Code
              </button>
            </div>

          </div>

          <div className="hero-card">

            <div className="phone-icon">📱</div>

            <h3>Two phones. One platform.</h3>

            <div className="feature">
              <span>✓</span> 8-question condition check
            </div>

            <div className="feature">
              <span>✓</span> AI photo inspection (6 views)
            </div>

            <div className="feature">
              <span>✓</span> Device diagnostics
            </div>

            <div className="feature">
              <span>✓</span> Resale + exchange value
            </div>

          </div>

        </section>

        {/* ---- NOTICE BANNER ---- */}

        <section className="notice-banner">
          <div className="notice-content">
            <div className="notice-icon">ℹ</div>
            <div>
              <strong>You'll need a second phone.</strong> A phone
              can't photograph itself. Start on the phone where you
              want the result to appear, and keep it open — the other
              phone will join with a 6-digit code to take photos or run
              diagnostics.
            </div>
          </div>
        </section>

        {/* ---- HOW IT WORKS / MENUS ---- */}

        <section className="services" id="how-it-works">

          <div className="section-heading">
            <p>GET STARTED</p>
            <h2>
              Choose how you want to
              <br />
              evaluate your device.
            </h2>
          </div>

          <div className="service-grid">

            <div
              className="service-card featured"
              onClick={() => setShowFullInspection(true)}
            >
              <div className="service-icon">💰</div>
              <h3>Phone Resale Value</h3>
              <p>
                Answer questions, take AI photos with another phone,
                run diagnostics, and get a single exchange + resale
                value for your device.
              </p>
              <button onClick={(e) => { e.stopPropagation(); setShowFullInspection(true); }}>
                Start →
              </button>
            </div>

            <div
              className="service-card"
              onClick={() => setShowJoinInspection(true)}
            >
              <div className="service-icon">🔗</div>
              <h3>Continue with a Code</h3>
              <p>
                Your partner's phone taking photos or running
                diagnostics? Enter the 6-digit code here to do your
                part.
              </p>
              <button onClick={(e) => { e.stopPropagation(); setShowJoinInspection(true); }}>
                Continue →
              </button>
            </div>

          </div>

        </section>

      </main>

      <footer>

        <div className="logo">
          <img src={logo} alt="DeviceValue" className="brand-logo" />
          Device<span>Value</span>
        </div>

        <p>
          AI-powered smartphone inspection
          and valuation platform.
        </p>

        <p className="copyright">
          © 2026 DeviceValue
        </p>

      </footer>

    </div>
  );
}

export default App;
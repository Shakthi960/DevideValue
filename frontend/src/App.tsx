import { useEffect, useState } from "react";
import "./App.css";
import PhotoInspection from "./PhotoInspection";
import ExchangeInspection from "./ExchangeInspection";
import Diagnostics from "./Diagnostics";
import Auth from "./Auth";
import ErrorBoundary from "./ErrorBoundary";
import SelectOrCustom, { CUSTOM } from "./components/SelectOrCustom";

const API_URL = "http://127.0.0.1:8000";

type DeviceData = {
  brand: string;
  model: string;
  storage: string;
};

type Answers = {
  device_age: string;
  screen_condition: string;
  body_condition: string;
  battery_condition: string;
  functionality: string;
  original_charger: string;
  original_box: string;
  repair_history: string;
};

type ValuationResult = {
  inspection_code: string;
  resale_price: number;
  exchange_price: number;
  condition_score: number;
  condition_grade: string;
  device?: {
    brand: string;
    model: string;
    storage: string;
  };
};

const initialAnswers: Answers = {
  device_age: "",
  screen_condition: "",
  body_condition: "",
  battery_condition: "",
  functionality: "",
  original_charger: "",
  original_box: "",
  repair_history: "",
};

function App() {
  const [showQuickValue, setShowQuickValue] = useState(false);
  const [showPhotoInspection, setShowPhotoInspection] =
  useState(false);

  const [showExchangeInspection, setShowExchangeInspection] =
  useState(false);

  const [showDiagnostics, setShowDiagnostics] =
  useState(false);

  const [showAuth, setShowAuth] = useState(false);

  const [user, setUser] = useState<{
    id: string;
    email: string;
    full_name?: string;
  } | null>(null);

  const [step, setStep] = useState(1);

  const [device, setDevice] = useState<DeviceData>({
    brand: "",
    model: "",
    storage: "",
  });

  const [answers, setAnswers] =
    useState<Answers>(initialAnswers);

  const [inspectionCode, setInspectionCode] =
    useState<string | null>(null);

  const [result, setResult] =
    useState<ValuationResult | null>(null);

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");

  const [brands, setBrands] = useState<string[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [variants, setVariants] = useState<any[]>([]);

  const [customModel, setCustomModel] = useState("");
  const [customStorage, setCustomStorage] = useState("");

  const loadBrands = async () => {
    try {
      const response = await fetch(
        `${API_URL}/api/device-catalog/brands`
      );
      const data = await response.json();
      setBrands(Array.isArray(data?.items) ? data.items : []);
    } catch {
      setError("Unable to load device catalog.");
    }
  };

  useEffect(() => {
    loadBrands();
  }, []);

  const loadModels = async (selectedBrand: string) => {
    if (!selectedBrand) {
      setModels([]);
      setVariants([]);
      return;
    }

    try {
      const response = await fetch(
        `${API_URL}/api/device-catalog/brands/${encodeURIComponent(
          selectedBrand
        )}/models`
      );
      const data = await response.json();
      setModels(Array.isArray(data?.items) ? data.items : []);
    } catch {
      setError("Unable to load models.");
    }
  };

  const loadVariants = async (
    selectedBrand: string,
    selectedModel: string
  ) => {
    if (!selectedBrand || !selectedModel) {
      setVariants([]);
      return;
    }

    try {
      const response = await fetch(
        `${API_URL}/api/device-catalog/models/` +
          `${encodeURIComponent(selectedBrand)}/` +
          `${encodeURIComponent(selectedModel)}/variants`
      );
      const data = await response.json();
      setVariants(Array.isArray(data?.items) ? data.items : []);
    } catch {
      setError("Unable to load variants.");
    }
  };

  const resetDeviceSelection = (change: Partial<DeviceData>) => {
    setDevice((prev) => ({ ...prev, ...change }));
  };

  const totalSteps = 8;

  const updateAnswer = (
    key: keyof Answers,
    value: string
  ) => {
    setAnswers((previous) => ({
      ...previous,
      [key]: value,
    }));
  };

  const startQuickValue = () => {
    setShowQuickValue(true);
    setStep(1);
    setResult(null);
    setInspectionCode(null);
    setError("");
  };

  const goHome = () => {
    setShowQuickValue(false);
    setStep(1);
    setResult(null);
    setInspectionCode(null);
    setError("");
    setAnswers(initialAnswers);
  };

  const openAuth = () => {
    setShowAuth(true);
  };

  const closeAuth = () => {
    setShowAuth(false);
  };

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

  const handleLogout = () => {
    setUser(null);
  };

  const nextStep = () => {
    setError("");

    if (step === 1) {
      const effectiveModel =
        device.model === CUSTOM ? customModel.trim() : device.model;
      const effectiveStorage =
        device.storage === CUSTOM ? customStorage.trim() : device.storage;

      if (!device.brand || !effectiveModel || !effectiveStorage) {
        setError("Please select a brand, model and variant.");
        return;
      }
    }

    const answerKeys: Record<number, keyof Answers> = {
      2: "device_age",
      3: "screen_condition",
      4: "body_condition",
      5: "battery_condition",
      6: "functionality",
      7: "original_charger",
      8: "repair_history",
    };

    const key = answerKeys[step];

    if (key && !answers[key]) {
      setError("Please select an option to continue.");
      return;
    }

    if (step < totalSteps) {
      setStep(step + 1);
    }
  };

  const previousStep = () => {
    setError("");

    if (step > 1) {
      setStep(step - 1);
    }
  };

  const submitValuation = async () => {
    setError("");
    setLoading(true);

    try {
      /*
       * Step 1:
       * Create inspection and device
       */
      const inspectionResponse = await fetch(
        `${API_URL}/api/inspections`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            brand: device.brand,
            model:
              device.model === CUSTOM
                ? customModel.trim()
                : device.model,
            storage:
              device.storage === CUSTOM
                ? customStorage.trim()
                : device.storage,
            inspection_type: "quick_value",
          }),
        }
      );

      if (!inspectionResponse.ok) {
        throw new Error(
          "Unable to create inspection."
        );
      }

      const inspection =
        await inspectionResponse.json();

      setInspectionCode(
        inspection.inspection_code
      );

      /*
       * Step 2:
       * Submit questionnaire answers
       */
      const answerList = Object.entries(
        answers
      ).map(([question_key, answer_value]) => ({
        question_key,
        answer_value,
      }));

      const valuationResponse = await fetch(
        `${API_URL}/api/inspections/${inspection.inspection_code}/answers`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            answers: answerList,
          }),
        }
      );

      if (!valuationResponse.ok) {
        throw new Error(
          "Unable to calculate device value."
        );
      }

      const valuation =
        await valuationResponse.json();

      setResult(valuation);
    } catch (err) {
      console.error(err);

      setError(
        "Unable to connect to the valuation server. Make sure FastAPI is running."
      );
    } finally {
      setLoading(false);
    }
  };

  /*
   * -------------------------
   * HOME PAGE
   * -------------------------
   */
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

  if (showDiagnostics) {
    return (
      <ErrorBoundary label="Diagnostics Error">
        <Diagnostics
          onBack={() => setShowDiagnostics(false)}
        />
      </ErrorBoundary>
    );
  }

  if (showExchangeInspection) {
    return (
      <ErrorBoundary label="Exchange Inspection Error">
        <ExchangeInspection
          onBack={() => setShowExchangeInspection(false)}
        />
      </ErrorBoundary>
    );
  }

  if (showPhotoInspection) {
    return (
      <ErrorBoundary label="Photo Inspection Error">
        <PhotoInspection
          onBack={() =>
            setShowPhotoInspection(false)
          }
        />
      </ErrorBoundary>
    );
  }

  if (!showQuickValue) {
    return (
      <div className="app">

        <header className="navbar">

          <div className="logo">
            Device<span>Value</span>
          </div>

          <nav>
            <a href="#home">Home</a>
            <a href="#how-it-works">
              How it works
            </a>
            <a href="#about">
              About
            </a>
          </nav>

          {user ? (
            <div className="user-menu">
              <span className="user-chip">
                {user.full_name || user.email.split("@")[0]}
              </span>

              <button
                className="login-btn"
                onClick={handleLogout}
              >
                Logout
              </button>
            </div>
          ) : (
            <button
              className="login-btn"
              onClick={openAuth}
            >
              Login
            </button>
          )}

        </header>

        <main>

          <section
            className="hero"
            id="home"
          >

            <div className="hero-content">

              <div className="badge">
                AI-Powered Device Valuation
              </div>

              <h1>
                Know what your
                <br />
                <span>phone is worth.</span>
              </h1>

              <p>
                Get a quick resale estimate,
                perform a detailed device
                inspection, or run complete
                diagnostics — all in one place.
              </p>

              <div className="hero-buttons">

                <button
                  className="primary-btn"
                  onClick={startQuickValue}
                >
                  Check Device Value →
                </button>

                <button
                  className="secondary-btn"
                  onClick={() => setShowDiagnostics(true)}
                >
                  Run Diagnostics
                </button>

              </div>

            </div>

            <div className="hero-card">

              <div className="phone-icon">
                📱
              </div>

              <h3>
                One device. One platform.
              </h3>

              <div className="feature">
                <span>✓</span>
                Quick valuation
              </div>

              <div className="feature">
                <span>✓</span>
                AI photo inspection
              </div>

              <div className="feature">
                <span>✓</span>
                Device diagnostics
              </div>

              <div className="feature">
                <span>✓</span>
                Resale + exchange value
              </div>

            </div>

          </section>

          <section
            className="services"
            id="how-it-works"
          >

            <div className="section-heading">

              <p>
                WHAT DO YOU NEED?
              </p>

              <h2>
                Choose how you want to
                <br />
                evaluate your device.
              </h2>

            </div>

            <div className="service-grid">

              <div
                className="service-card"
                onClick={startQuickValue}
              >

                <div className="service-icon">
                  💰
                </div>

                <h3>
                  Quick Value
                </h3>

                <p>
                  Answer a few simple questions
                  and get an estimated resale
                  and exchange value.
                </p>

                <button>
                  Start →
                </button>

              </div>

              <div className="service-card featured" onClick={() => setShowPhotoInspection(true)}>

                <div className="service-icon">
                  📷
                </div>

                <h3>
                  AI Photo Valuation
                </h3>

                <p>
                  Take guided photos of your
                  device and let AI analyze
                  its physical condition.
                </p>

                <button onClick={(e) => {e.stopPropagation(); setShowPhotoInspection(true);}}>Start →</button>

              </div>

              <div
                className="service-card"
                onClick={() => setShowExchangeInspection(true)}
              >

                <div className="service-icon">
                  🔄
                </div>

                <h3>
                  Exchange Inspection
                </h3>

                <p>
                  Complete inspection with
                  photographs, diagnostics and
                  final exchange valuation.
                </p>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowExchangeInspection(true);
                  }}
                >
                  Start →
                </button>
              </div>

              <div
                className="service-card"
                onClick={() => setShowDiagnostics(true)}
              >

                <div className="service-icon">
                  🔍
                </div>

                <h3>
                  Device Diagnostics
                </h3>

                <p>
                  Run browser-based sensor checks
                  and self-report on your hardware.
                </p>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowDiagnostics(true);
                  }}
                >
                  Start →
                </button>

              </div>

            </div>

          </section>

        </main>

        <footer>

          <div className="logo">
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

  /*
   * -------------------------
   * VALUATION RESULT
   * -------------------------
   */

  if (result) {
    return (
      <div className="app">

        <header className="navbar">

          <div className="logo">
            Device<span>Value</span>
          </div>

          <button
            className="login-btn"
            onClick={goHome}
          >
            Home
          </button>

        </header>

        <main className="result-page">

          <div className="result-card">

            <div className="success-icon">
              ✓
            </div>

            <p className="result-label">
              DEVICE VALUATION COMPLETE
            </p>

            <h1>
              Here's what your phone is worth.
            </h1>

            <p className="result-description">
              Based on the information you provided,
              here's our current estimate.
            </p>

            {result.device && (
              <div className="valued-device">
                <span>Valuing:</span>
                <strong>
                  {result.device.brand}{" "}
                  {result.device.model}
                </strong>
                <small>
                  {result.device.storage} · condition{" "}
                  {result.condition_grade}
                </small>
              </div>
            )}

            <div className="price-grid">

              <div className="price-box">

                <span>
                  Estimated Resale Value
                </span>

                <strong>
                  ₹{result.resale_price.toLocaleString(
                    "en-IN"
                  )}
                </strong>

                <small>
                  Expected market resale value
                </small>

              </div>

              <div className="price-box exchange">

                <span>
                  Estimated Exchange Value
                </span>

                <strong>
                  ₹{result.exchange_price.toLocaleString(
                    "en-IN"
                  )}
                </strong>

                <small>
                  Recommended exchange value
                </small>

              </div>

            </div>

            <div className="condition-result">

              <div>
                <span>
                  Condition Score
                </span>

                <strong>
                  {result.condition_score}/100
                </strong>
              </div>

              <div>
                <span>
                  Condition Grade
                </span>

                <strong>
                  {result.condition_grade}
                </strong>
              </div>

            </div>

            <div className="inspection-code">

              <span>
                Inspection Code
              </span>

              <strong>
                {inspectionCode}
              </strong>

            </div>

            <p className="next-step">
              This estimate uses current market data for the
              exact model and storage variant selected above.
            </p>

            <button
              className="primary-btn full-width"
              onClick={goHome}
            >
              Done
            </button>

          </div>

        </main>

      </div>
    );
  }

  /*
   * -------------------------
   * QUICK VALUE QUESTIONS
   * -------------------------
   */

  const renderStep = () => {

    switch (step) {

      case 1:
        return (
          <>
            <p className="step-label">
              STEP 1 OF 8
            </p>

            <h1>
              Tell us about your device.
            </h1>

            <p className="question-description">
              We'll use this information as the
              starting point for your valuation.
            </p>

            <div className="form-group">
              <label>Brand</label>

              <select
                value={device.brand}
                onChange={(e) => {
                  const value = e.target.value;
                  resetDeviceSelection({
                    brand: value,
                    model: "",
                    storage: "",
                  });
                  setCustomModel("");
                  setCustomStorage("");
                  loadModels(value);
                }}
              >
                <option value="">
                  Select brand
                </option>

                {brands.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label>Model</label>

              <SelectOrCustom
                value={device.model}
                onValueChange={(value) => {
                  resetDeviceSelection({
                    model: value,
                    storage: "",
                  });

                  if (value === CUSTOM) {
                    setCustomStorage("");
                    setVariants([]);
                  } else {
                    loadVariants(device.brand, value);
                  }
                }}
                customValue={customModel}
                onCustomChange={(value) =>
                  setCustomModel(value)
                }
                options={models}
                disabled={!models.length}
                placeholder="Select model"
                customPlaceholder="Type your model, e.g. Y200e 5G"
              />
            </div>

            <div className="form-group">
              <label>Variant</label>

              <SelectOrCustom
                value={device.storage}
                onValueChange={(value) =>
                  resetDeviceSelection({ storage: value })
                }
                customValue={customStorage}
                onCustomChange={(value) =>
                  setCustomStorage(value)
                }
                options={variants.map((v: any) => v.variant_name || v.storage || "")}
                disabled={
                  !device.model ||
                  (device.model !== CUSTOM && !variants.length)
                }
                placeholder={
                  device.model === CUSTOM
                    ? "Select variant (or Others)"
                    : "Select variant"
                }
                customPlaceholder="Type RAM + storage, e.g. 8GB + 128GB"
                optionLabel={(val) => val || "—"}
              />
            </div>
          </>
        );

      case 2:
        return (
          <Question
            step="STEP 2 OF 8"
            title="How old is your phone?"
            description="Approximate purchase age is enough."
            value={answers.device_age}
            onChange={(value) =>
              updateAnswer(
                "device_age",
                value
              )
            }
            options={[
              [
                "less_than_6_months",
                "Less than 6 months",
              ],
              [
                "6_to_12_months",
                "6–12 months",
              ],
              [
                "1_to_2_years",
                "1–2 years",
              ],
              [
                "2_to_3_years",
                "2–3 years",
              ],
              [
                "more_than_3_years",
                "More than 3 years",
              ],
            ]}
          />
        );

      case 3:
        return (
          <Question
            step="STEP 3 OF 8"
            title="How is the screen?"
            description="Choose the condition that best matches your display."
            value={answers.screen_condition}
            onChange={(value) =>
              updateAnswer(
                "screen_condition",
                value
              )
            }
            options={[
              [
                "excellent",
                "Excellent — no visible damage",
              ],
              [
                "minor_scratches",
                "Minor scratches",
              ],
              [
                "scratched",
                "Noticeably scratched",
              ],
              [
                "cracked",
                "Cracked",
              ],
              [
                "display_problem",
                "Display problem",
              ],
            ]}
          />
        );

      case 4:
        return (
          <Question
            step="STEP 4 OF 8"
            title="How is the body?"
            description="Consider the back, frame and corners."
            value={answers.body_condition}
            onChange={(value) =>
              updateAnswer(
                "body_condition",
                value
              )
            }
            options={[
              [
                "excellent",
                "Excellent — almost no marks",
              ],
              [
                "minor_scratches",
                "Minor scratches",
              ],
              [
                "multiple_scratches",
                "Multiple scratches",
              ],
              [
                "minor_dents",
                "Minor dents",
              ],
              [
                "major_damage",
                "Major dents or damage",
              ],
            ]}
          />
        );

      case 5:
        return (
          <Question
            step="STEP 5 OF 8"
            title="How is the battery?"
            description="Choose the closest option."
            value={answers.battery_condition}
            onChange={(value) =>
              updateAnswer(
                "battery_condition",
                value
              )
            }
            options={[
              [
                "excellent",
                "Excellent",
              ],
              [
                "good",
                "Good",
              ],
              [
                "below_80",
                "Below 80%",
              ],
              [
                "replaced",
                "Battery has been replaced",
              ],
              [
                "unknown",
                "I don't know",
              ],
            ]}
          />
        );

      case 6:
        return (
          <Question
            step="STEP 6 OF 8"
            title="Does everything work?"
            description="Think about the main functions of the phone."
            value={answers.functionality}
            onChange={(value) =>
              updateAnswer(
                "functionality",
                value
              )
            }
            options={[
              [
                "yes",
                "Yes, everything works",
              ],
              [
                "no",
                "No, something doesn't work",
              ],
              [
                "not_sure",
                "I'm not sure",
              ],
            ]}
          />
        );

      case 7:
        return (
          <>
            <p className="step-label">
              STEP 7 OF 8
            </p>

            <h1>
              What came with the phone?
            </h1>

            <p className="question-description">
              Accessories can slightly affect
              the exchange value.
            </p>

            <OptionGroup
              title="Original charger available?"
              value={answers.original_charger}
              onChange={(value) =>
                updateAnswer(
                  "original_charger",
                  value
                )
              }
              options={[
                ["yes", "Yes"],
                ["no", "No"],
              ]}
            />

            <OptionGroup
              title="Original box available?"
              value={answers.original_box}
              onChange={(value) =>
                updateAnswer(
                  "original_box",
                  value
                )
              }
              options={[
                ["yes", "Yes"],
                ["no", "No"],
              ]}
            />
          </>
        );

      case 8:
        return (
          <Question
            step="STEP 8 OF 8"
            title="Has the phone been repaired?"
            description="Include screen, battery or internal repairs."
            value={answers.repair_history}
            onChange={(value) =>
              updateAnswer(
                "repair_history",
                value
              )
            }
            options={[
              [
                "no",
                "No repairs",
              ],
              [
                "authorized",
                "Yes — authorized service",
              ],
              [
                "third_party",
                "Yes — third-party service",
              ],
              [
                "unknown",
                "I don't know",
              ],
            ]}
          />
        );

      default:
        return null;
    }
  };

  return (
    <div className="app">

      <header className="navbar">

        <div className="logo">
          Device<span>Value</span>
        </div>

        <button
          className="login-btn"
          onClick={goHome}
        >
          Cancel
        </button>

      </header>

      <main className="question-page">

        <div className="progress-container">

          <div className="progress-info">

            <span>
              Device valuation
            </span>

            <span>
              {step} / {totalSteps}
            </span>

          </div>

          <div className="progress-bar">

            <div
              className="progress-fill"
              style={{
                width: `${
                  (step / totalSteps) * 100
                }%`,
              }}
            />

          </div>

        </div>

        <div className="question-card">

          {renderStep()}

          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          <div className="question-actions">

            {step > 1 ? (
              <button
                className="secondary-btn"
                onClick={previousStep}
                disabled={loading}
              >
                ← Back
              </button>
            ) : (
              <button
                className="secondary-btn"
                onClick={goHome}
                disabled={loading}
              >
                Cancel
              </button>
            )}

            {step < totalSteps ? (
              <button
                className="primary-btn"
                onClick={nextStep}
                disabled={loading}
              >
                Continue →
              </button>
            ) : (
              <button
                className="primary-btn"
                onClick={submitValuation}
                disabled={loading}
              >
                {loading
                  ? "Analyzing..."
                  : "Analyze Device →"}
              </button>
            )}

          </div>

        </div>

      </main>

    </div>
  );
}


/*
 * Reusable question component
 */

function Question({
  step,
  title,
  description,
  value,
  onChange,
  options,
}: {
  step: string;
  title: string;
  description: string;
  value: string;
  onChange: (value: string) => void;
  options: [string, string][];
}) {
  return (
    <>
      <p className="step-label">
        {step}
      </p>

      <h1>
        {title}
      </h1>

      <p className="question-description">
        {description}
      </p>

      <div className="option-list">

        {options.map(
          ([optionValue, label]) => (
            <button
              type="button"
              key={optionValue}
              className={`option-button ${
                value === optionValue
                  ? "selected"
                  : ""
              }`}
              onClick={() =>
                onChange(optionValue)
              }
            >
              <span className="radio">
                {value === optionValue
                  ? "✓"
                  : ""}
              </span>

              {label}
            </button>
          )
        )}

      </div>
    </>
  );
}


/*
 * Reusable option group
 */

function OptionGroup({
  title,
  value,
  onChange,
  options,
}: {
  title: string;
  value: string;
  onChange: (value: string) => void;
  options: [string, string][];
}) {
  return (
    <div className="option-group">

      <h3>
        {title}
      </h3>

      <div className="small-options">

        {options.map(
          ([optionValue, label]) => (
            <button
              type="button"
              key={optionValue}
              className={`small-option ${
                value === optionValue
                  ? "selected"
                  : ""
              }`}
              onClick={() =>
                onChange(optionValue)
              }
            >
              {value === optionValue
                ? "✓ "
                : ""}
              {label}
            </button>
          )
        )}

      </div>

    </div>
  );
}

export default App;
import { useEffect, useRef, useState } from "react";
import "./ExchangeInspection.css";
import SelectOrCustom, { CUSTOM } from "./components/SelectOrCustom";

const API_URL = "http://127.0.0.1:8000";

type Phase =
  | "device"
  | "questions"
  | "photos"
  | "result";

type PhotoType =
  | "front"
  | "back"
  | "left"
  | "right"
  | "top"
  | "bottom";

const PHOTO_SLOTS: { type: PhotoType; title: string }[] = [
  { type: "front", title: "Front" },
  { type: "back", title: "Back" },
  { type: "left", title: "Left" },
  { type: "right", title: "Right" },
  { type: "top", title: "Top" },
  { type: "bottom", title: "Bottom" },
];

type AnswerKey =
  | "device_age"
  | "screen_condition"
  | "body_condition"
  | "battery_condition"
  | "functionality"
  | "original_charger"
  | "original_box"
  | "repair_history";

const QUESTIONS: {
  key: AnswerKey;
  title: string;
  step: string;
  options: [string, string][];
}[] = [
  {
    key: "device_age",
    title: "How old is your phone?",
    step: "STEP 1 OF 8",
    options: [
      ["less_than_6_months", "Less than 6 months"],
      ["6_to_12_months", "6–12 months"],
      ["1_to_2_years", "1–2 years"],
      ["2_to_3_years", "2–3 years"],
      ["more_than_3_years", "More than 3 years"],
    ],
  },
  {
    key: "screen_condition",
    title: "How is the screen?",
    step: "STEP 2 OF 8",
    options: [
      ["excellent", "Excellent — no visible damage"],
      ["minor_scratches", "Minor scratches"],
      ["scratched", "Noticeably scratched"],
      ["cracked", "Cracked"],
      ["display_problem", "Display problem"],
    ],
  },
  {
    key: "body_condition",
    title: "How is the body?",
    step: "STEP 3 OF 8",
    options: [
      ["excellent", "Excellent — almost no marks"],
      ["minor_scratches", "Minor scratches"],
      ["multiple_scratches", "Multiple scratches"],
      ["minor_dents", "Minor dents"],
      ["major_damage", "Major dents or damage"],
    ],
  },
  {
    key: "battery_condition",
    title: "How is the battery?",
    step: "STEP 4 OF 8",
    options: [
      ["excellent", "Excellent"],
      ["good", "Good"],
      ["below_80", "Below 80%"],
      ["replaced", "Battery has been replaced"],
      ["unknown", "I don't know"],
    ],
  },
  {
    key: "functionality",
    title: "Does everything work?",
    step: "STEP 5 OF 8",
    options: [
      ["yes", "Yes, everything works"],
      ["no", "No, something doesn't work"],
      ["not_sure", "I'm not sure"],
    ],
  },
  {
    key: "original_charger",
    title: "Original charger available?",
    step: "STEP 6 OF 8",
    options: [
      ["yes", "Yes"],
      ["no", "No"],
    ],
  },
  {
    key: "original_box",
    title: "Original box available?",
    step: "STEP 7 OF 8",
    options: [
      ["yes", "Yes"],
      ["no", "No"],
    ],
  },
  {
    key: "repair_history",
    title: "Has the phone been repaired?",
    step: "STEP 8 OF 8",
    options: [
      ["no", "No repairs"],
      ["authorized", "Yes — authorized service"],
      ["third_party", "Yes — third-party service"],
      ["unknown", "I don't know"],
    ],
  },
];

type Props = {
  onBack: () => void;
};

function ExchangeInspection({ onBack }: Props) {
  const [phase, setPhase] = useState<Phase>("device");

  const [brand, setBrand] = useState("");
  const [model, setModel] = useState("");
  const [storage, setStorage] = useState("");

  const [brands, setBrands] = useState<string[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [variants, setVariants] = useState<any[]>([]);

  const [customModel, setCustomModel] = useState("");
  const [customStorage, setCustomStorage] = useState("");

  const [inspectionCode, setInspectionCode] =
    useState<string | null>(null);

  const [qIndex, setQIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const [currentIndex, setCurrentIndex] = useState(0);
  const [photos, setPhotos] = useState<Record<string, string>>({});

  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [deviceChecking, setDeviceChecking] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const currentPhoto = PHOTO_SLOTS[currentIndex];
  const currentQ = QUESTIONS[qIndex];

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
    setModel("");
    setStorage("");
    setModels([]);
    setVariants([]);
    setCustomModel("");
    setCustomStorage("");

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

  const loadVariants = async (selectedModel: string) => {
    if (!brand || !selectedModel) {
      setVariants([]);
      return;
    }

    setStorage("");
    setVariants([]);

    try {
      const response = await fetch(
        `${API_URL}/api/device-catalog/models/` +
          `${encodeURIComponent(brand)}/` +
          `${encodeURIComponent(selectedModel)}/variants`
      );
      const data = await response.json();
      setVariants(Array.isArray(data?.items) ? data.items : []);
    } catch {
      setError("Unable to load variants.");
    }
  };

  const startQuestions = async () => {
    const effectiveModel =
      model === CUSTOM ? customModel.trim() : model;
    const effectiveStorage =
      storage === CUSTOM ? customStorage.trim() : storage;

    if (!brand || !effectiveModel || !effectiveStorage) {
      setError("Please select a brand, model and variant.");
      return;
    }

    setDeviceChecking(true);
    setError("");

    try {
      const params = new URLSearchParams({
        brand,
        model: effectiveModel,
        storage: effectiveStorage,
      });

      const checkResponse = await fetch(
        `${API_URL}/api/device-prices?${params.toString()}`
      );

      const checkData = checkResponse.ok
        ? await checkResponse.json()
        : null;

      if (checkData?.resolution === "not_found") {
        setError(
          `Couldn't verify "${effectiveModel}" as a real phone. ` +
            "Check the spelling or pick the closest model from the list."
        );
        return;
      }
    } catch {
      // Verification unavailable - allow fallback path.
    } finally {
      setDeviceChecking(false);
    }

    setQIndex(0);
    setPhase("questions");
  };

  const answerCurrent = (value: string) => {
    setAnswers((prev) => ({
      ...prev,
      [currentQ.key]: value,
    }));

    if (qIndex < QUESTIONS.length - 1) {
      setQIndex(qIndex + 1);
    }
  };

  const createInspection = async () => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/api/inspections`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            brand,
            model:
              model === CUSTOM
                ? customModel.trim()
                : model,
            storage:
              storage === CUSTOM
                ? customStorage.trim()
                : storage,
            inspection_type: "exchange_inspection",
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error("Unable to create inspection.");
      }

      setInspectionCode(data.inspection_code);
      setPhotos({});
      setCurrentIndex(0);
      setPhase("photos");
    } catch {
      setError(
        "Unable to connect to the server. Make sure FastAPI is running."
      );
    } finally {
      setLoading(false);
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => {
        track.stop();
      });
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

  const startCamera = async () => {
    setError("");
    stopCamera();

    try {
      const stream =
        await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: "environment" },
          },
        });

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch {
      setError(
        "Unable to access the camera. Please allow camera permissions."
      );
    }
  };

  const captureAndUpload = async () => {
    if (!inspectionCode) {
      setError("Inspection has not been created.");
      return;
    }

    const video = videoRef.current;
    const canvas = canvasRef.current;

    if (!video || !canvas) {
      setError("Camera is not ready.");
      return;
    }

    if (video.videoWidth === 0) {
      setError("Camera is still starting.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;

      const context = canvas.getContext("2d");

      if (!context) {
        throw new Error("Unable to capture frame.");
      }

      context.drawImage(
        video,
        0,
        0,
        canvas.width,
        canvas.height
      );

      const blob = await new Promise<Blob | null>((resolve) => {
        canvas.toBlob(resolve, "image/jpeg", 0.92);
      });

      if (!blob) {
        throw new Error("Unable to create image.");
      }

      const formData = new FormData();
      formData.append(
        "file",
        blob,
        `${currentPhoto.type}.jpg`
      );

      const url =
        `${API_URL}/api/inspections/` +
        `${inspectionCode}/photos` +
        `?photo_type=${currentPhoto.type}`;

      const response = await fetch(url, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData =
          await response.json().catch(() => null);
        throw new Error(
          errorData?.detail || "Photo upload failed."
        );
      }

      const previewUrl = URL.createObjectURL(blob);

      setPhotos((prev) => ({
        ...prev,
        [currentPhoto.type]: previewUrl,
      }));

      stopCamera();

      if (currentIndex < PHOTO_SLOTS.length - 1) {
        setCurrentIndex(currentIndex + 1);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Photo capture failed."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    return () => stopCamera();
  }, []);

  const allPhotosCaptured =
    Object.keys(photos).length === PHOTO_SLOTS.length;

  const submitExchangeValuation = async () => {
    if (!inspectionCode) {
      setError("Inspection code is missing.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const answerList = Object.entries(answers).map(
        ([key, value]) => ({
          question_key: key,
          answer_value: value,
        })
      );

      const response = await fetch(
        `${API_URL}/api/inspections/${inspectionCode}/exchange-valuate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ answers: answerList }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data?.detail === "string"
            ? data.detail
            : "Exchange valuation failed."
        );
      }

      setResult(data);
      setPhase("result");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to calculate exchange value."
      );
    } finally {
      setLoading(false);
    }
  };

  // ============================================================
  // DEVICE PHASE
  // ============================================================

  if (phase === "device") {
    return (
      <div className="xi-app">
        <header className="xi-navbar">
          <button className="xi-back" onClick={onBack}>
            ←
          </button>
          <div className="xi-logo">
            Device<span>Value</span>
          </div>
          <div />
        </header>

        <main className="xi-page">
          <div className="xi-card">
            <p className="xi-eyebrow">EXCHANGE INSPECTION</p>
            <h1>Select your device.</h1>
            <p className="xi-sub">
              We'll combine your answers and live photos to
              calculate a final exchange value.
            </p>

            <label className="xi-label">Brand</label>
            <select
              className="xi-select"
              value={brand}
              onChange={(e) => {
                setBrand(e.target.value);
                loadModels(e.target.value);
              }}
            >
              <option value="">Select brand</option>
              {brands.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>

            <label className="xi-label">Model</label>
            <SelectOrCustom
              className="xi-select"
              value={model}
              onValueChange={(value) => {
                setModel(value);
                setCustomStorage("");

                if (value === CUSTOM) {
                  setVariants([]);
                  setStorage("");
                } else {
                  loadVariants(value);
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

            <label className="xi-label">Variant</label>
            <SelectOrCustom
              className="xi-select"
              value={storage}
              onValueChange={(value) => setStorage(value)}
              customValue={customStorage}
              onCustomChange={(value) =>
                setCustomStorage(value)
              }
              options={variants.map((v: any) => v.variant_name || v.storage || "")}
              disabled={
                model === "" ||
                (model !== CUSTOM && !variants.length)
              }
              placeholder={
                model === CUSTOM
                  ? "Select variant (or Others)"
                  : "Select variant"
              }
              customPlaceholder="Type RAM + storage, e.g. 8GB + 128GB"
              optionLabel={(val) => val || "—"}
            />

            {error && <div className="xi-error">{error}</div>}

            <button
              className="xi-primary-btn"
              onClick={startQuestions}
              disabled={deviceChecking}
            >
              {deviceChecking
                ? "Checking device…"
                : "Continue →"}
            </button>
          </div>
        </main>
      </div>
    );
  }

  // ============================================================
  // QUESTIONS PHASE
  // ============================================================

  if (phase === "questions") {
    const lastQuestion = qIndex >= QUESTIONS.length - 1;

    return (
      <div className="xi-app">
        <header className="xi-navbar">
          <button
            className="xi-back"
            onClick={() => {
              if (qIndex > 0) setQIndex(qIndex - 1);
              else setPhase("device");
            }}
          >
            ←
          </button>
          <div className="xi-logo">
            Device<span>Value</span>
          </div>
          <div className="xi-progress">
            {qIndex + 1}/{QUESTIONS.length}
          </div>
        </header>

        <main className="xi-question-page">
          <div className="xi-progress-bar">
            <div
              className="xi-progress-fill"
              style={{
                width: `${((qIndex + 1) / QUESTIONS.length) * 100}%`,
              }}
            />
          </div>

          <div className="xi-question-card">
            <p className="xi-eyebrow">{currentQ.step}</p>
            <h1>{currentQ.title}</h1>

            <div className="xi-options">
              {currentQ.options.map(([value, label]) => (
                <button
                  key={value}
                  className={`xi-option ${
                    answers[currentQ.key] === value
                      ? "selected"
                      : ""
                  }`}
                  onClick={() => answerCurrent(value)}
                >
                  {label}
                </button>
              ))}
            </div>

            {lastQuestion && (
              <button
                className="xi-primary-btn"
                onClick={createInspection}
                disabled={loading}
              >
                {loading
                  ? "Setting up camera..."
                  : "Continue to Photos →"}
              </button>
            )}
          </div>
        </main>
      </div>
    );
  }

  // ============================================================
  // PHOTOS PHASE
  // ============================================================

  if (phase === "photos") {
    return (
      <div className="xi-app">
        <header className="xi-navbar">
          <button
            className="xi-back"
            onClick={() => {
              stopCamera();
              setPhase("questions");
            }}
          >
            ←
          </button>
          <div className="xi-logo">
            Device<span>Value</span>
          </div>
          <div>{Object.keys(photos).length}/6</div>
        </header>

        <main className="xi-camera-page">
          <div className="xi-camera-card">
            <p className="xi-eyebrow">STEP {currentIndex + 1} OF 6</p>
            <h1>{currentPhoto.title} view</h1>
            <p className="xi-sub">
              Center your phone and capture the complete{" "}
              {currentPhoto.title.toLowerCase()} view.
            </p>

            <div className="xi-camera-box">
              <video
                ref={videoRef}
                className="xi-video"
                playsInline
                onCanPlay={() => {
                  if (streamRef.current) {
                    streamRef.current
                      .getVideoTracks()[0]
                      ?.applyConstraints({
                        facingMode: { ideal: "environment" },
                      });
                  }
                }}
              />
              <div className="xi-frame-overlay">
                {currentPhoto.title}
              </div>
            </div>

            <canvas ref={canvasRef} className="xi-canvas" />

            {!photos[currentPhoto.type] ? (
              <div className="xi-camera-actions">
                <button
                  className="xi-primary-btn"
                  onClick={startCamera}
                >
                  Open Camera
                </button>
                <button
                  className="xi-capture-btn"
                  onClick={captureAndUpload}
                  disabled={loading}
                >
                  {loading ? "Capturing..." : "📷 Capture"}
                </button>
              </div>
            ) : (
              <div className="xi-camera-actions">
                <span className="xi-captured">
                  ✓ {currentPhoto.title} captured
                </span>
                <button
                  className="xi-primary-btn"
                  onClick={() => {
                    setPhotos((prev) => {
                      const next = { ...prev };
                      delete next[currentPhoto.type];
                      return next;
                    });
                    setCurrentIndex(currentIndex);
                  }}
                >
                  Retake
                </button>
                {currentIndex < PHOTO_SLOTS.length - 1 && (
                  <button
                    className="xi-primary-btn"
                    onClick={() =>
                      setCurrentIndex(currentIndex + 1)
                    }
                  >
                    Next →
                  </button>
                )}
              </div>
            )}

            {error && <div className="xi-error">{error}</div>}

            {allPhotosCaptured && (
              <button
                className="xi-submit-btn"
                onClick={submitExchangeValuation}
                disabled={loading}
              >
                {loading
                  ? "Calculating Value..."
                  : "Get Final Exchange Value →"}
              </button>
            )}
          </div>
        </main>
      </div>
    );
  }

  // ============================================================
  // RESULT PHASE
  // ============================================================

  return (
    <div className="xi-app">
      <header className="xi-navbar">
        <button className="xi-back" onClick={onBack}>
          ←
        </button>
        <div className="xi-logo">
          Device<span>Value</span>
        </div>
        <div />
      </header>

      <main className="xi-page">
        <div className="xi-result">
          <p className="xi-eyebrow">EXCHANGE VALUATION COMPLETE</p>

          <h1>
            Your {brand} {model}
          </h1>

          <div className="xi-result-card">
            <div className="xi-result-main">
              <div className="xi-result-price">
                ₹
                {result?.exchange_price?.toLocaleString(
                  "en-IN"
                ) ?? 0}
              </div>
              <div className="xi-result-label">
                Estimated Exchange Value
              </div>
            </div>

            <div className="xi-result-details">
              <div>
                Resale value:{" "}
                <strong>
                  ₹
                  {result?.resale_price?.toLocaleString(
                    "en-IN"
                  ) ?? 0}
                </strong>
              </div>
              <div>
                Market price:{" "}
                <strong>
                  ₹
                  {result?.market_price?.toLocaleString(
                    "en-IN"
                  ) ?? 0}
                </strong>
              </div>
              {result?.new_price_inr && (
                <div>
                  New price today:{" "}
                  <strong>
                    ₹{result.new_price_inr.toLocaleString("en-IN")}
                  </strong>
                </div>
              )}
              {result?.price_source && (
                <div className="xi-result-detail-small">
                  {result.price_source}
                </div>
              )}
              <div>
                Condition score:{" "}
                <strong>{result?.condition_score}/100</strong>
              </div>
              <div>
                Condition grade:{" "}
                <strong>{result?.condition_grade}</strong>
              </div>
              <div>
                Questionnaire score:{" "}
                <strong>{result?.questionnaire_score}/100</strong>
              </div>
              <div>
                AI photo score:{" "}
                <strong>{result?.ai_condition_score}/100</strong>
              </div>
            </div>

            <div className="xi-inspection-code">
              Inspection: {result?.inspection_code}
            </div>
          </div>

          <button className="xi-primary-btn" onClick={onBack}>
            Done
          </button>
        </div>
      </main>
    </div>
  );
}

export default ExchangeInspection;

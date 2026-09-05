import { useEffect, useRef, useState } from "react";
import "./PhotoInspection.css";
import SelectOrCustom, { CUSTOM } from "./components/SelectOrCustom";

const API_URL = "http://127.0.0.1:8000";

type PhotoType =
  | "front"
  | "back"
  | "left"
  | "right"
  | "top"
  | "bottom";

type PhotoSlot = {
  type: PhotoType;
  title: string;
  description: string;
};

const PHOTO_SLOTS: PhotoSlot[] = [
  {
    type: "front",
    title: "Front",
    description: "Show the complete front display.",
  },
  {
    type: "back",
    title: "Back",
    description: "Show the complete back panel.",
  },
  {
    type: "left",
    title: "Left Side",
    description: "Show the left frame and corners.",
  },
  {
    type: "right",
    title: "Right Side",
    description: "Show the right frame and corners.",
  },
  {
    type: "top",
    title: "Top",
    description: "Show the top edge of the phone.",
  },
  {
    type: "bottom",
    title: "Bottom",
    description: "Show the bottom edge and ports.",
  },
];

type Props = {
  onBack: () => void;
};

function PhotoInspection({ onBack }: Props) {
  const [phase, setPhase] =
    useState<"device" | "photos" | "complete">("device");

  const [brand, setBrand] = useState("");
  const [model, setModel] = useState("");
  const [storage, setStorage] = useState("");

  const [brands, setBrands] = useState<string[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [variants, setVariants] = useState<any[]>([]);

  const [customModel, setCustomModel] = useState("");
  const [customStorage, setCustomStorage] = useState("");

  const [catalogLoading, setCatalogLoading] = useState(false);

  const loadBrands = async () => {
    try {
      const response = await fetch(
        `${API_URL}/api/device-catalog/brands`
      );

      if (!response.ok) {
        throw new Error("Unable to load brands.");
      }

      const data = await response.json();

      setBrands(Array.isArray(data?.items) ? data.items : []);
    } catch (err) {
      console.error("Brand loading error:", err);
      setError("Unable to load device brands.");
    }
  };

  const loadModels = async (selectedBrand: string) => {
    if (!selectedBrand) {
      setModels([]);
      return;
    }

    try {
      setCatalogLoading(true);

      const response = await fetch(
        `${API_URL}/api/device-catalog/brands/${encodeURIComponent(
          selectedBrand
        )}/models`
      );

      if (!response.ok) {
        throw new Error("Unable to load models.");
      }

      const data = await response.json();

      setModels(Array.isArray(data?.items) ? data.items : []);
    } catch (err) {
      console.error("Model loading error:", err);
      setError("Unable to load models.");
    } finally {
      setCatalogLoading(false);
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
      setCatalogLoading(true);

      const response = await fetch(
        `${API_URL}/api/device-catalog/models/` +
          `${encodeURIComponent(selectedBrand)}/` +
          `${encodeURIComponent(selectedModel)}/variants`
      );

      if (!response.ok) {
        throw new Error("Unable to load variants.");
      }

      const data = await response.json();

      setVariants(Array.isArray(data?.items) ? data.items : []);
    } catch (err) {
      console.error("Variant loading error:", err);
      setError("Unable to load storage variants.");
    } finally {
      setCatalogLoading(false);
    }
  };

  const [inspectionCode, setInspectionCode] =
    useState<string | null>(null);

  const [currentIndex, setCurrentIndex] = useState(0);

  const [photos, setPhotos] =
    useState<Record<PhotoType, string>>(
      {} as Record<PhotoType, string>
    );

  const [uploading, setUploading] = useState(false);
  const [creatingInspection, setCreatingInspection] =
    useState(false);

  const [cameraReady, setCameraReady] = useState(false);
  const [error, setError] = useState("");

  const [analysisLoading, setAnalysisLoading] =
    useState(false);

  const [analysisResult, setAnalysisResult] =
    useState<any>(null);

  const [valuationLoading, setValuationLoading] =
    useState(false);

  const [valuationResult, setValuationResult] =
    useState<any>(null);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const currentPhoto = PHOTO_SLOTS[currentIndex];

  const capturedCount = Object.keys(photos).length;

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

    setCameraReady(false);
  };

  const startCamera = async () => {
    setError("");
    setCameraReady(false);

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error(
          "Live camera is not supported by this browser."
        );
      }

      stopCamera();

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      });

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCameraReady(true);
      }
    } catch (err) {
      console.error(err);

      setError(
        "Camera access is required. Please allow camera permission and try again."
      );
    }
  };

  useEffect(() => {
    loadBrands();
  }, []);

  useEffect(() => {
    if (phase === "photos") {
      startCamera();
    } else {
      stopCamera();
    }

    return () => {
      stopCamera();
    };
  }, [phase, currentIndex]);

  const createInspection = async () => {
    setError("");

    const effectiveModel =
      model === CUSTOM ? customModel.trim() : model;
    const effectiveStorage =
      storage === CUSTOM ? customStorage.trim() : storage;

    if (!brand || !effectiveModel || !effectiveStorage) {
      setError("Please complete all device details.");
      return;
    }

    setCreatingInspection(true);

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
            model: effectiveModel,
            storage: effectiveStorage,
            inspection_type: "photo_inspection",
          }),
        }
      );

      if (!response.ok) {
        throw new Error("Unable to create inspection.");
      }

      const data = await response.json();

      setInspectionCode(data.inspection_code);
      setPhase("photos");
    } catch (err) {
      console.error(err);

      setError(
        "Unable to connect to the server. Make sure FastAPI is running."
      );
    } finally {
      setCreatingInspection(false);
    }
  };

  const captureAndUploadPhoto = async () => {
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

    if (
      video.readyState < HTMLMediaElement.HAVE_ENOUGH_DATA ||
      video.videoWidth === 0 ||
      video.videoHeight === 0
    ) {
      setError("Camera is still starting. Please wait a moment.");
      return;
    }

    setUploading(true);
    setError("");

    try {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;

      const context = canvas.getContext("2d");

      if (!context) {
        throw new Error("Unable to capture camera frame.");
      }

      context.drawImage(
        video,
        0,
        0,
        canvas.width,
        canvas.height
      );

      const blob = await new Promise<Blob | null>((resolve) => {
        canvas.toBlob(
          resolve,
          "image/jpeg",
          0.92
        );
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

      const data = await response.json();

      console.log("Camera photo uploaded:", data);

      const previewUrl = URL.createObjectURL(blob);

      setPhotos((previous) => ({
        ...previous,
        [currentPhoto.type]: previewUrl,
      }));

      stopCamera();

      if (currentIndex < PHOTO_SLOTS.length - 1) {
        setCurrentIndex((previous) => previous + 1);
      } else {
        setPhase("complete");
      }
    } catch (err) {
      console.error(err);

      setError(
        err instanceof Error
          ? err.message
          : "Unable to capture photo."
      );
    } finally {
      setUploading(false);
    }
  };

  const retakePhoto = (photoType: PhotoType) => {
    const index = PHOTO_SLOTS.findIndex(
      (item) => item.type === photoType
    );

    if (index !== -1) {
      setCurrentIndex(index);
      setPhase("photos");
    }
  };


  const analyzePhotos = async () => {
    if (!inspectionCode) {
      setError("Inspection code is missing.");
      return;
    }

    setError("");
    setAnalysisLoading(true);

    try {
      const response = await fetch(
        `${API_URL}/api/inspections/${inspectionCode}/analyze`,
        {
          method: "POST",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data?.detail === "string"
            ? data.detail
            : data?.detail?.message ||
              "Photo analysis failed."
        );
      }

      console.log("Photo analysis result:", data);
      setAnalysisResult(data);
    } catch (err) {
      console.error(err);

      setError(
        err instanceof Error
          ? err.message
          : "Unable to analyze photos."
      );
    } finally {
      setAnalysisLoading(false);
    }
  };

  const valuatePhotos = async () => {
    if (!inspectionCode) {
      setError("Inspection code is missing.");
      return;
    }

    setError("");
    setValuationLoading(true);

    try {
      const response = await fetch(
        `${API_URL}/api/inspections/${inspectionCode}/valuate`,
        {
          method: "POST",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data?.detail === "string"
            ? data.detail
            : data?.detail?.message ||
              "Valuation failed."
        );
      }

      setValuationResult(data);
    } catch (err) {
      console.error(err);

      setError(
        err instanceof Error
          ? err.message
          : "Unable to valuate photos."
      );
    } finally {
      setValuationLoading(false);
    }
  };

  /*
   * DEVICE DETAILS
   */
  if (phase === "device") {
    return (
      <div className="photo-app">
        <header className="photo-navbar">
          <button
            className="photo-back"
            onClick={onBack}
          >
            ←
          </button>

          <div className="photo-logo">
            Device<span>Value</span>
          </div>

          <div />
        </header>

        <main className="photo-device-page">
          <div className="photo-intro">
            <div className="camera-icon">📷</div>

            <p className="photo-eyebrow">
              PHOTO VALUATION
            </p>

            <h1>Let's inspect your phone.</h1>

            <p>
              We'll guide you through six live-camera
              captures of your device. Existing photos
              cannot be selected or uploaded.
            </p>
          </div>

          <div className="photo-device-card">
            <h2>Device details</h2>

            <div className="photo-form-group">
              <label>Brand</label>

              <select
                value={brand}
                onChange={(e) => {
                  const selectedBrand = e.target.value;

                  setBrand(selectedBrand);
                  setModel("");
                  setStorage("");
                  setModels([]);
                  setVariants([]);
                  setCustomModel("");
                  setCustomStorage("");

                  if (selectedBrand) {
                    loadModels(selectedBrand);
                  }
                }}
              >
                <option value="">Select brand</option>

                {brands.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </div>

            <div className="photo-form-group">
              <label>Model</label>

              <SelectOrCustom
                value={model}
                disabled={!brand || catalogLoading}
                onValueChange={(value) => {
                  setModel(value);
                  setStorage("");
                  setCustomStorage("");

                  if (value === CUSTOM) {
                    setVariants([]);
                  } else if (brand) {
                    loadVariants(brand, value);
                  }
                }}
                customValue={customModel}
                onCustomChange={(value) =>
                  setCustomModel(value)
                }
                options={models}
                placeholder={
                  !brand
                    ? "Select brand first"
                    : catalogLoading
                    ? "Loading models..."
                    : "Select model"
                }
                customPlaceholder="Type your model, e.g. Y200e 5G"
              />
            </div>

            <div className="photo-form-group">
              <label>RAM + Storage</label>

              <SelectOrCustom
                value={storage}
                disabled={!model || catalogLoading}
                onValueChange={(value) =>
                  setStorage(value)
                }
                customValue={customStorage}
                onCustomChange={(value) =>
                  setCustomStorage(value)
                }
                options={variants.map((v: any) => v.variant_name || v.storage || "")}
                placeholder={
                  !model
                    ? "Select model first"
                    : catalogLoading
                    ? "Loading variants..."
                    : "Select variant"
                }
                customPlaceholder="Type RAM + storage, e.g. 8GB + 128GB"
                optionLabel={(val) => val || "—"}
              />
            </div>

            {error && (
              <div className="photo-error">
                {error}
              </div>
            )}

            <button
              className="photo-primary-btn"
              onClick={createInspection}
              disabled={creatingInspection}
            >
              {creatingInspection
                ? "Starting..."
                : "Start Photo Inspection →"}
            </button>
          </div>
        </main>
      </div>
    );
  }

  /*
   * LIVE CAMERA CAPTURE
   */
  if (phase === "photos") {
    return (
      <div className="photo-app">
        <header className="photo-navbar">
          <button
            className="photo-back"
            onClick={() => {
              stopCamera();
              onBack();
            }}
          >
            ←
          </button>

          <div className="photo-logo">
            Device<span>Value</span>
          </div>

          <div className="photo-counter">
            {currentIndex + 1} / 6
          </div>
        </header>

        <main className="capture-page">
          <div className="capture-progress">
            {PHOTO_SLOTS.map((slot, index) => {
              const completed = photos[slot.type];

              return (
                <div
                  key={slot.type}
                  className={
                    `capture-dot ${
                      completed
                        ? "completed"
                        : index === currentIndex
                        ? "active"
                        : ""
                    }`
                  }
                >
                  {completed ? "✓" : index + 1}
                </div>
              );
            })}
          </div>

          <div className="capture-content">
            <p className="photo-eyebrow">
              PHOTO {currentIndex + 1} OF 6
            </p>

            <h1>
              Take the {currentPhoto.title.toLowerCase()} photo.
            </h1>

            <p className="capture-description">
              {currentPhoto.description}
            </p>

            <div className="camera-frame">
              <video
                ref={videoRef}
                className="camera-video"
                autoPlay
                playsInline
                muted
              />

              <div className="camera-overlay">
                <div className="frame-corner top-left" />
                <div className="frame-corner top-right" />
                <div className="frame-corner bottom-left" />
                <div className="frame-corner bottom-right" />

                <div className="camera-guide">
                  Position your phone inside the frame
                </div>
              </div>

              {!cameraReady && (
                <div className="camera-loading">
                  <div className="camera-loading-icon">
                    📷
                  </div>
                  <span>Starting camera...</span>
                </div>
              )}
            </div>

            <canvas
              ref={canvasRef}
              className="capture-canvas"
            />

            <div className="capture-tips">
              <div>✓ Good lighting</div>
              <div>✓ Entire phone visible</div>
              <div>✓ Keep camera steady</div>
            </div>

            {error && (
              <div className="photo-error">
                {error}
              </div>
            )}

            <button
              className="capture-btn"
              onClick={captureAndUploadPhoto}
              disabled={uploading || !cameraReady}
            >
              <span className="shutter">●</span>

              {uploading
                ? "Uploading..."
                : "Capture Photo"}
            </button>

            <p className="capture-note">
              This inspection uses live camera capture.
              File uploads are disabled.
            </p>
          </div>
        </main>
      </div>
    );
  }

  /*
   * COMPLETE
   */
  return (
    <div className="photo-app">
      <header className="photo-navbar">
        <button
          className="photo-back"
          onClick={onBack}
        >
          ←
        </button>

        <div className="photo-logo">
          Device<span>Value</span>
        </div>
      </header>

      <main className="complete-page">
        <div className="complete-card">
          <div className="complete-icon">✓</div>

          <p className="photo-eyebrow">
            PHOTO INSPECTION READY
          </p>

          <h1>All photos captured.</h1>

          <p>
            We've successfully captured and uploaded
            all six live-camera views of your {model}.
          </p>

          <div className="photo-grid">
            {PHOTO_SLOTS.map((slot) => (
              <div
                className="photo-preview"
                key={slot.type}
              >
                {photos[slot.type] && (
                  <img
                    src={photos[slot.type]}
                    alt={slot.title}
                  />
                )}

                <div className="preview-label">
                  <span>✓</span>
                  {slot.title}
                </div>

                <button
                  onClick={() => retakePhoto(slot.type)}
                >
                  Retake
                </button>
              </div>
            ))}
          </div>

          <div className="inspection-code-box">
            <span>Inspection Code</span>

            <strong>{inspectionCode}</strong>
          </div>

          <button
            className="photo-primary-btn"
            onClick={analyzePhotos}
            disabled={analysisLoading}
          >
            {analysisLoading
              ? "Analyzing Photos..."
              : "Analyze Photos →"}
          </button>

          {error && (
            <div className="photo-error">
              {error}
            </div>
          )}

          {analysisResult && (
            <div
              className="analysis-result-card"
              style={{
                marginTop: "24px",
                padding: "24px",
                borderRadius: "18px",
                background: "#f7faff",
                textAlign: "left",
              }}
            >
              <div
                style={{
                  textAlign: "center",
                  marginBottom: "22px",
                }}
              >
                <div
                  style={{
                    fontSize: "13px",
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    color: "#2563eb",
                    textTransform: "uppercase",
                  }}
                >
                  Photo Inspection Complete
                </div>

                <h3
                  style={{
                    margin: "8px 0 4px",
                    fontSize: "30px",
                  }}
                >
                  {analysisResult.overall_photo_quality ?? 0}/100
                </h3>

                <div
                  style={{
                    fontWeight: 700,
                    color: "#334155",
                  }}
                >
                  {analysisResult.overall_grade ?? "Pending"}
                </div>

                <div
                  style={{
                    marginTop: "6px",
                    color: "#64748b",
                    fontSize: "13px",
                  }}
                >
                  {analysisResult.photos_analyzed ?? 0} of 6 photos analyzed
                </div>
              </div>

              {Array.isArray(analysisResult.photos) && (
                <div>
                  <h4 style={{ marginBottom: "12px" }}>
                    Individual Photo Analysis
                  </h4>

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns:
                        "repeat(auto-fit, minmax(240px, 1fr))",
                      gap: "12px",
                    }}
                  >
                    {analysisResult.photos.map(
                      (photo: any) => {
                        const analysis = photo.analysis || {};
                        const phone =
                          analysis.phone_detection || {};

                        return (
                          <div
                            key={photo.photo_type}
                            style={{
                              background: "#ffffff",
                              border: "1px solid #e2e8f0",
                              borderRadius: "14px",
                              padding: "16px",
                            }}
                          >
                            <div
                              style={{
                                display: "flex",
                                justifyContent:
                                  "space-between",
                                alignItems: "center",
                                marginBottom: "12px",
                              }}
                            >
                              <strong
                                style={{
                                  textTransform:
                                    "capitalize",
                                }}
                              >
                                {photo.photo_type}
                              </strong>

                              <span
                                style={{
                                  fontSize: "13px",
                                  fontWeight: 700,
                                  color:
                                    phone.detected
                                      ? "#16a34a"
                                      : "#dc2626",
                                }}
                              >
                                {phone.detected
                                  ? "✓ Detected"
                                  : "✕ Not detected"}
                              </span>
                            </div>

                            <div
                              style={{
                                display: "grid",
                                gap: "7px",
                                fontSize: "14px",
                                color: "#475569",
                              }}
                            >
                              <div>
                                Photo quality:{" "}
                                <strong>
                                  {analysis.quality_score ??
                                    0}
                                  /100
                                </strong>
                              </div>

                              <div>
                                Detection confidence:{" "}
                                <strong>
                                  {phone.confidence !==
                                  undefined
                                    ? `${(
                                        phone.confidence *
                                        100
                                      ).toFixed(1)}%`
                                    : "—"}
                                </strong>
                              </div>

                              <div>
                                Position:{" "}
                                <strong>
                                  {phone.position ?? "—"}
                                </strong>
                              </div>

                              <div>
                                Capture integrity:{" "}
                                <strong>
                                  {phone.integrity_score ??
                                    0}
                                  /100
                                </strong>
                              </div>

                              <div>
                                Grade:{" "}
                                <strong>
                                  {analysis.quality_grade ??
                                    "—"}
                                </strong>
                              </div>
                            </div>
                          </div>
                        );
                      }
                    )}
                  </div>
                </div>
              )}

              <div
                style={{
                  marginTop: "18px",
                  padding: "16px",
                  borderRadius: "12px",
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                }}
              >
                <strong>Physical Condition AI</strong>

                <div
                  style={{
                    marginTop: "6px",
                    display: "grid",
                    gap: "5px",
                    color: "#475569",
                    fontSize: "14px",
                  }}
                >
                  {analysisResult.physical_condition_ai
                    ?.status === "unavailable" && (
                    <div>
                      Condition analysis is currently
                      unavailable. Please try again later
                      or retake the photos.
                    </div>
                  )}

                  {analysisResult.physical_condition_ai
                    ?.status === "partial" && (
                    <div>
                      Some photos could not be fully
                      analyzed, so the estimate was adjusted
                      down.
                    </div>
                  )}

                  {analysisResult.physical_condition_ai
                    ?.detected_views !== undefined && (
                    <div>
                      Phone detected in{" "}
                      <strong>
                        {
                          analysisResult
                            .physical_condition_ai
                            .detected_views
                        }
                        /{
                          analysisResult
                            .physical_condition_ai
                            .total_views
                        }
                      </strong>{" "}
                      views
                    </div>
                  )}

                  {analysisResult.physical_condition_ai
                    ?.average_confidence !== undefined &&
                    analysisResult.physical_condition_ai
                      .average_confidence !== null && (
                      <div>
                        AI confidence:{" "}
                        <strong>
                          {(
                            analysisResult
                              .physical_condition_ai
                              .average_confidence * 100
                          ).toFixed(0)}
                          %
                        </strong>
                      </div>
                    )}

                  {analysisResult.overall_photo_quality <
                    60 && (
                    <div>
                      Photo quality is low, which reduces the
                      condition score. Retake photos in good
                      light for a better estimate.
                    </div>
                  )}
                </div>
              </div>

              <div
                style={{
                  marginTop: "18px",
                  textAlign: "center",
                  color: "#64748b",
                  fontSize: "13px",
                }}
              >
                Inspection: {analysisResult.inspection_code}
              </div>
            </div>
          )}

          <p className="analysis-note">
            {analysisResult
              ? "AI photo analysis completed."
              : "AI photo analysis will run after you click Analyze Photos."}
          </p>

          {analysisResult && !valuationResult && (
            <button
              className="photo-primary-btn valuation-btn"
              onClick={valuatePhotos}
              disabled={valuationLoading}
            >
              {valuationLoading
                ? "Calculating Value..."
                : "Get Device Value →"}
            </button>
          )}

          {valuationResult && (
            <div
              className="valuation-result-card"
              style={{
                marginTop: "24px",
                padding: "24px",
                borderRadius: "18px",
                background:
                  "linear-gradient(135deg, #0f172a, #1e3a8a)",
                color: "#ffffff",
                textAlign: "left",
              }}
            >
              <div
                style={{
                  textAlign: "center",
                  marginBottom: "22px",
                }}
              >
                <div
                  style={{
                    fontSize: "13px",
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    color: "#93c5fd",
                    textTransform: "uppercase",
                  }}
                >
                  Estimated Resale Value
                </div>

                <h3
                  style={{
                    margin: "10px 0 4px",
                    fontSize: "44px",
                    fontWeight: 800,
                  }}
                >
                  ₹{valuationResult.resale_price?.toLocaleString("en-IN") ?? 0}
                </h3>

                <div
                  style={{
                    color: "#cbd5e1",
                    fontSize: "14px",
                  }}
                >
                  Exchange value:{" "}
                  <strong style={{ color: "#ffffff" }}>
                    ₹{valuationResult.exchange_price?.toLocaleString("en-IN") ?? 0}
                  </strong>
                </div>
              </div>

              <div
                style={{
                  display: "grid",
                  gap: "10px",
                  fontSize: "14px",
                  color: "#e2e8f0",
                }}
              >
                <div>
                  Market price:{" "}
                  <strong>₹{valuationResult.market_price?.toLocaleString("en-IN")}</strong>
                </div>

                <div>
                  Condition score:{" "}
                  <strong>{valuationResult.condition_score}/100</strong>
                </div>

                <div>
                  Condition grade:{" "}
                  <strong>{valuationResult.condition_grade}</strong>
                </div>

                <div>
                  Condition multiplier:{" "}
                  <strong>{valuationResult.condition_multiplier}</strong>
                </div>

                <div>
                  Photo quality:{" "}
                  <strong>{valuationResult.overall_photo_quality}/100</strong>
                </div>

                <div>
                  Method:{" "}
                  <strong>{valuationResult.valuation_type}</strong>
                </div>
              </div>
            </div>
          )}

          <p className="analysis-note">
            {capturedCount} / 6 photos captured
          </p>
        </div>
      </main>
    </div>
  );
}

export default PhotoInspection;
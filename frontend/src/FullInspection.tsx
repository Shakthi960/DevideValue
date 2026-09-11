import { useEffect, useRef, useState } from "react";
import "./ExchangeInspection.css";
import "./PhotoInspection.css";
import "./Diagnostics.css";
import SelectOrCustom, { CUSTOM } from "./components/SelectOrCustom";
import LoadingSpinner from "./components/LoadingSpinner";
import logo from "./logo.png";
import {
  formatINR,
  getApiUrl,
  isEstimatedPriceSource,
} from "./config";

type Phase =
  | "device"
  | "questions"
  | "role"
  | "code"
  | "photos"
  | "diagnostics"
  | "result";

type DiagPhase = "gate" | "sensors" | "report" | "saving";

type PhotoType =
  | "front" | "back" | "left" | "right" | "top" | "bottom";

type PhotoSlot = { type: PhotoType; title: string; description: string };

const PHOTO_SLOTS: PhotoSlot[] = [
  { type: "front",   title: "Front",       description: "Show the complete front display." },
  { type: "back",    title: "Back",        description: "Show the complete back panel." },
  { type: "left",    title: "Left Side",   description: "Show the left frame and corners." },
  { type: "right",   title: "Right Side",  description: "Show the right frame and corners." },
  { type: "top",     title: "Top",         description: "Show the top edge of the phone." },
  { type: "bottom",  title: "Bottom",      description: "Show the bottom edge and ports." },
];

type QuestionKey =
  | "device_age" | "screen_condition" | "body_condition" | "battery_condition"
  | "functionality" | "original_charger" | "original_box" | "repair_history";

const QUESTIONS: { key: QuestionKey; title: string; step: string; options: [string, string][] }[] = [
  { key: "device_age",        title: "How old is your phone?",       step: "STEP 1 OF 8", options: [["less_than_6_months","Less than 6 months"],["6_to_12_months","6–12 months"],["1_to_2_years","1–2 years"],["2_to_3_years","2–3 years"],["more_than_3_years","More than 3 years"]] },
  { key: "screen_condition",  title: "How is the screen?",           step: "STEP 2 OF 8", options: [["excellent","Excellent — no visible damage"],["minor_scratches","Minor scratches"],["scratched","Noticeably scratched"],["cracked","Cracked"],["display_problem","Display problem"]] },
  { key: "body_condition",    title: "How is the body?",             step: "STEP 3 OF 8", options: [["excellent","Excellent — almost no marks"],["minor_scratches","Minor scratches"],["multiple_scratches","Multiple scratches"],["minor_dents","Minor dents"],["major_damage","Major dents or damage"]] },
  { key: "battery_condition", title: "How is the battery?",          step: "STEP 4 OF 8", options: [["excellent","Excellent"],["good","Good"],["below_80","Below 80%"],["replaced","Battery has been replaced"],["unknown","I don't know"]] },
  { key: "functionality",     title: "Does everything work?",        step: "STEP 5 OF 8", options: [["yes","Yes, everything works"],["no","No, something doesn't work"],["not_sure","I'm not sure"]] },
  { key: "original_charger",  title: "Original charger available?",  step: "STEP 6 OF 8", options: [["yes","Yes"],["no","No"]] },
  { key: "original_box",      title: "Original box available?",      step: "STEP 7 OF 8", options: [["yes","Yes"],["no","No"]] },
  { key: "repair_history",    title: "Has the phone been repaired?", step: "STEP 8 OF 8", options: [["no","No repairs"],["authorized","Yes — authorized service"],["third_party","Yes — third-party service"],["unknown","I don't know"]] },
];

type TestStatus = "pending" | "running" | "passed" | "failed" | "unsupported";

const SENSOR_TESTS: { id: string; name: string; description: string }[] = [
  { id: "camera",     name: "Camera",      description: "Check the rear camera responds." },
  { id: "microphone", name: "Microphone",  description: "Check the microphone captures audio." },
  { id: "motion",     name: "Motion sensor", description: "Check the accelerometer / gyroscope." },
  { id: "location",   name: "GPS / Location", description: "Check location services are available." },
  { id: "touch",      name: "Touchscreen", description: "Tap the tile three times to test it." },
];

const SELF_REPORT: { key: string; title: string; options: [string, string][] }[] = [
  { key: "battery",       title: "How is the battery life?",           options: [["excellent","Excellent — lasts all day"],["good","Good — but drains a bit"],["average","Average — needs frequent charging"],["poor","Poor — drains very fast"]] },
  { key: "charging",      title: "Does the phone charge properly?",    options: [["yes","Yes, charges normally"],["slow","Charges but slowly"],["no","No, doesn't charge"]] },
  { key: "speaker",       title: "How is the speaker/mic quality?",    options: [["excellent","Crystal clear"],["good","Good — slight distortion"],["poor","Poor — muffled or crackling"],["not_working","Not working"]] },
  { key: "buttons",       title: "Are the hardware buttons working?",  options: [["yes","All buttons work"],["partial","Some buttons sticky/broken"],["no","None work"]] },
  { key: "connectivity",  title: "Does Wi-Fi / Bluetooth work?",       options: [["yes","Yes, all works"],["wifi_only","Wi-Fi works, Bluetooth doesn't"],["nothing","Neither works"],["frequent","Frequent disconnections"]] },
  { key: "screen_touch",  title: "Is the touchscreen fully responsive?", options: [["yes","Yes, fully responsive"],["dead_zones","Some dead zones"],["no","No, unresponsive"]] },
];

const SENSOR_LABEL: Record<TestStatus, string> = {
  pending: "Pending", running: "Testing…", passed: "✓ Passed", failed: "✕ Failed", unsupported: "Not supported",
};

type Props = { onBack: () => void };

export default function FullInspection({ onBack }: Props) {
  const [phase, setPhase] = useState<Phase>("device");

  // --- Device ---
  const [brand, setBrand] = useState("");  const [model, setModel] = useState("");  const [storage, setStorage] = useState("");
  const [brands, setBrands] = useState<string[]>([]);  const [models, setModels] = useState<string[]>([]);  const [variants, setVariants] = useState<any[]>([]);
  const [customBrand, setCustomBrand] = useState("");  const [customModel, setCustomModel] = useState("");  const [customStorage, setCustomStorage] = useState("");
  const [catalogBusy, setCatalogBusy] = useState(false);  const [catalogNote, setCatalogNote] = useState("");  const [priceInput, setPriceInput] = useState("");
  const [deviceChecking, setDeviceChecking] = useState(false);

  // --- Questionnaire ---
  const [qIndex, setQIndex] = useState(0);  const [answers, setAnswers] = useState<Record<string, string>>({});

  // --- Inspection ---
  const [inspectionCode, setInspectionCode] = useState<string | null>(null);
  const [linkCode, setLinkCode] = useState<string | null>(null);
  const [role, setRole] = useState<"this_phone" | "other_phone" | null>(null);

  // --- Camera ---
  const videoRef  = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [cameraReady, setCameraReady] = useState(false);
  const [photoIndex, setPhotoIndex] = useState(0);
  const [photos, setPhotos] = useState<Record<PhotoType, string>>({} as Record<PhotoType, string>);
  const [uploading, setUploading] = useState(false);
  const [photoPhase, setPhotoPhase] = useState<"capture" | "complete">("capture");

  // --- Diagnostics ---
  const [diagPhase, setDiagPhase] = useState<DiagPhase>("gate");
  const [phoneWorking, setPhoneWorking] = useState<string | null>(null);
  const [sensorTests, setSensorTests] = useState<SensorTest[]>(SENSOR_TESTS.map((t) => ({ ...t, status: "pending" as TestStatus })));
  const [selfReport, setSelfReport] = useState<Record<string, string>>({});
  const [reportIndex, setReportIndex] = useState(0);
  const [diagSaving, setDiagSaving] = useState(false);
  const touchCount = useRef(0);

  // --- Result ---
  const [result, setResult] = useState<any>(null);
  const [resultLoading, setResultLoading] = useState(false);

  // --- Polling ---
  const [pollData, setPollData] = useState<any>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // --- UI ---
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [warning, setWarning] = useState("");

  const currentQ     = QUESTIONS[qIndex];
  const currentPhoto = PHOTO_SLOTS[photoIndex];
  const currentReport = SELF_REPORT[reportIndex];

  const getEffectiveDevice = () => ({
    brand:   brand === CUSTOM ? customBrand.trim() : brand,
    model:   model === CUSTOM ? customModel.trim() : model,
    storage: storage === CUSTOM ? customStorage.trim() : storage,
  });

  // ================================================================
  // CATALOG
  // ================================================================

  const fetchBrands = async (): Promise<string[]> => {
    const r = await fetch(getApiUrl("/api/device-catalog/brands"));
    const d = await r.json(); return Array.isArray(d?.items) ? d.items : [];
  };
  useEffect(() => { fetchBrands().then(setBrands).catch(() => setError("Unable to load device catalog.")); }, []);

  const loadModels = async (b: string) => {
    setModel(""); setStorage(""); setModels([]); setVariants([]); setCustomModel(""); setCustomStorage("");
    if (!b || b === CUSTOM) return;
    try { const r = await fetch(getApiUrl(`/api/device-catalog/brands/${encodeURIComponent(b)}/models`)); const d = await r.json(); setModels(Array.isArray(d?.items) ? d.items : []); }
    catch { setError("Unable to load models."); }
  };

  const loadVariants = async (m: string) => {
    if (!brand || !m || brand === CUSTOM || m === CUSTOM) { setVariants([]); return; }
    setStorage(""); setVariants([]);
    try { const r = await fetch(getApiUrl(`/api/device-catalog/models/${encodeURIComponent(brand)}/${encodeURIComponent(m)}/variants`)); const d = await r.json(); setVariants(Array.isArray(d?.items) ? d.items : []); }
    catch { setError("Unable to load variants."); }
  };

  const handleAddToCatalog = async () => {
    const { brand: eb, model: em, storage: es } = getEffectiveDevice();
    if (!eb || !em || !es) return;
    setCatalogBusy(true); setCatalogNote("");
    try {
      const r = await fetch(getApiUrl("/api/device-catalog/devices"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ brand: eb, model: em, storage: es, new_price_inr: priceInput ? parseInt(priceInput, 10) : null }) });
      const d = await r.json(); if (!r.ok) { setCatalogNote(d?.detail || "Unable to add the device."); return; }
      setCatalogNote(`Added ${d.brand} ${d.model} (${d.storage}) to the catalog.`); setWarning(""); setPriceInput(""); loadModels(eb); fetchBrands().then(setBrands).catch(() => {});
    } catch { setCatalogNote("Unable to reach the server to add this device."); }
    finally { setCatalogBusy(false); }
  };

  // ================================================================
  // QUESTIONNAIRE
  // ================================================================

  const answerCurrent = (value: string) => {
    setAnswers((p) => ({ ...p, [currentQ.key]: value }));
    if (qIndex < QUESTIONS.length - 1) setQIndex(qIndex + 1);
  };

  // ================================================================
  // CREATE INSPECTION
  // ================================================================

  const createInspection = async () => {
    setLoading(true); setError("");
    const { brand: eb, model: em, storage: es } = getEffectiveDevice();
    try {
      const r = await fetch(getApiUrl("/api/inspections"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ brand: eb, model: em, storage: es, inspection_type: "full_inspection" }) });
      if (!r.ok) throw new Error("Unable to create inspection.");
      const d = await r.json(); setInspectionCode(d.inspection_code); setLinkCode(d.link_code); setPhase("role");
    } catch { setError("Unable to connect to the server. Make sure FastAPI is running."); }
    finally { setLoading(false); }
  };

  // ================================================================
  // ROLE
  // ================================================================

  const proceedAfterRole = (chosen: "this_phone" | "other_phone") => {
    setRole(chosen);
    if (chosen === "this_phone") setPhase("code");
    else { setPhase("photos"); setPhotoPhase("capture"); setPhotoIndex(0); setPhotos({} as Record<PhotoType, string>); }
  };

  // ================================================================
  // CAMERA
  // ================================================================

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraReady(false);
  };

  const startCamera = async () => {
    setError(""); setCameraReady(false);
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Live camera is not supported by this browser.");
      stopCamera();
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false });
      streamRef.current = stream;
      if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play(); setCameraReady(true); }
    } catch { setError("Camera access is required. Please allow camera permission and try again."); }
  };

  useEffect(() => {
    if (phase === "photos" && photoPhase === "capture") { startCamera(); } else { stopCamera(); }
    return () => { stopCamera(); };
  }, [phase, photoPhase, photoIndex]);

  const captureAndUploadPhoto = async () => {
    if (!inspectionCode) { setError("Inspection has not been created."); return; }
    const video = videoRef.current, canvas = canvasRef.current;
    if (!video || !canvas) { setError("Camera is not ready."); return; }
    if (video.readyState < HTMLMediaElement.HAVE_ENOUGH_DATA || video.videoWidth === 0) { setError("Camera is still starting. Please wait a moment."); return; }
    setUploading(true); setError("");
    try {
      canvas.width = video.videoWidth; canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d"); if (!ctx) throw new Error("Unable to capture camera frame.");
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
      if (!blob) throw new Error("Unable to create image.");
      const fd = new FormData(); fd.append("file", blob, `${currentPhoto.type}.jpg`);
      const r = await fetch(getApiUrl(`/api/inspections/${inspectionCode}/photos?photo_type=${currentPhoto.type}`), { method: "POST", body: fd });
      if (!r.ok) { const e = await r.json().catch(() => null); throw new Error(e?.detail || "Photo upload failed."); }
      setPhotos((p) => ({ ...p, [currentPhoto.type]: URL.createObjectURL(blob) }));
      stopCamera();
      if (photoIndex < PHOTO_SLOTS.length - 1) setPhotoIndex((p) => p + 1);
      else setPhotoPhase("complete");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to capture photo."); }
    finally { setUploading(false); }
  };

  // ================================================================
  // DIAGNOSTICS — sensor tests
  // ================================================================

  const setStatus = (id: string, status: TestStatus) => setSensorTests((p) => p.map((t) => t.id === id ? { ...t, status } : t));

  const checkCamera = async (): Promise<TestStatus> => {
    try {
      if (!navigator.mediaDevices?.getUserMedia) return "unsupported";
      const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } } });
      const ok = s.getVideoTracks().length > 0; s.getTracks().forEach((t) => t.stop()); return ok ? "passed" : "failed";
    } catch { return "failed"; }
  };

  const checkMicrophone = async (): Promise<TestStatus> => {
    try {
      if (!navigator.mediaDevices?.getUserMedia) return "unsupported";
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      const ok = s.getAudioTracks().length > 0; s.getTracks().forEach((t) => t.stop()); return ok ? "passed" : "failed";
    } catch { return "failed"; }
  };

  const runSensorTests = async () => {
    setStatus("camera", "running"); setStatus("microphone", "running");
    const cam = await checkCamera(); setStatus("camera", cam);
    const mic = await checkMicrophone(); setStatus("microphone", mic);
    setStatus("motion", window.DeviceOrientationEvent !== undefined || window.DeviceMotionEvent !== undefined ? "passed" : "unsupported");
    setStatus("location", "geolocation" in navigator ? "passed" : "unsupported");
  };

  const handleTouch = (e: React.PointerEvent) => {
    if (e.pointerType === "touch" || e.pointerType === "pen") {
      touchCount.current += 1;
      if (touchCount.current >= 3) setStatus("touch", "passed");
      else setStatus("touch", "running");
    }
  };

  // ================================================================
  // DIAGNOSTICS — gate → sensors → report → save → complete-valuate → result
  // ================================================================

  const finishReport = async () => {
    const passed = sensorTests.filter((t) => t.status === "passed").length;
    const sensorScore = (passed / sensorTests.length) * 70;
    const reportScore = Object.values(selfReport).reduce((s, v) => {
      if (["excellent", "yes", "good"].includes(v)) return s + 6;
      if (["average", "slow", "partial", "wifi_only"].includes(v)) return s + 3;
      return s + 1;
    }, 0);
    const reportMax = SELF_REPORT.length * 6;
    const reportRatio = reportMax > 0 ? reportScore / reportMax : 0;
    const finalScore = Math.round(Math.min(100, sensorScore + reportRatio * 30));

    setDiagPhase("saving");
    setError("");

    try {
      // 1) Save diagnostics
      const dr = await fetch(getApiUrl(`/api/inspections/${inspectionCode}/diagnostics`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ working: "yes", diagnostics_score: finalScore, diagnostics_report: { sensorResults: Object.fromEntries(sensorTests.map((t) => [t.id, t.status])), selfReport, finalScore } }),
      });
      if (!dr.ok) { const e = await dr.json().catch(() => null); throw new Error(e?.detail || "Unable to save diagnostics."); }

      // 2) Complete + valuate
      const answerList = Object.entries(answers).map(([question_key, answer_value]) => ({ question_key, answer_value }));
      const vr = await fetch(getApiUrl(`/api/inspections/${inspectionCode}/complete-valuate`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers: answerList }),
      });
      if (!vr.ok) { const e = await vr.json().catch(() => null); throw new Error(e?.detail || "Valuation failed."); }

      setResult(await vr.json());
      setPhase("result");
    } catch (err) { setError(err instanceof Error ? err.message : "Something went wrong."); setDiagPhase("report"); }
    finally { setDiagSaving(false); }
  };

  const skipDiagnostics = async () => {
    setDiagPhase("saving"); setError("");
    try {
      const dr = await fetch(getApiUrl(`/api/inspections/${inspectionCode}/diagnostics`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ working: "no", diagnostics_score: 0, diagnostics_report: { working: "no", sensorResults: {} } }),
      });
      if (!dr.ok) { const e = await dr.json().catch(() => null); throw new Error(e?.detail || "Unable to save diagnostics."); }

      const answerList = Object.entries(answers).map(([question_key, answer_value]) => ({ question_key, answer_value }));
      const vr = await fetch(getApiUrl(`/api/inspections/${inspectionCode}/complete-valuate`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers: answerList }),
      });
      if (!vr.ok) { const e = await vr.json().catch(() => null); throw new Error(e?.detail || "Valuation failed."); }
      setResult(await vr.json()); setPhase("result");
    } catch (err) { setError(err instanceof Error ? err.message : "Something went wrong."); setDiagPhase("gate"); }
    finally { setDiagSaving(false); }
  };

  // ================================================================
  // POLLING
  // ================================================================

  const finalizingRef = useRef(false);

  const finalizeValuation = async () => {
    if (finalizingRef.current) return;
    finalizingRef.current = true;
    setResultLoading(true); setError("");
    try {
      const vr = await fetch(getApiUrl(`/api/inspections/${inspectionCode}/complete-valuate`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers: Object.entries(answers).map(([question_key, answer_value]) => ({ question_key, answer_value })) }),
      });
      if (!vr.ok) { const e = await vr.json().catch(() => null); throw new Error(e?.detail || "Valuation failed."); }
      setResult(await vr.json());
      setPhase("result");
    } catch (err) { setError(err instanceof Error ? err.message : "Something went wrong."); }
    finally { setResultLoading(false); finalizingRef.current = false; }
  };

  useEffect(() => {
    if (phase !== "code" || !inspectionCode) return;
    const poll = async () => { try { const r = await fetch(getApiUrl(`/api/inspections/${inspectionCode}`)); if (r.ok) setPollData(await r.json()); } catch {} };
    poll(); pollRef.current = setInterval(poll, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [phase, inspectionCode]);

  // Diagnostics complete: "other_phone" scenario — the primary is the helper,
  // so it must submit the answers + run the final valuation itself.
  useEffect(() => {
    if (phase === "code" && role === "other_phone" && pollData?.diagnostics_complete) {
      if (pollRef.current) clearInterval(pollRef.current);
      finalizeValuation();
    }
  }, [phase, role, pollData]);

  // This phone + photos complete → run diagnostics locally on this phone.
  useEffect(() => {
    if (phase === "code" && role === "this_phone" && pollData?.photos_complete && !pollData?.diagnostics_complete) { if (pollRef.current) clearInterval(pollRef.current); setPhase("diagnostics"); }
  }, [phase, role, pollData]);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  // ================================================================
  // DEVICE SELECTION
  // ================================================================

  if (phase === "device") {
    return (
      <div className="xi-app">
        <header className="xi-navbar">
          <button className="xi-back" onClick={onBack}>←</button>
          <div className="xi-logo"><img src={logo} alt="DeviceValue" className="brand-logo" />Device<span>Value</span></div>
          <div />
        </header>
        <main className="xi-page">
          {loading && <LoadingSpinner overlay label="Processing..." />}
          <div className="xi-card">
            <p className="xi-eyebrow">PHONE RESALE VALUE</p>
            <h1>Which phone do you want to value?</h1>
            <p className="xi-sub">Start here on the phone where you want the result to appear. You'll need a second phone to take photos.</p>
            <label className="xi-label">Brand</label>
            <SelectOrCustom className="xi-select" value={brand} onValueChange={(v) => { setBrand(v); setModel(""); setStorage(""); setWarning(""); setCatalogNote(""); if (v && v !== CUSTOM) loadModels(v); else { setModels([]); setVariants([]); } }} customValue={customBrand} onCustomChange={(v) => { setCustomBrand(v); setWarning(""); setCatalogNote(""); }} options={brands} placeholder="Select brand" customPlaceholder="Type your brand, e.g. Nothing" />
            <label className="xi-label">Model</label>
            <SelectOrCustom className="xi-select" value={model} onValueChange={(v) => { setModel(v); setStorage(""); setCustomStorage(""); setWarning(""); setCatalogNote(""); if (v === CUSTOM) setVariants([]); else loadVariants(v); }} customValue={customModel} onCustomChange={(v) => { setCustomModel(v); setWarning(""); setCatalogNote(""); }} options={models} disabled={!models.length && brand !== CUSTOM} placeholder="Select model" customPlaceholder="Type your model, e.g. Y200e 5G" />
            <label className="xi-label">Variant (RAM + Storage)</label>
            <SelectOrCustom className="xi-select" value={storage} onValueChange={(v) => { setStorage(v); setWarning(""); setCatalogNote(""); }} customValue={customStorage} onCustomChange={(v) => { setCustomStorage(v); setWarning(""); setCatalogNote(""); }} options={variants.map((v: any) => v.variant_name || v.storage || "")} disabled={!model || (model !== CUSTOM && !variants.length)} placeholder={model === CUSTOM ? "Select variant (or Others)" : "Select variant"} customPlaceholder="Type RAM + storage, e.g. 8GB + 128GB" optionLabel={(val) => val || "—"} />
            {error && <div className="xi-error">{error}</div>}
            {warning && (<div className="xi-warning"><p>{warning}</p><div className="catalog-form"><input type="number" min="0" placeholder="Estimated price in ₹ (optional)" value={priceInput} onChange={(e) => setPriceInput(e.target.value)} disabled={catalogBusy} /><button className="catalog-btn" onClick={handleAddToCatalog} disabled={catalogBusy}>{catalogBusy ? "Adding..." : "Add to catalog"}</button></div></div>)}
            {catalogNote && <div className="catalog-note">{catalogNote}</div>}
            <button className="xi-primary-btn" onClick={() => setPhase("questions")} disabled={deviceChecking || loading || !brand || !model || !storage}>Start Questionnaire →</button>
          </div>
        </main>
      </div>
    );
  }

  // ================================================================
  // QUESTIONNAIRE
  // ================================================================

  if (phase === "questions") {
    return (
      <div className="xi-app">
        <header className="xi-navbar">
          <button className="xi-back" onClick={() => { if (qIndex > 0) setQIndex(qIndex - 1); else setPhase("device"); }}>←</button>
          <div className="xi-logo"><img src={logo} alt="DeviceValue" className="brand-logo" />Device<span>Value</span></div>
          <div className="xi-progress">{qIndex + 1}/{QUESTIONS.length}</div>
        </header>
        <main className="xi-question-page">
          {loading && <LoadingSpinner overlay label="Processing..." />}
          <div className="xi-progress-bar"><div className="xi-progress-fill" style={{ width: `${((qIndex + 1) / QUESTIONS.length) * 100}%` }} /></div>
          <div className="xi-question-card">
            <p className="xi-eyebrow">{currentQ.step}</p>
            <h1>{currentQ.title}</h1>
            <div className="xi-options">
              {currentQ.options.map(([value, label]) => (<button key={value} className={`xi-option ${answers[currentQ.key] === value ? "selected" : ""}`} onClick={() => answerCurrent(value)}>{label}</button>))}
            </div>
            {qIndex >= QUESTIONS.length - 1 && (<button className="xi-primary-btn" onClick={createInspection} disabled={loading}>{loading ? "Creating inspection…" : "Continue →"}</button>)}
          </div>
        </main>
      </div>
    );
  }

  // ================================================================
  // ROLE CHOICE
  // ================================================================

  if (phase === "role") {
    return (
      <div className="xi-app">
        <header className="xi-navbar">
          <button className="xi-back" onClick={() => setPhase("questions")}>←</button>
          <div className="xi-logo"><img src={logo} alt="DeviceValue" className="brand-logo" />Device<span>Value</span></div>
          <div />
        </header>
        <main className="xi-page">
          <div className="xi-card">
            <p className="xi-eyebrow">PHOTO INSPECTION</p>
            <h1>Which phone are you valuing?</h1>
            <p className="xi-sub">A phone can't photograph itself, so we need a second device for the photos. The result will always appear on the phone you're using right now.</p>
            <div className="xi-options">
              <button className="xi-option" onClick={() => proceedAfterRole("this_phone")}><strong>This phone</strong><br /><span style={{ fontSize: "13px", color: "#64748b" }}>I want the value of the phone I'm holding. I'll get a code to enter on the second phone for photos.</span></button>
              <button className="xi-option" onClick={() => proceedAfterRole("other_phone")}><strong>Another phone</strong><br /><span style={{ fontSize: "13px", color: "#64748b" }}>The phone I want to value is with me — I'll take photos of it right here with this device, then get a code for the other phone's diagnostics.</span></button>
            </div>
            {error && <div className="xi-error">{error}</div>}
          </div>
        </main>
      </div>
    );
  }

  // ================================================================
  // PHOTO CAPTURE
  // ================================================================

  if (phase === "photos" && photoPhase === "capture") {
    return (
      <div className="photo-app">
        <header className="photo-navbar">
          <button className="photo-back" onClick={() => { stopCamera(); setPhase("role"); }}>←</button>
          <div className="photo-logo"><img src={logo} alt="DeviceValue" className="brand-logo" />Device<span>Value</span></div>
          <div className="photo-counter">{photoIndex + 1} / 6</div>
        </header>
        <main className="capture-page">
          <div className="capture-progress">
            {PHOTO_SLOTS.map((slot, i) => (<div key={slot.type} className={`capture-dot ${photos[slot.type] ? "completed" : i === photoIndex ? "active" : ""}`}>{photos[slot.type] ? "✓" : i + 1}</div>))}
          </div>
          <div className="capture-content">
            <p className="photo-eyebrow">PHOTO {photoIndex + 1} OF 6</p>
            <h1>Take the {currentPhoto.title.toLowerCase()} photo.</h1>
            <p className="capture-description">{currentPhoto.description}</p>
            <div className="camera-frame">
              <video ref={videoRef} className="camera-video" autoPlay playsInline muted />
              <div className="camera-overlay"><div className="frame-corner top-left" /><div className="frame-corner top-right" /><div className="frame-corner bottom-left" /><div className="frame-corner bottom-right" /><div className="camera-guide">Position the phone inside the frame</div></div>
              {!cameraReady && <div className="camera-loading"><LoadingSpinner size="md" label="Starting camera..." /></div>}
            </div>
            <canvas ref={canvasRef} className="capture-canvas" />
            <div className="capture-tips"><div>✓ Good lighting</div><div>✓ Entire phone visible</div><div>✓ Keep camera steady</div></div>
            {error && <div className="photo-error">{error}</div>}
            <button className="capture-btn" onClick={captureAndUploadPhoto} disabled={uploading || !cameraReady}><span className="shutter">●</span>{uploading ? "Uploading..." : "Capture Photo"}</button>
            <p className="capture-note">This inspection uses live camera capture. File uploads are disabled.</p>
          </div>
        </main>
      </div>
    );
  }

  // ================================================================
  // PHOTO COMPLETE → show code for diagnostics
  // ================================================================

  if (phase === "photos" && photoPhase === "complete") {
    return (
      <div className="photo-app">
        <header className="photo-navbar">
          <button className="photo-back" onClick={() => { setPhotoPhase("capture"); setPhotoIndex(0); }}>←</button>
          <div className="photo-logo"><img src={logo} alt="DeviceValue" className="brand-logo" />Device<span>Value</span></div>
          <div />
        </header>
        <main className="complete-page">
          <div className="complete-card">
            <div className="complete-icon">✓</div>
            <p className="photo-eyebrow">PHOTOS CAPTURED</p>
            <h1>All 6 photos taken.</h1>
            <p>Now open the app on the phone being valued and choose <strong>"Continue with a Code"</strong> to run diagnostics.</p>
            <div className="photo-grid">
              {PHOTO_SLOTS.map((slot) => (<div className="photo-preview" key={slot.type}>{photos[slot.type] && <img src={photos[slot.type]} alt={slot.title} />}<div className="preview-label"><span>✓</span>{slot.title}</div></div>))}
            </div>
            <div style={{ margin: "24px 0", padding: "16px", background: "#eff6ff", borderRadius: "12px", textAlign: "center" }}>
              <div style={{ fontSize: "12px", color: "#64748b", marginBottom: "6px" }}>ENTER THIS CODE ON THE OTHER PHONE</div>
              <div style={{ fontSize: "48px", fontWeight: 800, color: "#2563eb", letterSpacing: "6px", userSelect: "all" }}>{linkCode}</div>
            </div>
            <p style={{ color: "#64748b", fontSize: "14px", marginBottom: "20px" }}>Keep this phone open. Once diagnostics are completed on the other phone, your valuation result will appear here automatically.</p>
            <button className="xi-primary-btn" onClick={() => setPhase("code")}>I've given the code — wait for diagnostics →</button>
          </div>
        </main>
      </div>
    );
  }

  // ================================================================
  // CODE / WAITING
  // ================================================================

  if (phase === "code") {
    const photosComplete = pollData?.photos_complete ?? false;
    const diagnosticsComplete = pollData?.diagnostics_complete ?? false;
    const photosCaptured = pollData?.photos_captured ?? 0;
    return (
      <div className="xi-app">
        <header className="xi-navbar">
          <button className="xi-back" onClick={() => { if (pollRef.current) clearInterval(pollRef.current); setPhase(role === "this_phone" ? "role" : "photos"); }}>←</button>
          <div className="xi-logo"><img src={logo} alt="DeviceValue" className="brand-logo" />Device<span>Value</span></div>
          <div />
        </header>
        <main className="xi-page">
          <div className="xi-card" style={{ textAlign: "center" }}>
            <p className="xi-eyebrow">{role === "this_phone" && !photosComplete ? "WAITING FOR PHOTOS" : "WAITING FOR DIAGNOSTICS"}</p>
            <h1>{role === "this_phone" && !photosComplete ? "Open the app on the other phone" : diagnosticsComplete ? "Almost done" : "Waiting for diagnostics"}</h1>
            <p className="xi-sub">{role === "this_phone" && !photosComplete ? "On the second phone, choose 'Continue with a Code', enter the code below, and take 6 photos of this phone." : diagnosticsComplete ? "Finalizing your valuation…" : "The other phone is now running device diagnostics. Keep this phone open."}</p>
            <div style={{ fontSize: "48px", fontWeight: 800, color: "#2563eb", letterSpacing: "6px", padding: "24px", background: "#eff6ff", borderRadius: "14px", marginBottom: "24px", userSelect: "all" }}>{linkCode}</div>
            <p style={{ fontSize: "13px", color: "#64748b", marginBottom: "18px" }}>{role === "this_phone" ? `Photos captured: ${photosCaptured} / 6` : `Diagnostics: ${diagnosticsComplete ? "Complete" : "In progress…"}`}</p>
            <div style={{ padding: "14px 18px", background: "#fffbeb", border: "1px solid #fde68a", borderRadius: "10px", color: "#92400e", fontSize: "14px", lineHeight: "1.5", textAlign: "left", marginTop: "16px" }}><strong>Keep this phone open and unlocked.</strong> You don't need to do anything — the next step will start automatically.</div>
            {error && <div className="xi-error" style={{ marginTop: "16px" }}>{error}</div>}
          </div>
        </main>
      </div>
    );
  }

  // ================================================================
  // DIAGNOSTICS
  // ================================================================

  if (phase === "diagnostics") {
    // --- Gate ---
    if (diagPhase === "gate") {
      return (
        <div className="xi-app">
          <header className="xi-navbar">
            <button className="xi-back" onClick={() => setPhase("code")}>←</button>
            <div className="xi-logo"><img src={logo} alt="DeviceValue" className="brand-logo" />Device<span>Value</span></div>
            <div />
          </header>
          <main className="xi-page">
            <div className="xi-card">
              <p className="xi-eyebrow">DEVICE DIAGNOSTICS</p>
              <h1>Is this phone working properly?</h1>
              <p className="xi-sub">If the phone can't run a web browser or the screen doesn't work, we'll skip the sensor tests and give it a zero diagnostics score. This only affects the diagnostic assessment — your photo and questionnaire data are still used.</p>
              <div className="xi-options">
                <button className="xi-option" onClick={() => { setPhoneWorking("yes"); setDiagPhase("sensors"); runSensorTests(); }}>Yes, the phone is working and I can use it</button>
                <button className="xi-option" onClick={() => { setPhoneWorking("no"); skipDiagnostics(); }}>No, the phone is not working / display is broken</button>
              </div>
              {error && <div className="xi-error">{error}</div>}
            </div>
          </main>
        </div>
      );
    }

    // --- Saving ---
    if (diagPhase === "saving") {
      return (
        <div className="xi-app">
          <header className="xi-navbar">
            <div className="xi-logo"><img src={logo} alt="DeviceValue" className="brand-logo" />Device<span>Value</span></div>
            <div />
            <div />
          </header>
          <main className="xi-page">
            <LoadingSpinner overlay label={phoneWorking === "no" ? "Skipping diagnostics — saving result…" : "Saving diagnostics and calculating valuation…"} />
          </main>
        </div>
      );
    }

    // --- Sensor tests ---
    if (diagPhase === "sensors") {
      return (
        <div className="diag-app">
          <header className="diag-navbar">
            <button className="diag-back" onClick={() => setDiagPhase("gate")}>←</button>
            <div className="diag-logo"><img src={logo} alt="DeviceValue" className="brand-logo" />Device<span>Value</span></div>
            <div />
          </header>
          <main className="diag-page">
            <div className="diag-card">
              <p className="diag-eyebrow">STEP 1 OF 2 — SENSOR TESTS</p>
              <h1>Check your device's hardware.</h1>
              <p className="diag-sub">Run the browser-based sensor tests below, then continue to the self-report questions.</p>
              <div className="diag-tests">
                {sensorTests.map((test) => (
                  <div key={test.id} className={`diag-test ${test.status}`} onPointerDown={test.id === "touch" ? handleTouch : undefined}>
                    <div className="diag-test-info"><strong>{test.name}</strong><span>{test.description}</span></div>
                    <div className="diag-test-status">{SENSOR_LABEL[test.status]}</div>
                  </div>
                ))}
              </div>
              {error && <div className="xi-error">{error}</div>}
              <button className="diag-primary-btn" onClick={() => setDiagPhase("report")} style={{ marginTop: "18px" }}>Continue to Self-Report →</button>
            </div>
          </main>
        </div>
      );
    }

    // --- Self-report questions ---
    return (
      <div className="diag-app">
        <header className="diag-navbar">
          <button className="diag-back" onClick={() => { if (reportIndex > 0) setReportIndex(reportIndex - 1); else setDiagPhase("sensors"); }}>←</button>
          <div className="diag-logo"><img src={logo} alt="DeviceValue" className="brand-logo" />Device<span>Value</span></div>
          <div className="diag-progress">{reportIndex + 1}/{SELF_REPORT.length}</div>
        </header>
        <main className="diag-report-page">
          <div className="diag-progress-track"><div className="diag-progress-fill" style={{ width: `${((reportIndex + 1) / SELF_REPORT.length) * 100}%` }} /></div>
          <div className="diag-question-card">
            <p className="diag-eyebrow">STEP 2 OF 2 — SELF-REPORT QUESTION {reportIndex + 1}</p>
            <h1>{currentReport.title}</h1>
            <div className="diag-options">
              {currentReport.options.map(([value, label]) => (<button key={value} className={`diag-option ${selfReport[currentReport.key] === value ? "selected" : ""}`} onClick={() => { setSelfReport((p) => ({ ...p, [currentReport.key]: value })); if (reportIndex < SELF_REPORT.length - 1) setReportIndex(reportIndex + 1); else finishReport(); }}>{label}</button>))}
            </div>
          </div>
        </main>
      </div>
    );
  }

  // ================================================================
  // RESULT
  // ================================================================

  return (
    <div className="xi-app">
      <header className="xi-navbar">
        <button className="xi-back" onClick={onBack}>←</button>
        <div className="xi-logo"><img src={logo} alt="DeviceValue" className="brand-logo" />Device<span>Value</span></div>
        <div />
      </header>
      <main className="xi-page">
        {resultLoading && <LoadingSpinner overlay label="Loading valuation…" />}
        <div className="xi-result" style={{ maxWidth: 640, margin: "0 auto" }}>
          <p className="xi-eyebrow" style={{ textAlign: "center" }}>VALUATION RESULT</p>
          <h1 style={{ textAlign: "center", fontSize: 32, marginBottom: 24 }}>Your device's estimated value</h1>

          <div className="xi-result-card">
            <div className="xi-result-main">
              <div className="xi-result-label">ESTIMATED RESALE VALUE</div>
              <div className="xi-result-price">{formatINR(result?.resale_price ?? 0)}</div>
              <div style={{ color: "#93c5fd", fontSize: 14, marginTop: 6 }}>Exchange value: <strong style={{ color: "#fff" }}>{formatINR(result?.exchange_price ?? 0)}</strong></div>
            </div>
            <div className="xi-result-details">
              <div>Market price: <strong>{formatINR(result?.market_price ?? 0)}</strong></div>
              {result?.new_price_inr && <div>New price today: <strong>{formatINR(result.new_price_inr)}</strong></div>}
              {result?.price_source && <div style={{ fontSize: 12, color: "#94a3b8" }}>{result.price_source}</div>}
              {isEstimatedPriceSource(result?.price_source) && (<div className="xi-warning" style={{ marginTop: 8 }}><strong>New device — approximate price.</strong><br />This looks like a recently launched device, so we couldn't find its exact market price. The value above is an estimate based on the closest known model.</div>)}
              <div>Condition score: <strong>{result?.condition_score}/100</strong></div>
              <div>Condition grade: <strong>{result?.condition_grade}</strong></div>
              <div>Condition multiplier: <strong>{result?.condition_multiplier}×</strong></div>
              <div>Photo quality: <strong>{result?.overall_photo_quality}/100</strong></div>
              <div>Questionnaire score: <strong>{result?.questionnaire_score}/100</strong></div>
              <div>AI photo score: <strong>{result?.ai_condition_score}/100</strong></div>
              {result?.diagnostics && (<div>Diagnostics score: <strong>{result.diagnostics.diagnostics_score ?? 0}/100</strong></div>)}
              <div style={{ marginTop: 8, fontSize: 12, color: "#94a3b8" }}>Method: {result?.valuation_type}</div>
            </div>
          </div>

          <div className="xi-inspection-code" style={{ textAlign: "center", marginTop: 18 }}>Inspection: {result?.inspection_code}</div>

          <button className="xi-primary-btn" style={{ marginTop: 24 }} onClick={onBack}>Done</button>
        </div>
      </main>
    </div>
  );
}

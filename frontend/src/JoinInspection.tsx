import { useEffect, useRef, useState } from "react";
import "./ExchangeInspection.css";
import "./PhotoInspection.css";
import "./Diagnostics.css";
import LoadingSpinner from "./components/LoadingSpinner";
import logo from "./logo.png";
import { getApiUrl } from "./config";

type PhotoType = "front" | "back" | "left" | "right" | "top" | "bottom";
type PhotoSlot = { type: PhotoType; title: string; description: string };

const PHOTO_SLOTS: PhotoSlot[] = [
  { type: "front",   title: "Front",       description: "Show the complete front display." },
  { type: "back",    title: "Back",        description: "Show the complete back panel." },
  { type: "left",    title: "Left Side",   description: "Show the left frame and corners." },
  { type: "right",   title: "Right Side",  description: "Show the right frame and corners." },
  { type: "top",     title: "Top",         description: "Show the top edge of the phone." },
  { type: "bottom",  title: "Bottom",      description: "Show the bottom edge and ports." },
];

type TestStatus = "pending" | "running" | "passed" | "failed" | "unsupported";
type SensorTest = { id: string; name: string; description: string; status: TestStatus };

const SENSOR_TESTS: { id: string; name: string; description: string }[] = [
  { id: "camera",     name: "Camera",       description: "Check the rear camera responds." },
  { id: "microphone", name: "Microphone",   description: "Check the microphone captures audio." },
  { id: "motion",     name: "Motion sensor", description: "Check the accelerometer / gyroscope." },
  { id: "location",   name: "GPS / Location", description: "Check location services are available." },
  { id: "touch",      name: "Touchscreen",  description: "Tap the tile three times to test it." },
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

type Phase = "code" | "photos" | "photos_done" | "diag_gate" | "diag_sensors" | "diag_report" | "diag_saving" | "done";

type Props = { onBack: () => void };

export default function JoinInspection({ onBack }: Props) {
  const [phase, setPhase] = useState<Phase>("code");

  // --- Code entry ---
  const [linkCode, setLinkCode] = useState("");
  const [joining, setJoining] = useState(false);
  const [joinInfo, setJoinInfo] = useState<any>(null);
  const [joinError, setJoinError] = useState("");

  // --- Photos ---
  const videoRef  = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [cameraReady, setCameraReady] = useState(false);
  const [photoIndex, setPhotoIndex] = useState(0);
  const [photos, setPhotos] = useState<Record<PhotoType, string>>({} as Record<PhotoType, string>);
  const [uploading, setUploading] = useState(false);

  // --- Diagnostics ---
  const [phoneWorking, setPhoneWorking] = useState<string | null>(null);
  const [sensorTests, setSensorTests] = useState<SensorTest[]>(SENSOR_TESTS.map((t) => ({ ...t, status: "pending" as TestStatus })));
  const [selfReport, setSelfReport] = useState<Record<string, string>>({});
  const [reportIndex, setReportIndex] = useState(0);
  const [diagSaving, setDiagSaving] = useState(false);
  const touchCount = useRef(0);

  // --- UI ---
  const [error, setError] = useState("");

  const currentPhoto  = PHOTO_SLOTS[photoIndex];
  const currentReport = SELF_REPORT[reportIndex];
  const inspectionCode = joinInfo?.inspection_code ?? null;
  const deviceModel    = joinInfo?.model ?? "";

  const setStatus = (id: string, status: TestStatus) => setSensorTests((p) => p.map((t) => t.id === id ? { ...t, status } : t));

  // ================================================================
  // JOIN VIA CODE
  // ================================================================

  const joinInspection = async () => {
    const trimmed = linkCode.trim();
    if (!trimmed) { setJoinError("Please enter the 6-digit code."); return; }
    setJoining(true); setJoinError(""); setError("");
    try {
      const r = await fetch(getApiUrl("/api/inspections/link"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ link_code: trimmed }),
      });
      const d = await r.json();
      if (!r.ok) { setJoinError(typeof d?.detail === "string" ? d.detail : "Unable to join that inspection."); return; }
      setJoinInfo(d);
      if (d.need === "photos") { setPhase("photos"); setPhotoIndex(0); setPhotos({} as Record<PhotoType, string>); }
      else if (d.need === "diagnostics") { setPhase("diag_gate"); }
      else { setPhase("done"); }
    } catch { setJoinError("Unable to reach the server. Make sure FastAPI is running."); }
    finally { setJoining(false); }
  };

  // ================================================================
  // PHOTOS
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
      const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false });
      streamRef.current = s;
      if (videoRef.current) { videoRef.current.srcObject = s; await videoRef.current.play(); setCameraReady(true); }
    } catch { setError("Camera access is required. Please allow camera permission and try again."); }
  };

  useEffect(() => {
    if (phase === "photos") startCamera(); else stopCamera();
    return () => { stopCamera(); };
  }, [phase, photoIndex]);

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
      else setPhase("photos_done");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to capture photo."); }
    finally { setUploading(false); }
  };

  // ================================================================
  // DIAGNOSTICS
  // ================================================================

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

  const saveDiagnostics = async (working: string, score: number, report: any) => {
    setDiagSaving(true); setError("");
    try {
      const r = await fetch(getApiUrl(`/api/inspections/${inspectionCode}/diagnostics`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ working, diagnostics_score: score, diagnostics_report: report }),
      });
      if (!r.ok) { const e = await r.json().catch(() => null); throw new Error(e?.detail || "Unable to save diagnostics."); }
      setPhase("done");
    } catch (err) { setError(err instanceof Error ? err.message : "Something went wrong."); setDiagSaving(false); }
  };

  const finishReport = async () => {
    const passed = sensorTests.filter((t) => t.status === "passed").length;
    const sensorScore = (passed / sensorTests.length) * 70;
    const reportScore = Object.values(selfReport).reduce((s, v) => {
      if (["excellent", "yes", "good"].includes(v)) return s + 6;
      if (["average", "slow", "partial", "wifi_only"].includes(v)) return s + 3;
      return s + 1;
    }, 0);
    const reportMax = SELF_REPORT.length * 6;
    const finalScore = Math.round(Math.min(100, sensorScore + (reportMax > 0 ? (reportScore / reportMax) * 30 : 0)));
    await saveDiagnostics("yes", finalScore, { sensorResults: Object.fromEntries(sensorTests.map((t) => [t.id, t.status])), selfReport, finalScore });
  };

  const skipDiagnostics = async () => {
    await saveDiagnostics("no", 0, { working: "no", sensorResults: {} });
  };

  // ================================================================
  // RENDER — ENTER CODE
  // ================================================================

  if (phase === "code") {
    return (
      <div className="xi-app">
        <header className="xi-navbar">
          <button className="xi-back" onClick={onBack}>←</button>
          <div className="xi-logo"><img src={logo} alt="DeviceValue" className="brand-logo" />Device<span>Value</span></div>
          <div />
        </header>
        <main className="xi-page">
          <div className="xi-card">
            <p className="xi-eyebrow">CONTINUE WITH A CODE</p>
            <h1>Enter the 6-digit code.</h1>
            <p className="xi-sub">Your partner started an inspection on another phone and should be showing you a 6-digit code. Enter it here to take photos or run diagnostics.</p>
            <input
              className="xi-select"
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={linkCode}
              placeholder="e.g. 482109"
              onChange={(e) => { setLinkCode(e.target.value.replace(/\D/g, "")); setJoinError(""); }}
              style={{ fontSize: "28px", fontWeight: 800, textAlign: "center", letterSpacing: "8px", padding: "18px 16px", textTransform: undefined }}
            />
            {joinError && <div className="xi-error">{joinError}</div>}
            {error && <div className="xi-error">{error}</div>}
            <button className="xi-primary-btn" onClick={joinInspection} disabled={joining || linkCode.length !== 6}>
              {joining ? "Joining…" : "Join Inspection →"}
            </button>
          </div>
        </main>
      </div>
    );
  }

  // ================================================================
  // RENDER — PHOTOS
  // ================================================================

  if (phase === "photos") {
    return (
      <div className="photo-app">
        <header className="photo-navbar">
          <button className="photo-back" onClick={() => { stopCamera(); setPhase("code"); }}>←</button>
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
  // RENDER — PHOTOS DONE
  // ================================================================

  if (phase === "photos_done") {
    return (
      <div className="photo-app">
        <header className="photo-navbar">
          <button className="photo-back" onClick={() => setPhase("photos")}>←</button>
          <div className="photo-logo"><img src={logo} alt="DeviceValue" className="brand-logo" />Device<span>Value</span></div>
          <div />
        </header>
        <main className="complete-page">
          <div className="complete-card">
            <div className="complete-icon">✓</div>
            <p className="photo-eyebrow">THANK YOU</p>
            <h1>All 6 photos taken!</h1>
            <p>The photos of your <strong>{deviceModel}</strong> have been sent to the phone that started the inspection. Go back to that phone to continue.</p>
            <div className="photo-grid">
              {PHOTO_SLOTS.map((slot) => (<div className="photo-preview" key={slot.type}>{photos[slot.type] && <img src={photos[slot.type]} alt={slot.title} />}<div className="preview-label"><span>✓</span>{slot.title}</div></div>))}
            </div>
            <button className="xi-primary-btn" onClick={onBack}>Done</button>
          </div>
        </main>
      </div>
    );
  }

  // ================================================================
  // RENDER — DIAGNOSTICS GATE
  // ================================================================

  if (phase === "diag_gate") {
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
            <p className="xi-sub">We'll run sensor tests on <strong>{deviceModel}</strong>. If the phone can't run a browser or the screen is broken, choose "No" and we'll skip the tests.</p>
            {diagSaving && <LoadingSpinner overlay label="Saving diagnostics…" />}
            <div className="xi-options">
              <button className="xi-option" onClick={() => { setPhoneWorking("yes"); setPhase("diag_sensors"); runSensorTests(); }}>Yes, the phone is working and I can use it</button>
              <button className="xi-option" onClick={() => { setPhoneWorking("no"); skipDiagnostics(); }}>No, the phone is not working / display is broken</button>
            </div>
            {error && <div className="xi-error">{error}</div>}
          </div>
        </main>
      </div>
    );
  }

  // ================================================================
  // RENDER — SENSOR TESTS
  // ================================================================

  if (phase === "diag_sensors") {
    return (
      <div className="diag-app">
        <header className="diag-navbar">
          <button className="diag-back" onClick={() => setPhase("diag_gate")}>←</button>
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
            <button className="diag-primary-btn" onClick={() => setPhase("diag_report")} style={{ marginTop: "18px" }}>Continue to Self-Report →</button>
          </div>
        </main>
      </div>
    );
  }

  // ================================================================
  // RENDER — SELF-REPORT
  // ================================================================

  if (phase === "diag_report") {
    return (
      <div className="diag-app">
        <header className="diag-navbar">
          <button className="diag-back" onClick={() => { if (reportIndex > 0) setReportIndex(reportIndex - 1); else setPhase("diag_sensors"); }}>←</button>
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
  // RENDER — DONE (photos or diagnostics completed)
  // ================================================================

  return (
    <div className="xi-app">
      <header className="xi-navbar">
        <button className="xi-back" onClick={onBack}>←</button>
        <div className="xi-logo"><img src={logo} alt="DeviceValue" className="brand-logo" />Device<span>Value</span></div>
        <div />
      </header>
      <main className="xi-page">
        <div className="xi-card" style={{ textAlign: "center" }}>
          <div style={{ width: 65, height: 65, margin: "0 auto 20px", display: "flex", alignItems: "center", justifyContent: "center", borderRadius: "50%", background: "#dcfce7", color: "#16a34a", fontSize: 30, fontWeight: 800 }}>✓</div>
          <p className="xi-eyebrow">{joinInfo?.need === "complete" ? "INSPECTION COMPLETE" : "ALL DONE"}</p>
          <h1>{joinInfo?.need === "complete" ? "This inspection is already complete." : "Your part is done!"}</h1>
          <p className="xi-sub">
            {joinInfo?.need === "complete"
              ? "Both photos and diagnostics have already been submitted for this inspection."
              : "Your results have been sent back to the phone that started the inspection. That phone will now show the final valuation automatically."}
          </p>
          {error && <div className="xi-error">{error}</div>}
          <button className="xi-primary-btn" onClick={onBack}>Done</button>
        </div>
      </main>
    </div>
  );
}
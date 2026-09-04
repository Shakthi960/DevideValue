import { useRef, useState } from "react";
import "./Diagnostics.css";

type TestStatus =
  | "pending"
  | "running"
  | "passed"
  | "failed"
  | "unsupported";

type SensorTest = {
  id: string;
  name: string;
  description: string;
  status: TestStatus;
};

type Phase = "main" | "report" | "result";

type Props = {
  onBack: () => void;
};

const SELF_REPORT: {
  key: string;
  title: string;
  options: [string, string][];
}[] = [
  {
    key: "battery",
    title: "How is the battery life?",
    options: [
      ["excellent", "Excellent — lasts all day"],
      ["good", "Good — but drains a bit"],
      ["average", "Average — needs frequent charging"],
      ["poor", "Poor — drains very fast"],
    ],
  },
  {
    key: "charging",
    title: "Does the phone charge properly?",
    options: [
      ["yes", "Yes, charges normally"],
      ["slow", "Charges but slowly"],
      ["no", "No, doesn't charge"],
    ],
  },
  {
    key: "speaker",
    title: "How is the speaker/mic quality?",
    options: [
      ["excellent", "Crystal clear"],
      ["good", "Good — slight distortion"],
      ["poor", "Poor — muffled or crackling"],
      ["not_working", "Not working"],
    ],
  },
  {
    key: "buttons",
    title: "Are the hardware buttons working?",
    options: [
      ["yes", "All buttons work"],
      ["partial", "Some buttons sticky/broken"],
      ["no", "None work"],
    ],
  },
  {
    key: "connectivity",
    title: "Does Wi-Fi / Bluetooth work?",
    options: [
      ["yes", "Yes, all works"],
      ["wifi_only", "Wi-Fi works, Bluetooth doesn't"],
      ["nothing", "Neither works"],
      ["frequent", "Frequent disconnections"],
    ],
  },
  {
    key: "screen_touch",
    title: "Is the touchscreen fully responsive?",
    options: [
      ["yes", "Yes, fully responsive"],
      ["dead_zones", "Some dead zones"],
      ["no", "No, unresponsive"],
    ],
  },
];

const STATUS_LABEL: Record<TestStatus, string> = {
  pending: "Pending",
  running: "Testing…",
  passed: "✓ Passed",
  failed: "✕ Failed",
  unsupported: "Not supported",
};

function Diagnostics({ onBack }: Props) {
  const [phase, setPhase] = useState<Phase>("main");

  const [tests, setTests] = useState<SensorTest[]>([
    {
      id: "camera",
      name: "Camera",
      description: "Check the rear camera responds.",
      status: "pending",
    },
    {
      id: "microphone",
      name: "Microphone",
      description: "Check the microphone captures audio.",
      status: "pending",
    },
    {
      id: "motion",
      name: "Motion sensor",
      description: "Check the accelerometer / gyroscope.",
      status: "pending",
    },
    {
      id: "location",
      name: "GPS / Location",
      description: "Check location services are available.",
      status: "pending",
    },
    {
      id: "touch",
      name: "Touchscreen",
      description: "Tap the tile three times to test it.",
      status: "pending",
    },
  ]);

  const [running, setRunning] = useState(false);
  const [touchNotes, setTouchNotes] = useState("");

  const [selfReport, setSelfReport] = useState<
    Record<string, string>
  >({});
  const [reportIndex, setReportIndex] = useState(0);

  const [result, setResult] = useState<any>(null);

  const touchCount = useRef(0);

  const setStatus = (id: string, status: TestStatus) => {
    setTests((prev) =>
      prev.map((t) => (t.id === id ? { ...t, status } : t))
    );
  };

  const setResultStatus = (
    id: string,
    status: TestStatus
  ) => {
    setStatus(id, status);
    setResult((prev: any) => {
      const sensorResults = {
        ...(prev?.sensorResults || {}),
        [id]: status,
      };
      const passed = Object.values(sensorResults).filter(
        (s) => s === "passed"
      ).length;
      const healthScore = Math.min(
        100,
        60 + passed * 6
      );
      return {
        ...(prev || {}),
        sensorResults,
        passedCount: passed,
        healthScore,
        overallGrade:
          healthScore >= 85
            ? "Excellent"
            : healthScore >= 70
            ? "Good"
            : healthScore >= 50
            ? "Fair"
            : "Poor",
      };
    });
  };

  const checkCamera = async (): Promise<TestStatus> => {
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        return "unsupported";
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
      });
      const ok = stream.getVideoTracks().length > 0;
      stream.getTracks().forEach((t) => t.stop());
      return ok ? "passed" : "failed";
    } catch {
      return "failed";
    }
  };

  const checkMicrophone = async (): Promise<TestStatus> => {
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        return "unsupported";
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      const ok = stream.getAudioTracks().length > 0;
      stream.getTracks().forEach((t) => t.stop());
      return ok ? "passed" : "failed";
    } catch {
      return "failed";
    }
  };

  const checkMotion = (): TestStatus => {
    const supported =
      window.DeviceOrientationEvent !== undefined ||
      window.DeviceMotionEvent !== undefined;
    return supported ? "passed" : "unsupported";
  };

  const checkLocation = (): TestStatus => {
    return "geolocation" in navigator ? "passed" : "unsupported";
  };

  const runDiagnostics = async () => {
    setRunning(true);
    setResultStatus("camera", "running");
    setResultStatus("microphone", "running");

    const camera = await checkCamera();
    setResultStatus("camera", camera);

    const mic = await checkMicrophone();
    setResultStatus("microphone", mic);

    setResultStatus("motion", checkMotion());
    setResultStatus("location", checkLocation());

    setRunning(false);
  };

  const handleTouch = (e: React.PointerEvent) => {
    if (e.pointerType === "touch" || e.pointerType === "pen") {
      touchCount.current += 1;

      if (touchCount.current >= 3) {
        setResultStatus("touch", "passed");
        setTouchNotes(
          `Touchscreen registered ${touchCount.current} taps.`
        );
      } else {
        setResultStatus("touch", "running");
      }
    }
  };

  const currentReport = SELF_REPORT[reportIndex];

  const answerReport = (value: string) => {
    setSelfReport((prev) => ({
      ...prev,
      [currentReport.key]: value,
    }));

    if (reportIndex < SELF_REPORT.length - 1) {
      setReportIndex(reportIndex + 1);
    } else {
      finishReport();
    }
  };

  const finishReport = () => {
    const passed = Object.values(result.sensorResults || {}).filter(
      (s) => s === "passed"
    ).length;

    const sensorScore = (passed / tests.length) * 70;

    const reportScore = Object.values(selfReport).reduce(
      (sum, value) => {
        if (["excellent", "yes", "good"].includes(value)) {
          return sum + 6;
        }
        if (
          ["average", "slow", "partial", "wifi_only"].includes(
            value
          )
        ) {
          return sum + 3;
        }
        return sum + 1;
      },
      0
    );

    const reportMax = SELF_REPORT.length * 6;

    const reportRatio = reportMax > 0 ? reportScore / reportMax : 0;

    const finalScore = Math.round(
      Math.min(
        100,
        sensorScore + reportRatio * 30
      )
    );

    setResult((prev: any) => ({
      ...prev,
      selfReport,
      reportComplete: true,
      finalScore,
      finalGrade:
        finalScore >= 85
          ? "Healthy"
          : finalScore >= 70
          ? "Good"
          : finalScore >= 50
          ? "Fair"
          : "Needs attention",
    }));

    setPhase("result");
  };

  // ============================================================
  // MAIN SCREEN
  // ============================================================

  if (phase === "main") {
    return (
      <div className="diag-app">
        <header className="diag-navbar">
          <button className="diag-back" onClick={onBack}>
            ←
          </button>
          <div className="diag-logo">
            Device<span>Value</span>
          </div>
          <div />
        </header>

        <main className="diag-page">
          <div className="diag-card">
            <p className="diag-eyebrow">DEVICE DIAGNOSTICS</p>
            <h1>Check your device's hardware.</h1>
            <p className="diag-sub">
              Run the browser-based sensor tests, then answer a
              few questions about your phone.
            </p>

            <div className="diag-tests">
              {tests.map((test) => (
                <div
                  key={test.id}
                  className={`diag-test ${test.status}`}
                  onPointerDown={
                    test.id === "touch"
                      ? handleTouch
                      : undefined
                  }
                >
                  <div className="diag-test-info">
                    <strong>{test.name}</strong>
                    <span>{test.description}</span>
                  </div>
                  <div className="diag-test-status">
                    {STATUS_LABEL[test.status]}
                  </div>
                </div>
              ))}
            </div>

            {touchNotes && (
              <div className="diag-note">{touchNotes}</div>
            )}

            <button
              className="diag-primary-btn"
              onClick={runDiagnostics}
              disabled={running}
            >
              {running
                ? "Running Sensor Tests..."
                : "Run Sensor Tests →"}
            </button>

            <button
              className="diag-secondary-btn"
              onClick={() => {
                setReportIndex(0);
                setPhase("report");
              }}
            >
              Continue to Self-Report →
            </button>
          </div>
        </main>
      </div>
    );
  }

  // ============================================================
  // SELF-REPORT SCREEN
  // ============================================================

  if (phase === "report") {
    return (
      <div className="diag-app">
        <header className="diag-navbar">
          <button
            className="diag-back"
            onClick={() => {
              if (reportIndex > 0) {
                setReportIndex(reportIndex - 1);
              } else {
                setPhase("main");
              }
            }}
          >
            ←
          </button>
          <div className="diag-logo">
            Device<span>Value</span>
          </div>
          <div className="diag-progress">
            {reportIndex + 1}/{SELF_REPORT.length}
          </div>
        </header>

        <main className="diag-report-page">
          <div className="diag-progress-track">
            <div
              className="diag-progress-fill"
              style={{
                width: `${
                  ((reportIndex + 1) / SELF_REPORT.length) * 100
                }%`,
              }}
            />
          </div>

          <div className="diag-question-card">
            <p className="diag-eyebrow">
              SELF-REPORT QUESTION {reportIndex + 1}
            </p>
            <h1>{currentReport.title}</h1>

            <div className="diag-options">
              {currentReport.options.map(([value, label]) => (
                <button
                  key={value}
                  className={`diag-option ${
                    selfReport[currentReport.key] === value
                      ? "selected"
                      : ""
                  }`}
                  onClick={() => answerReport(value)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </main>
      </div>
    );
  }

  // ============================================================
  // RESULT SCREEN
  // ============================================================

  return (
    <div className="diag-app">
      <header className="diag-navbar">
        <button className="diag-back" onClick={onBack}>
          ←
        </button>
        <div className="diag-logo">
          Device<span>Value</span>
        </div>
        <div />
      </header>

      <main className="diag-page">
        <div className="diag-card diag-result-card">
          <p className="diag-eyebrow">DIAGNOSTICS COMPLETE</p>
          <h1>Device health report.</h1>

          <div className="diag-score-ring">
            <div className="diag-score-value">
              {result?.finalScore ?? result?.healthScore ?? 0}
            </div>
            <div className="diag-score-label">Health Score</div>
          </div>

          <div className="diag-grade">{result?.finalGrade}</div>

          <div className="diag-results-list">
            <h3>Sensor Tests</h3>
            {Object.entries(result?.sensorResults || {}).map(
              ([key, value]) => (
                <div key={key} className="diag-result-row">
                  <span style={{ textTransform: "capitalize" }}>
                    {key}
                  </span>
                  <strong className={`diag-row-${value}`}>
                    {STATUS_LABEL[value as TestStatus]}
                  </strong>
                </div>
              )
            )}
          </div>

          <button className="diag-primary-btn" onClick={onBack}>
            Done
          </button>
        </div>
      </main>
    </div>
  );
}

export default Diagnostics;

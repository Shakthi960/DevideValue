import "./LoadingSpinner.css";
import logo from "../logo.png";

type LoadingSpinnerProps = {
  label?: string;
  overlay?: boolean;
  size?: "md" | "lg";
};

export default function LoadingSpinner({
  label,
  overlay = false,
  size = "lg",
}: LoadingSpinnerProps) {
  const spinner = (
    <div
      className={`loading-spinner ${
        size === "md" ? "loading-spinner--md" : ""
      }`}
      role="status"
      aria-live="polite"
    >
      <div className="loading-spinner__wheel">
        <div className="spinner-ring" />
        <div className="spinner-logo">
          <img src={logo} alt="DeviceValue" />
        </div>
      </div>

      {label && <p className="spinner-label">{label}</p>}
    </div>
  );

  if (overlay) {
    return <div className="loading-overlay">{spinner}</div>;
  }

  return spinner;
}
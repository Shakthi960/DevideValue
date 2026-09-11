import { useEffect, useState } from "react";
import "./AddedDevices.css";
import LoadingSpinner from "./components/LoadingSpinner";
import { formatINR, getApiUrl } from "./config";
import logo from "./logo.png";

type AddedDevice = {
  id: number;
  brand: string;
  model: string;
  storage: string;
  price_inr: number | null;
  price_source: string;
  notes: string | null;
  added_at: string | null;
};

type Props = {
  onBack: () => void;
};

function formatWhen(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function AddedDevices({ onBack }: Props) {
  const [devices, setDevices] = useState<AddedDevice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let stale = false;

    const load = async () => {
      try {
        const response = await fetch(
          getApiUrl("/api/device-catalog/devices/recent")
        );

        if (!response.ok) {
          throw new Error(
            `Server returned ${response.status}`
          );
        }

        const data = await response.json();

        if (!stale) {
          setDevices(data.items ?? []);
        }
      } catch {
        if (!stale) {
          setError(
            "Unable to load recently added devices. Make sure FastAPI is running."
          );
        }
      } finally {
        if (!stale) {
          setLoading(false);
        }
      }
    };

    load();

    return () => {
      stale = true;
    };
  }, []);

  return (
    <div className="added-app">
      <header className="added-navbar">
        <button className="added-back" onClick={onBack}>
          ←
        </button>
        <div className="added-logo">
          <img src={logo} alt="DeviceValue" className="brand-logo" />
          Device<span>Value</span>
        </div>
        <div />
      </header>

      <main className="added-page">
        <div className="added-card">
          <p className="added-eyebrow">
            ADMIN · CATALOG
          </p>

          <h1>Recently added devices.</h1>

          <p className="added-subtitle">
            Devices registered through the "Add to catalog"
            flow across the valuation screens.
          </p>

          {error && (
            <div className="added-error">{error}</div>
          )}

          {loading ? (
            <LoadingSpinner label="Loading added devices…" />
          ) : devices.length === 0 ? (
            <p className="added-empty">
              No custom devices added yet. Register a new
              device from any valuation flow and it will
              appear here.
            </p>
          ) : (
            <div className="added-list">
              <table className="added-table">
                <thead>
                  <tr>
                    <th>Device</th>
                    <th>Variant</th>
                    <th>Price</th>
                    <th>Added at</th>
                  </tr>
                </thead>
                <tbody>
                  {devices.map((device) => (
                    <tr key={device.id}>
                      <td>
                        <strong>
                          {device.brand} {device.model}
                        </strong>
                        <div className="added-note">
                          {device.notes}
                        </div>
                      </td>
                      <td>{device.storage}</td>
                      <td>
                        {device.price_inr != null
                          ? formatINR(device.price_inr)
                          : "—"}
                      </td>
                      <td>{formatWhen(device.added_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <button
            className="added-primary-btn"
            onClick={onBack}
          >
            Done
          </button>
        </div>
      </main>
    </div>
  );
}

export default AddedDevices;
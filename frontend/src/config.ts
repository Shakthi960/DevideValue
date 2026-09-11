// When VITE_API_URL is empty or unset the app is deployed on
// Vercel (or similar) where the frontend and backend share
// the same origin — use the path as-is (same-origin relative).
const VITE_API_URL =
  (import.meta.env?.VITE_API_URL as string | undefined) ?? "";

export const API_URL = VITE_API_URL;

export function getApiUrl(path: string): string {
  if (API_URL) {
    return `${API_URL}${path}`;
  }

  return path;
}

export function formatINR(value: number): string {
  return `₹${value.toLocaleString("en-IN")}`;
}

export const isEstimatedPriceSource = (
  source?: string
): boolean =>
  /unverified|closest match/i.test(source || "");

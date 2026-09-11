# Device Valuation Platform

AI-powered smartphone rating, inspection, and resale/exchange valuation platform. Users answer condition questions or submit photos, and the platform combines AI photo analysis with a machine-learned price model to produce a fair market, resale, and exchange price.

## Architecture

- **Backend**: FastAPI (Python) — `/backend`
  - REST API for device catalog, inspections, photo analysis, ML valuation, RAG knowledge base, and Supabase auth
  - ML price prediction (Random Forest via scikit-learn + joblib)
  - Computer vision (OpenCV + Ultralytics YOLO) phone/condition detection
  - Gemini-powered condition analysis and RAG answers
  - ChromaDB vector store for device knowledge
- **Frontend**: React + Vite + TypeScript — `/frontend`

## Requirements

- Python 3.10
- Node 20+
- PostgreSQL database (Supabase Postgres or local)
- Supabase project (for authentication)
- Google Gemini API key (photo condition analysis, RAG answers)

## Setup — Backend

```bash
cd backend

# 1. Create and activate a virtual environment
python -m venv venv
# Windows: venv\Scripts\activate     Linux/macOS: source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/macOS
# Edit .env with your DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_KEY,
# and GEMINI_API_KEY (see inline comments).

# 4. Train the ML price model (creates ml/models/price_model.joblib)
python -m ml.train_price_model

# 5. Run the API
uvicorn app.main:app --reload --port 8000
```

The API runs at `http://127.0.0.1:8000`. Interactive docs at `http://127.0.0.1:8000/docs`.

Health status (model loaded, dataset rows, database, Gemini config):
`http://127.0.0.1:8000/api/health`.

### API highlights

- `GET /api/device-prices?brand=&model=&storage=` — price lookup. For recently launched / unrecognized devices it returns `resolution: "not_found"` plus an `estimated_price_inr`, `estimated_matched_model`, and `notes` (dataset-closest-match ML estimate).
- `POST /api/device-catalog/devices` — add a new device so it appears in the dropdowns, in the ML dataset, and in the price cache. Body: `{ "brand", "model", "storage", "new_price_inr" }` (`new_price_inr` optional).
- `POST /ml/predict` — raw ML prediction with an optional `condition_score` (skips catalog/dataset matching).
- `POST /api/inspections` + `/api/inspections/{code}/valuate` / `.../exchange-valuate` / `.../analyze` — the full quick-value / photo / exchange inspection pipelines.

Each new device added via the API is written to `data/smartphones.csv`, so run `python -m ml.train_price_model` periodically to fold custom devices into the ML model.

### Backend tests

```bash
python -m pytest tests -q
```

## Setup — Frontend

```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Run the dev server
npm run dev
```

The frontend runs at `http://localhost:5173` and connects to the backend at `http://127.0.0.1:8000`. The Diagnostics page (`/diagnostics`) includes a "Backend" sensor check that pings `/api/health`.

To point the frontend at a different backend (e.g. a deployed API), create `frontend/.env.local` (see `frontend/.env.example`) and set:

```bash
VITE_API_URL=https://your-backend.example.com
```

Lint and production build:

```bash
npm run lint
npm run build
```

All three device flows (quick value, photo, exchange) let you pick a brand/model/variant from the catalog or type your own via **"Others (type your own)"** — including a brand-new brand. Unrecognized devices raise a "new device" warning with an ML estimate and an **Add to catalog** button; adding one registers it so future lookups resolve immediately with a confirmed price, and it becomes part of the retraining dataset.

The **Added Devices** screen (home page → "Added Devices") lists everything registered through the add-to-catalog flow, newest first: `GET /api/device-catalog/devices/recent`.

## Setup — Docker

Run the whole platform (backend + frontend) with Docker Compose:

```bash
# 1. Configure environment variables
cp backend/.env.example backend/.env      # Windows: copy backend\.env.example backend\.env
# Edit backend/.env with your DATABASE_URL, SUPABASE_URL,
# SUPABASE_SERVICE_KEY, and GEMINI_API_KEY.

# 2. Build images and start
docker compose up --build
```

- Backend API: `http://localhost:8000` (interactive docs at `http://localhost:8000/docs`)
- Frontend: `http://localhost:8080` (nginx serves the built SPA and proxies `/api` and `/ml` to the backend, so the browser uses a single origin)

The ML model is trained at image build time. If you add devices to the catalog at runtime, retrain inside the container and rebuild when you want it baked in:

```bash
docker compose exec backend python -m ml.train_price_model
```

## Environment Variables

See `backend/.env.example` for placeholders and where to obtain each value:
`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GEMINI_API_KEY`, and optional `GEMINI_MODEL`.

Frontend: `VITE_API_URL` (optional) overrides the backend URL that the React app talks to. Defaults to `http://127.0.0.1:8000`.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs backend unit tests and frontend lint/build on push to `main`.

## Important notes

- The trained ML model (`backend/ml/models/price_model.joblib`) is **gitignored** and must be generated locally with `python -m ml.train_price_model` (the dataset CSVs are committed).
- The real `.env` file is gitignored; only `.env.example` is committed.

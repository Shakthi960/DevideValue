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

The frontend runs at `http://localhost:5173` and connects to the backend at `http://127.0.0.1:8000`.

## Environment Variables

See `backend/.env.example` for placeholders and where to obtain each value:
`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GEMINI_API_KEY`.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs backend unit tests and frontend lint/build on push to `main`.

## Important notes

- The trained ML model (`backend/ml/models/price_model.joblib`) is **gitignored** and must be generated locally with `python -m ml.train_price_model` (the dataset CSVs are committed).
- The real `.env` file is gitignored; only `.env.example` is committed.

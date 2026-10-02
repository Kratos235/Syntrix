# Syntrix

A supply-chain resilience and recovery workspace built around deterministic graph algorithms, constrained allocation and discrete daily simulation. No AI scores.

## Available workflow
Dashboard → Supply network → Scenario simulator → Impact analysis → Recovery planner → Optimization results → Scenario comparison → Timeline → PDF/CSV reports.

The sample workspace is immediately usable without signing in. It has 33 synthetic Indian supply-chain nodes, 36 lanes, 24 descriptive products and a precomputed S2 shutdown scenario. Sample changes last for the browser session; authenticated scenarios persist in MongoDB.

## Configuration
Use existing `frontend/.env` and `backend/.env`; do not replace platform-provided MONGO_URL, DB_NAME or REACT_APP_BACKEND_URL. Configure Supabase URL/public key in both apps, OWNER_EMAIL on the backend and CORS_ORIGINS for the frontend origin. Never place a Supabase service-role key in browser code.

**Current setup blocker:** Supabase rejects the supplied public key as invalid. Live sign-in/signup cannot be completed until the workspace owner supplies a working key. The app shows this clearly and never bypasses authentication. The configured owner's verified email receives ADMIN; other roles come from trusted app_metadata, default VIEWER.

## Development and verification
- Frontend dependencies: `cd frontend && yarn install`
- Backend dependencies: `pip install -r backend/requirements.txt`
- Services are managed by the platform supervisor; ordinary source changes hot-reload.
- Build: `cd frontend && yarn build`
- Tests: `cd backend && pytest tests -v` (uses the configured external preview URL and a Mongo-backed test repository)
- Latest testing records: `test_reports/iteration_2.json`, `test_result.md` (81 backend checks passed; desktop/mobile flows verified)

## Model boundaries
The physical simulator uses aggregated equivalent units with 1:1 conversion, finite inventory, capacity and whole-day lead times. The product/BOM catalogue is descriptive, not a full product-level manufacturing model. All costs are INR; recovery costs are committed contracts. Results are calculated on synthetic data, not live operating forecasts.

Detailed algorithm definitions, schema, API, authorization and backlog: [Architecture](docs/ARCHITECTURE.md). Original requested scope: [Plan](plan/plan.md). Current completion and blockers: [PRD](memory/PRD.md).


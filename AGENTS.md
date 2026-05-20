# AGENTS.md

## Project Scope
- Repository: `agrovision-ai`
- Product: olive farm management platform with AI modules:
  - `Olive Detect`
  - `Harvest Time`
  - `Disease Scan`

## Non-Negotiable Guardrails
- Do not migrate frameworks.
- Do not rewrite the whole app for feature work.
- Keep changes small, testable, and localized.
- Preserve working endpoints and UI flows unless a bug requires change.
- For Harvest Time work:
  - Inspect existing harvest files first.
  - Do not retrain the image endpoint from old capacitance CSV assumptions.
  - Keep image endpoint logic modular and production-safe.
- Always run verification commands before finishing.

## Current Stack
- Backend: FastAPI (`backend/main.py`)
- Frontend: React + Vite + Tailwind + Leaflet (`frontend/src`)
- Persistence: SQLite (`data/analysis_history.db`)
- AI services: `backend/services/*` (PyTorch, Ultralytics, rule layers, adapters)

## Quick Start (Windows PowerShell)

### Backend setup
```powershell
cd C:\Users\Win11\Downloads\pfe\agrovision-ai
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Run backend
```powershell
cd C:\Users\Win11\Downloads\pfe\agrovision-ai
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

### Run backend tests
```powershell
cd C:\Users\Win11\Downloads\pfe\agrovision-ai
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

### Frontend setup + build
```powershell
cd C:\Users\Win11\Downloads\pfe\agrovision-ai\frontend
npm install
npm run build
```

## Harvest Logic: First Files to Inspect

### API and route orchestration
- `backend/main.py`

### Harvest services
- `backend/services/harvest_time_service.py`
- `backend/services/harvest_image_service.py`
- `backend/services/harvest_fusion_service.py`
- `backend/services/harvest_oil_service.py`
- `backend/services/climate_weather_service.py`
- `backend/services/climate_harvest_service.py`
- `backend/services/tunisian_harvest_logic.py`
- `backend/services/cultivar_service.py`

### Persistence and dashboard sync
- `backend/db/farm_repo.py`
- `backend/db/history_repo.py`

### Frontend harvest and dashboard
- `frontend/src/pages/HarvestTimePage.jsx`
- `frontend/src/pages/DashboardPage.jsx`
- `frontend/src/lib/api.js`
- `frontend/src/components/DragDropUpload.jsx`

## Working Style for Refactors
- Start with a targeted audit of the affected module.
- Keep existing response contracts unless coordinated changes are made.
- Add compatibility fields/routes when needed rather than breaking callers.
- Validate backend import/compile, test suite, and frontend build on every meaningful change.

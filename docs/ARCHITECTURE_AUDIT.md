# Harvest Time Architecture Audit (Phase 1)

## Current Architecture Summary
- Backend:
  - `backend/main.py` exposes a rich FastAPI API surface for disease, harvest, olive detection, scene routing, chat, weather, and orchard history.
  - AI logic is reasonably modular in `backend/services/*`.
  - Persistence is SQLite with repository functions in `backend/db/history_repo.py`.
- Frontend:
  - Single large app component (`frontend/src/App.jsx`) handles navigation, data fetching, forms, module workflows, and dashboard rendering.
  - Shared utilities exist in `frontend/src/lib`, but state and logic remain monolithic.

## What To Keep
- Existing inference services and model adapters:
  - `vision_service`, `harvest_image_service`, `olive_detection_service`, `harvest_fusion_service`
- Existing quality and scene routing logic.
- Existing history/orchard endpoints and database records.
- Existing multilingual dictionary as a migration base.

## What To Refactor
- Frontend information architecture:
  - split giant `App.jsx` into pages and reusable components.
- Frontend data layer:
  - centralize API calls and reduce duplicated fetch logic.
- Farm domain model:
  - separate farm profile/tree groups/scans/alerts from legacy tree-level tables.
- Dashboard composition:
  - derive widgets from persisted farm scan records.

## What To Replace
- Monolithic tab-driven UI with product-style flow:
  - landing
  - onboarding
  - dashboard
  - AI module pages
  - assistant workspace

## What To Remove (Gradually)
- Duplicated UI logic embedded in `App.jsx`.
- Hard-coded assumptions that couple dashboard and modules too tightly.

## Phased Implementation Plan
1. Phase 1:
   - architecture audit, repo guidance, migration-safe backend additions.
2. Phase 2:
   - farm onboarding APIs + frontend onboarding flow + map selection.
3. Phase 3:
   - dedicated pages for Olive Detect, Harvest Time, Disease Scan, Assistant.
4. Phase 4:
   - connect module outputs to farm scan records, alerts, and dashboard widgets.
5. Phase 5:
   - polish, responsive tuning, loading/error/empty states, tests and docs.

## Risk Control
- Keep old endpoints active while new farm APIs and UI are introduced.
- Use additive schema changes in SQLite.
- Build with compile checks and frontend production build checks after each phase.


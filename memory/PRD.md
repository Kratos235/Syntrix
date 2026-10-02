# Syntrix — Product & implementation record

## Original requirement
Build a supply chain resilience and recovery platform using graph algorithms, constrained optimization and daily simulation (no ML/AI). Premium dark enterprise command center, Cytoscape network, Supabase email/password identity; ADMIN, ANALYST, VIEWER. Currency INR. Full approved reference: `/app/plan/plan.md`.

## Confirmed decisions and constraints
- User explicitly retained Supabase and supplied project URL + anon key.
- Use Supabase Auth and platform-required MongoDB application storage (disclosed before credentials supplied).
- Owner email: aneeshsawant10@gmail.com. Owner ADMIN only after server verifies Supabase identity and confirmed email; no passwords supplied or accounts created.
- Initial provider check returned HTTP 401 Invalid API key. Do not claim live auth works; expose honest provider status and isolated synthetic sample workspace.
- No need for a service-role key or SQL connection for this identity architecture.

## Small, independently testable build steps
1. Foundation: Pydantic/Mongo models, deterministic 33-node/36-lane/24-product synthetic seed, protected auth dependencies. Verify deterministic counts, valid graph, unauthenticated denial.
2. Algorithms: validation, propagation, criticality, max-flow bottlenecks, supplier MIP, min-cost reserve reallocation, Dijkstra rerouting, order prioritization, plan generation, feasibility, daily simulation, recovery threshold, KPIs, Pareto/recommendation. Verify zero severity matches baseline, full failure reduces service, conservation, lead-time, feasible budgets and deterministic replay.
3. API pipeline: sample-only calculation endpoints separated from protected persisted scenarios; role checks and owner-scoped queries. Verify sample data isolation, validation errors, role denials, ownership and CRUD persistence.
4. Workspace: dashboard, network, simulator, impact, recovery, results, comparison, timeline, reports, login. Verify all routes and sample scenario end to end.
5. Exports and verification: server CSV/PDF, render PDF, desktop+390px mobile smoke, testing agent functional regression.

## Architecture
- React + Tailwind/shadcn + Recharts + Cytoscape; FastAPI + Motor + MongoDB.
- Supabase JS client + Auth API `/auth/v1/user` verification. Role from trusted app_metadata; VIEWER default. Verified configured owner ADMIN.
- network and scenario document models serialize all Mongo IDs via BaseDocument.
- Public synthetic endpoints never query private scenarios. Signed-in scenario queries include verified owner_id.
- Engine uses aggregated equivalent units; product/BOM catalogue is descriptive, not a multi-SKU production optimizer. Explicitly disclose this modelling limitation in UI/reports.

## Implemented and verified — 2026-10-02 preview environment date
- All 10 pages: login, dashboard, Cytoscape network, multi-event simulator, impact, recovery, optimization results, comparison, daily timeline, reports. Dark default and light toggle; 390px mobile navigation.
- Real deterministic aggregate engine with all 14 algorithm stages. Canonical baseline 100% service; S2 failure 92.15%; recovery trade-offs computed via real OR-Tools and NetworkX algorithms.
- Private Mongo scenario persistence, role-based action authorization and owner-scoped queries; public synthetic computation completely separated from private records.
- ReportLab PDF and CSV exports. Real PDF endpoints rendered and visually inspected, no blank/overflow pages. Selected plan is included.
- First testing pass: 55/55 backend tests, 10 scenario regressions, role matrix via isolated test overrides, public APIs and frontend flow smoke. Initial main screenshots correct 1920x800 and 390x844 without overflow. Live Supabase auth remains untestable due rejected public key.
- Post-test fixes verified: per-scenario budget/policy/strategies preserved for exports; selected plan preserved through scenario switching; baseline timeline no disruption highlighting; chart first-layout dimensions; malformed trusted role defaults to VIEWER.
- Final testing: `/app/test_reports/iteration_2.json`, **81/81 backend tests passed** (55 original + 26 added). Includes direct mocked Supabase identity response tests, verified-owner role mapping, VIEWER/ANALYST/ADMIN endpoint matrix, owner isolation on read/optimize/select/export/delete, Mongo roundtrip, options persistence, selected-plan report validation, transport-delay propagation, and ten deterministic scenarios. Nine workspace routes verified overflow-clean at exactly 1920x800 and 390x844, including long scenario names.
- PDF selected-plan report generated through real API and both pages rendered/viewed. Actual CSV/PDF streams verified. Sample calculations are not mocked; test provider mocks are isolated to tests only.
- Direct test review tightened two permissive PDF assertions: require real 200/PDF response and require 422 for an actually infeasible overlapping supplier allocation. Final suite rerun recorded in test_reports/pytest/final_results.xml.
- No known functional sample-workspace bugs. Non-functional dev annotator/Cytoscape console warnings are environment/library-specific and not blockers. Live Supabase remains blocked by rejected user key; do not claim live auth verified.
- Production frontend build passes. README and docs/ARCHITECTURE.md cover model, schema, API, tests and limitations.

## Scope differences from the original full plan
- Mongo application storage rather than Supabase Postgres/RLS (platform constraint, disclosed). Auth identity remains Supabase.
- Physical engine is aggregate-equivalent rather than product/BOM-specific; no claim of complete multi-SKU optimizer.
- Per-user private scenarios, not shared organization collaboration. Short simulations execute in a worker thread with a busy indicator, not a persisted background-job queue.
- Live auth / real owner and analyst sessions need a valid Supabase key. No role accounts/passwords were seeded, no identity bypass.
- Dataset import/mappings, advanced KPIs (utilization/agility), admin audit viewer, live progress and richer product constraints remain future work.

## Backlog
P0: Valid Supabase public key needed; then verify real sign-in, signup/email confirmation, owner access.
P1: Full product-specific BOM/inventory/order constraints beyond aggregate-equivalent simulation.
Phase 2: Admin user/role management; node/lane/product/inventory/order editing; audit viewer; Brunel/DataCo CSV field mapping, validation and import; custom seed.
Phase 3: Live simulation progress, saved scenario library/cloning/versioning, constrained multi-lane routing, stochastic lead-time, multi-organization workspaces.
Refactoring: none required beyond small domain modules in initial implementation.

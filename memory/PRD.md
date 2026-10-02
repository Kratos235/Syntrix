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

## In progress
All Phase 1 implementation and tests.

## Backlog
P0: Valid Supabase public key needed; then verify real sign-in, signup/email confirmation, owner access.
P1: Full product-specific BOM/inventory/order constraints beyond aggregate-equivalent simulation.
Phase 2: Admin user/role management; node/lane/product/inventory/order editing; audit viewer; Brunel/DataCo CSV field mapping, validation and import; custom seed.
Phase 3: Live simulation progress, saved scenario library/cloning/versioning, constrained multi-lane routing, stochastic lead-time, multi-organization workspaces.
Refactoring: none required beyond small domain modules in initial implementation.

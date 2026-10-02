# Syntrix architecture & algorithm reference

## Running services
FastAPI `backend/server.py` on the platform-managed backend service. React `frontend/src/App.js` on the platform-managed frontend service. Do not start independent servers. Configuration comes from backend/.env and frontend/.env; Mongo connection uses MONGO_URL and DB_NAME unchanged. Frontend uses REACT_APP_BACKEND_URL.

## Identity and authorization
Supabase JS handles email/password signup, confirmation, session persistence, refresh and sign-out. FastAPI verifies bearer tokens with Supabase /auth/v1/user on each protected request. app_metadata.role is trusted, user_metadata is not. Unknown roles become VIEWER. Confirmed OWNER_EMAIL maps to ADMIN. Authorization is centralized in auth.authorize; a user-scoped ScenarioRepository filters every read/write/delete by owner_id. This MVP uses private per-user scenarios rather than shared organization access.

Required auth config: SUPABASE_URL, SUPABASE_ANON_KEY, OWNER_EMAIL, corresponding REACT_APP_SUPABASE_URL and REACT_APP_SUPABASE_ANON_KEY. Public key supplied by user was rejected by the provider (401 Invalid API key); live signup/login must be retested when a corrected key is supplied. No service-role credential or SQL pooler string is needed. No custom auth bypass exists. No account passwords have been created.

## Data schema
- Network: `_id`, name, nodes, lanes, products, seed, synthetic. Generated deterministically by seed.synthetic_network and inserted once into Mongo.
- Node: id, name, echelon type, location/region, capacity, initial inventory, daily demand, priority, unit value.
- Lane: id, source/target, capacity, cost, lead_time, distance, mode, alternate.
- Product catalogue: 24 descriptive products, supplier, unit_value, one-component BOM. Not used as a multi-SKU physical optimization model.
- ScenarioDocument: `_id`, owner_id, config (disruptions, horizon, recovery threshold/window), impact, baseline, disrupted, plans, selected_plan, created_at. BaseDocument converts `_id` to JSON-safe `id`.
- Seed: 12 suppliers, 4 manufacturers, 5 warehouses, 12 customers; 36 lanes; 24 products. Canonical failure: S2, 100%, day 3 for 7 days.

## Engine / 14 stages
1. validate_network: duplicate identifiers, references, DAG, reachable customers, valid supplier/BOM quantities, lane-vs-dispatch warnings.
2. propagate: descendant traversal and Dijkstra lead-time paths; structural exposure is not realized loss.
3. criticality: normalized betweenness and downstream demand; no predictive risk score.
4. bottlenecks: node-split max-flow/min-cut enforcing physical node and lane capacity.
5. supplier_mip: OR-Tools SCIP integer procurement/activation, compatible supplier capacity, cost and budget, shortage slack.
6. inventory_flow: NetworkX min-cost max-flow from finite reserve stock over real alternate lanes, capped by budget.
7. reroute: Dijkstra on available graph; only real alternate lanes can be activated; no fabricated connectivity.
8. prioritize_orders: business priority, due date, smallest remaining quantity.
9. generate_strategies: alternative sourcing, reserve allocation, rerouting, priority policy, combined procurement + inventory.
10. check_feasibility: committed budget, inventory, duration/lane limits, overlapping supplier overtime; no action creates free supply.
11. simulate: receive arrivals, supplier production, due orders, fulfilment, reverse-echelon dispatch, next-day-or-later shipments, daily state ledger. Finite stock and per-node/per-lane capacities. Initial in-transit flows represent a steady-state pipeline. Conservation residual returned for verification.
12. recovery_time: after final deterioration, first sustained threshold window; no deterioration = zero; cannot establish recovery within horizon = null.
13. calculate_kpis: unit-based on-time service, fulfilment, backlog, overdue orders, unit-weighted delay, perfect-order rate, committed recovery cost, operating spend and INR exposure.
14. pareto_compare: four-objective nondomination and normalized deterministic recommendation; balanced weights service .35, cost .25, speed .20, unmet demand .20.

## Explicit modelling boundaries
Flows are aggregated equivalent units with 1:1 conversion. Per-product inventories, multi-level BOM material balance, product compatibility and order-specific pricing are not modelled. Daily customer orders use synthetic quantities/priorities. Demand surge adds demand; transportation severity adds up to 5 whole days. In-transit shipments already dispatched are not recalled by later closures. Inventory at an out-of-service node can receive arrivals but cannot dispatch while capacity is zero. Supplier recovery assumes contracted overtime and matching expedited lane capacity, bounded at 75% nominal additional capacity. Recovery costs represent committed contracts, not actual utilized spend. Short sample jobs run in threadpool; true background queue/progress updates remain future work.

## APIs
Public: GET /api/, GET /api/auth/status, GET /api/sample/workspace, POST /api/sample/simulate, POST /api/sample/optimize, POST /api/sample/report/pdf or csv.
Authenticated: GET /api/me, GET /api/network, GET/POST /api/scenarios, GET/DELETE /api/scenarios/{id}, POST /api/scenarios/{id}/optimize, POST /api/scenarios/{id}/select, GET /api/scenarios/{id}/report/{format}.
Public sample endpoints never query private scenario collections. Synthetic computations are genuine but not persisted between browser reloads. Authenticated scenarios persist in Mongo. Role permissions: VIEWER read/export; ANALYST adds simulate/optimize/select; ADMIN adds delete.

## UI and exports
Dashboard uses stored/computed current scenario results. Cytoscape network supports pan, zoom, search, echelon filtering, directory and node inspector. Simulator accepts 1–5 simultaneous events. Recovery uses adjustable budget and policy; results show allocations/constraints and plan selection. Comparison supports cost/service/speed/balanced recommendations. Timeline is client-side playback of persisted daily states, not a scheduled backend task. PDF (ReportLab) and CSV are generated server-side. Report cost currency INR.

## Later phases / not delivered in this MVP
Admin user management, network/data editing, CSV imports with Brunel/DataCo mappings, custom seed, live progress, cloned/versioned scenario library, multi-lane multi-commodity routing, stochastic lead times, multi-organization access, full SKU/BOM inventory model. These remain backlog, not mocked features.

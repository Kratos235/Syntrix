# Syntrix — Supply Chain Resilience & Recovery Platform

A web-based decision-support system that models a multi-echelon supply chain as a connected network, simulates disruptions, traces their ripple effects, generates and optimizes recovery strategies, simulates them day by day, and compares outcomes on service, cost, recovery time and unmet demand.
All intelligence comes from graph algorithms, constraint optimization and discrete-time simulation — no machine learning, no AI scores, no hard-coded dashboard numbers.

## Who it's for

- **Supply-chain analysts / planners** who need to answer "what breaks if Supplier S2 fails for a week, and what is the best way to recover?"
- **Operations leadership** who want a single executive view of network health, active disruptions, orders at risk and recovery cost.
- **Project evaluators (PBL panel)** who must see a reproducible, explainable, end-to-end pipeline running on real algorithms.

## Core features and experience

**1. Supply-chain network model**
- Directed graph of Suppliers → Manufacturers → Warehouses → Distribution Centers → Customers, connected by transport lanes with distance, cost, lead time, capacity and status.
- Products with BOM, supplier–product relationships (capacity, unit cost, lead time, MOQ, reliability), warehouse inventory (quantity, safety stock, reorder level), customer orders (quantity, due date, priority, status).
- Network validation report before any simulation: broken references, unreachable demand nodes, negative quantities, invalid BOMs, over-committed capacities.

**2. Interactive network view (Cytoscape)**
- Status-coloured nodes: Operational / Warning / Disrupted / Recovering / Recovered.
- Click a node → side panel with capacity, inventory, products, connected nodes, status, and a plain-language criticality explanation ("High criticality: 5 downstream products depend on this supplier and only one alternative exists").
- Bottleneck lanes highlighted from max-flow / min-cut analysis.

**3. Scenario simulator**
- Presets: Supplier Failure, Supplier Capacity Reduction, Transportation Delay, Lane Closure, Warehouse Outage, Demand Surge, Production Capacity Reduction, Multiple Simultaneous Disruptions.
- Inputs: name, type, target node/lane, start day, duration, severity, capacity reduction, horizon (default 30 days).
- Actions: Run Impact Analysis, Run Full Simulation, Reset.

**4. Impact analysis**
- Graph traversal with supply-chain dependency rules computes real operational effects: affected nodes, products, production loss, inventory shortfall, affected orders, unmet demand, expected delay, estimated cost impact.
- Visual propagation tree from disruption origin to affected orders, plus inventory-depletion, service-deterioration and production-impact charts.

**5. Recovery planner and optimization**
- Strategies: A Alternative Supplier (OR-Tools MIP), B Inventory Reallocation (min-cost flow), C Logistics Rerouting (Dijkstra with disruption-aware weights), D Order Prioritization (configurable policy: service-first / urgency-first / business-priority-first), E Combined Recovery.
- Every plan passes a feasibility checker; infeasible plans are labelled with the exact violated constraint ("Supplier capacity insufficient by 230 units").
- Results page per plan: feasibility, recovery cost, service level, recovery time, unmet demand, delayed orders, utilization, plus "Why is this plan feasible?" and "What constraints determined the allocation?".

**6. Daily simulation and KPI engine**
- Day-by-day engine (receive shipments → update inventory → apply supplier capacity → production → fulfil orders → move shipments → apply disruptions → execute recovery → KPIs → persist state).
- KPIs: Service Level, Unmet Demand, Delayed Orders, Average Delay, Recovery Time (derived from a configurable threshold, not assumed), Recovery Cost, Capacity Utilization, Orders at Risk, perfect-order-style Reliability, Responsiveness (fulfilment cycle time), Agility (recovery effectiveness). SCOR-aligned terminology.
- Timeline page: service level, inventory, backlog and cost by day with markers for disruption start, recovery start, threshold and recovery achieved.

**7. Scenario comparison**
- Disrupted baseline vs every plan in one table and in grouped bars, recovery curves, cost and unmet-demand charts.
- Pareto-efficient plans identified and shown; user picks a priority (Cost / Service / Speed / Balanced) and the deterministic recommender highlights the plan for that priority with the reason.

**8. Executive dashboard**
- Network Health, Active Disruptions, Affected Nodes, Orders at Risk, Service Level, Recovery Time, Recovery Cost, Unmet Demand — all read from stored simulation results.

**9. Reports**
- Scenario report (scenario, disruption, impact, strategies, optimization, KPIs, comparison, selected plan, explanation) with PDF and CSV export.

**10. Accounts and roles**
- Supabase email + password sign-in. Roles ADMIN (full management), ANALYST (create scenarios, run simulations, build recovery plans), VIEWER (read-only dashboards and reports). Roles enforced by the backend on every request and by Postgres row-level security.

**11. Demo data**
- Deterministic synthetic network regenerated identically from a fixed seed: 12 suppliers, 4 manufacturers, 5 warehouses, 12 customer/distribution nodes, ~30 lanes, ~24 products, inventory and orders.
- Canonical demo scenario pre-loaded: **Supplier S2 fails 100% for 7 days** — runs end-to-end from a fresh seed.

## User flow

1. Sign in → lands on Executive Dashboard showing baseline health of the seeded network.
2. Opens Supply Network → explores nodes, reads criticality explanations, sees bottleneck lanes.
3. Opens Scenario Simulator → selects "Supplier Failure", target S2, start day 3, duration 7, severity 100% → Run Impact Analysis.
4. Impact Analysis shows the propagation tree, affected products/inventory/orders and unmet demand.
5. Recovery Planner → ticks the strategies to generate (defaults: all five) → Generate Recovery Plans.
6. Optimization Results lists each plan with feasibility badge, allocations and constraint explanations → Run Full Simulation.
7. Simulation Timeline shows recovery curves per plan; Scenario Comparison shows the trade-off table, Pareto set and the recommended plan for the chosen priority.
8. Reports → generate scenario report → export PDF or CSV.
9. Dashboard now reflects the active scenario's results.

## UI/UX feel

- Premium enterprise command center: Linear/Vercel-level restraint and typography, Stripe-level data clarity, Kinaxis/IBM-style operational workflow.
- **Dark theme by default** with a light toggle; solid dark surfaces, one sharp accent colour for primary actions, dedicated status colours (operational / warning / disrupted / recovering / recovered) used consistently across graph, tables and KPI cards.
- Persistent left sidebar navigation in pipeline order; dense but readable tables; KPI cards with trend deltas; detail side panels for drill-down instead of page jumps; progressive disclosure — primary metrics first, charts on demand.
- Desktop-first, responsive down to tablet. Minimal animation (subtle transitions only). No hero sections, gradients, or "AI" branding. Costs shown in ₹.

## Implementation phases

**Phase 1 — MVP (built now)**
- Supabase Postgres schema with migrations, Supabase Auth, three roles, RLS, seeded synthetic network and S2 demo scenario.
- All 14 algorithms: validation, propagation, criticality, bottleneck, supplier MIP, min-cost-flow reallocation, rerouting, order prioritization, strategy generation, feasibility checker, daily simulation, recovery time, KPI engine, Pareto comparison + priority recommender.
- Pages: Login, Executive Dashboard, Supply Network, Scenario Simulator, Impact Analysis, Recovery Planner, Optimization Results, Scenario Comparison, Simulation Timeline, Reports (PDF/CSV).
- Backend unit tests for every algorithm, integration test of the full pipeline, and the ten deterministic scenario tests. README, architecture, schema, algorithm, API, dataset and testing documentation.

**Phase 2 — Data Management and Admin**
- Admin page: manage users and roles, edit nodes, lanes, products, inventory and orders in-app, audit log viewer.
- Data Management page: CSV upload with field mapping, validation and import summary for the Brunel Supply Chain Logistics dataset and DataCo Smart Supply Chain dataset; regenerate synthetic network with a chosen seed.

**Phase 3 — Live operations and depth**
- Realtime simulation progress and dashboard updates (Supabase Realtime).
- Scenario library with saved comparisons, scenario cloning and versioning.
- Capacity-constrained multi-lane routing fed into the flow optimizer; stochastic lead-time variability in the simulator; multi-organization workspaces.

## Assumptions

- **Credentials needed before the build starts:** Supabase project URL, anon (publishable) key, service-role key, and the **Transaction Pooler** connection string (port 6543). The build cannot begin without these; they will be requested after plan approval.
- Supabase project should use an asymmetric JWT signing key (Project Settings → JWT Keys); email confirmation is turned off for the demo so seeded accounts can sign in immediately.
- Three seeded accounts (one per role) are created for demonstration; the first ADMIN is assigned through a trusted migration, and role changes happen only server-side.
- Supabase is the only database; the platform's default MongoDB is not used.
- Frontend is React with JavaScript (platform template) using Tailwind, shadcn/ui, React Router, TanStack Query, Cytoscape.js, Plotly.js and Lucide icons — functionally identical to the spec's React + TypeScript choice.
- Single organization in the MVP; the organizations table exists but all data belongs to one default organization.
- Recovery threshold defaults to "service level within 5 points of baseline for 3 consecutive days"; simulation horizon defaults to 30 days; both configurable per scenario.
- Order prioritization default policy is business-priority-first; comparison default priority is Balanced.
- PDF export is generated server-side from stored results; CSV export covers the KPI comparison table and daily simulation states.
- Impact Analysis runs synchronously; Full Simulation runs as a background job with polling for status (no Realtime in MVP).
- Brunel and DataCo datasets are documented and schema-mapped in Phase 1 but importable only in Phase 2.
- No UI reference photos were provided; visual design follows the reference formula (Kinaxis/SAP/IBM workflow + Linear/Vercel polish + Stripe data density + Cytoscape network).
- Not included at any phase: ML, chatbots, blockchain, IoT, GPS tracking, ERP/SAP integration, fleet routing, Kafka/Kubernetes/Redis.

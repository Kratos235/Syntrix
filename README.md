# Syntrix
### Supply Chain Resilience, Disruption Simulation & Recovery Optimization

Syntrix is a supply-chain decision-support platform that helps users understand network vulnerabilities, simulate disruptions, compare their operational impact, and evaluate recovery strategies. It combines graph algorithms, constrained optimization and discrete-time simulation in an interactive workspace.

The platform provides an end-to-end workflow — from exploring a supply network to modelling disruption scenarios, allocating constrained resources, comparing recovery plans and exporting reports.

## Overview

A supply chain is a connected network of suppliers, manufacturers, warehouses, transport lanes and customers. A disruption at one point can affect downstream operations.

Syntrix models these relationships as a directed network and provides tools to examine how disruptions propagate, where capacity constraints occur, and which recovery actions can improve service while respecting inventory, capacity, lead-time and budget constraints.

### Demo workspace

The sample workspace is available immediately and includes a reproducible synthetic Indian supply-chain network:

- **33 network nodes** across suppliers, manufacturers, warehouses and customers
- **36 transport lanes** with capacity, cost and lead-time attributes
- **24 descriptive products**
- A preconfigured supplier shutdown scenario for exploring the workflow

Sample scenarios can be explored without signing in. When a user is authenticated, their scenarios can be saved and revisited.

## Key features

### 1. Supply network explorer
- Interactive network visualisation with pan and zoom.
- Search nodes and filter the network by supply-chain echelon.
- Inspect node details, capacity, inventory, demand and connected lanes.
- Explore alternate transport connections and network structure.

### 2. Disruption scenario simulator
- Model multiple concurrent disruption events.
- Configure the affected node or transport lane, disruption severity and duration.
- Examine downstream exposure and operational impact.
- Compare baseline network performance with disrupted conditions.

### 3. Impact analysis
- Trace downstream exposure through the supply network.
- Identify critical nodes using graph-based network measures.
- Analyse bottlenecks using network flow and capacity constraints.
- Review service, fulfilment, backlog, delay and cost indicators.

### 4. Recovery planning and optimization
Generate and evaluate recovery strategies using available resources and operational constraints, including:

- Alternative supplier allocation.
- Reserve inventory allocation.
- Transport rerouting through available alternate lanes.
- Order-priority policies.
- Combined procurement and inventory strategies.

The optimizer evaluates feasible plans against budget, supplier capacity, available inventory, lane capacity and recovery duration.

### 5. Scenario comparison and reporting
- Compare recovery plans across service, cost, recovery speed and unmet demand.
- Review a deterministic multi-objective recommendation.
- Inspect daily operational changes through a scenario timeline.
- Export analysis as PDF and CSV reports.

## Optimization and simulation engine

Syntrix uses a deterministic, multi-stage engine to evaluate supply-chain disruptions and recovery strategies.

| Method | Purpose |
|---|---|
| Directed graph traversal | Validate network structure and trace downstream exposure |
| Dijkstra's shortest-path algorithm | Evaluate lead-time paths and alternate routing |
| Betweenness centrality | Assess node criticality in the supply network |
| Maximum flow / minimum cut | Identify capacity bottlenecks |
| OR-Tools integer optimization | Allocate supplier procurement and activation decisions under constraints |
| NetworkX min-cost max-flow | Allocate reserve inventory across available network lanes |
| Discrete-time simulation | Model arrivals, production, order fulfilment, inventory and capacity over the planning horizon |
| Pareto comparison | Compare recovery strategies across multiple objectives |

### Daily simulation and performance indicators

The simulation advances through daily operational states, considering shipment arrivals, supplier production, due orders, fulfilment and dispatch decisions.

The analysis reports indicators such as:

- On-time service and order fulfilment.
- Backlog and overdue orders.
- Order delay and perfect-order rate.
- Recovery time.
- Operating spend and committed recovery cost.
- Monetary exposure in INR.

### Multi-objective recovery evaluation

Recovery plans can be compared using four objectives:

- Service improvement
- Recovery cost
- Recovery speed
- Unmet demand

The balanced recommendation uses the following weights:

| Objective | Weight |
|---|---:|
| Service | 0.35 |
| Cost | 0.25 |
| Recovery speed | 0.20 |
| Unmet demand | 0.20 |

## Technology stack

| Layer | Technologies |
|---|---|
| Frontend | React 19, JavaScript, Tailwind CSS |
| Interactive network visualisation | Cytoscape.js |
| Charts and data visualisation | Recharts |
| Backend API | Python, FastAPI |
| Graph modelling | NetworkX |
| Mathematical optimization | Google OR-Tools |
| Data processing | NumPy, Pandas |
| Database | MongoDB, Motor |
| Authentication | Supabase Auth |
| Reporting | ReportLab, CSV |
| Testing | Pytest |

## System architecture

The application is organised into a React frontend and a FastAPI backend.

```text
                 React Frontend
                       |
             REST API / Bearer Token
                       |
                 FastAPI Backend
                       |
          +------------+-------------+
          |                          |
    Authentication              Syntrix Engine
    & Authorization                  |
          |                 +--------+---------+
          |                 |        |         |
          |               Graph   Optimizer  Simulator
          |              Analysis   OR-Tools  Daily Flow
          |                 |        |         |
          +-----------------+--------+---------+
                                |
                           MongoDB
                    Networks & User Scenarios
                                |
                       PDF / CSV Reports
```

### Main backend responsibilities

- **Network modelling:** stores nodes, lanes, products and network configuration.
- **Scenario management:** saves scenario configuration, disruption events, analysis results and selected recovery plans.
- **Optimization engine:** validates constraints and generates feasible recovery alternatives.
- **Simulation engine:** evaluates daily network operations under baseline, disrupted and recovery conditions.
- **Reporting:** generates downloadable PDF and CSV reports.

### Authentication and access roles

Supabase handles account authentication and session management. The backend validates bearer tokens and applies role-based permissions to scenario operations.

| Role | Access |
|---|---|
| VIEWER | View scenarios and export reports |
| ANALYST | Viewer permissions, plus simulate, optimize and select recovery plans |
| ADMIN | Analyst permissions, plus scenario deletion |

Scenario records are scoped to their owner.

## Application workflow

```text
Dashboard
   |
   v
Supply Network Explorer
   |
   v
Scenario Simulator
   |
   v
Impact Analysis
   |
   v
Recovery Planner
   |
   v
Optimization Results
   |
   v
Scenario Comparison
   |
   v
Timeline & Reports
   |
   v
PDF / CSV Export
```

## API overview

The FastAPI backend exposes public sample-workspace endpoints and authenticated scenario endpoints.

### Sample workspace

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/` | API status |
| GET | `/api/auth/status` | Authentication configuration status |
| GET | `/api/sample/workspace` | Load the sample workspace |
| POST | `/api/sample/simulate` | Simulate a sample disruption |
| POST | `/api/sample/optimize` | Optimize sample recovery plans |
| POST | `/api/sample/report/pdf` | Generate a sample PDF report |
| POST | `/api/sample/report/csv` | Generate a sample CSV report |

### Authenticated workspace

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/me` | Current authenticated user |
| GET | `/api/network` | Retrieve the user's network |
| GET / POST | `/api/scenarios` | List or create scenarios |
| GET / DELETE | `/api/scenarios/{id}` | Retrieve or delete a scenario |
| POST | `/api/scenarios/{id}/optimize` | Generate recovery plans |
| POST | `/api/scenarios/{id}/select` | Select a recovery plan |
| GET | `/api/scenarios/{id}/report/{format}` | Export a scenario report |

## Getting started

### Prerequisites

- Python 3.11 or later
- Node.js 18 or later
- Yarn
- MongoDB connection
- Supabase project credentials for authenticated access

### 1. Configure environment variables

Keep the existing environment files in `backend/.env` and `frontend/.env`. Configure the following values for your environment:

**Backend — `backend/.env`**

```env
MONGO_URL=your_mongodb_connection_string
DB_NAME=syntrix
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_public_anon_key
OWNER_EMAIL=admin@example.com
CORS_ORIGINS=http://localhost:3000
```

**Frontend — `frontend/.env`**

```env
REACT_APP_BACKEND_URL=http://localhost:8000
REACT_APP_SUPABASE_URL=your_supabase_project_url
REACT_APP_SUPABASE_ANON_KEY=your_supabase_public_anon_key
```

Use the same Supabase project URL and public anon key in both applications. Keep private credentials and service-role keys out of frontend code and source control.

When using the hosted development workspace, retain the platform-provided `MONGO_URL`, `DB_NAME` and `REACT_APP_BACKEND_URL` values.

### 2. Install backend dependencies

From the repository root:

```bash
pip install -r backend/requirements.txt
```

### 3. Install frontend dependencies

```bash
cd frontend
yarn install
```

### 4. Build the frontend

```bash
cd frontend
yarn build
```

In the hosted development workspace, the platform supervisor manages the frontend and backend services and applies source changes through its development workflow.

## Testing and verification

Backend tests are located in `tests/`.

Run the backend test suite from the repository root:

```bash
cd backend
pytest tests -v
```

The repository's Iteration 2 verification report records:

- **81 of 81 backend checks passed.**
- Authentication and role-permission behaviour covered by automated tests.
- Scenario ownership and recovery-plan selection checks.
- PDF and CSV report validation.
- Nine frontend views checked at desktop and mobile viewport sizes.

See [Iteration 2 test report](test_reports/iteration_2.json) and [test history](test_result.md) for the recorded verification details.

## Project documentation

- [Architecture and algorithm reference](docs/ARCHITECTURE.md)
- [Project plan](plan/plan.md)
- [Iteration 2 test report](test_reports/iteration_2.json)
- [Test history](test_result.md)

## Design principles

- **Constraint-aware decisions:** recovery actions are evaluated against available resources and network capacity.
- **Explainable computation:** graph analysis, optimization objectives and simulation outputs are inspectable.
- **Reproducible scenarios:** deterministic sample data supports repeatable analysis and demonstrations.
- **Operational visibility:** network views, KPIs, timelines and reports bring scenario results into one workflow.

---

Syntrix combines graph theory, operations research and full-stack application development to explore how supply chains respond to disruption and recover under operational constraints.

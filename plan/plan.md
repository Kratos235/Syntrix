# Running Syntrix Locally

A step-by-step guide to run the Syntrix supply-chain platform on your own machine.
Syntrix has three parts that all need to be running together: a MongoDB database, the Python backend, and the React frontend.

## Who this is for

Anyone who wants to run the existing app on a personal laptop/desktop (macOS, Linux, or Windows with WSL) outside the Emergent preview environment.

## What you need installed first

- **Python 3.11+** (the backend is FastAPI)
- **Node.js 18+** and **Yarn** (the frontend is React; use Yarn, not npm)
- **MongoDB** running locally on the default port `27017` (Community Edition is fine), OR a free MongoDB Atlas cloud connection string

## Good to know before you start

- The app runs fully on built-in **sample data**. You do **not** need a working Supabase account or any API key to see every screen and feature locally.
- Supabase is only used for real user login/roles. With no valid key, the app automatically opens the sample workspace — which is the expected local experience.
- Two terminal windows stay open while you use the app: one for the backend, one for the frontend.

## Step 1 — Start MongoDB

- If MongoDB is installed locally, make sure its service is running and listening on `mongodb://localhost:27017`.
- Alternatively, create a free MongoDB Atlas cluster and copy its connection string for use in Step 2.

## Step 2 — Backend (the API)

1. Open a terminal in the `backend` folder.
2. Create and activate a Python virtual environment.
3. Install the Python dependencies from `requirements.txt`.
   - One dependency (`emergentintegrations`) comes from a special package source and needs the extra index URL shown in the project notes; the rest install normally.
4. Confirm the backend `.env` file has:
   - `MONGO_URL` — your local `mongodb://localhost:27017` (or your Atlas string)
   - `DB_NAME` — any database name you like
   - `CORS_ORIGINS` — set this to `http://localhost:3000` for local use
5. Start the API on port **8001**.
6. Check it works by opening `http://localhost:8001/api/` — you should see a small JSON status message.

## Step 3 — Frontend (the website)

1. Open a second terminal in the `frontend` folder.
2. Install dependencies with Yarn.
3. In the frontend `.env` file, set `REACT_APP_BACKEND_URL` to `http://localhost:8001` (point it at your local backend instead of the preview URL).
4. Start the frontend on port **3000**.
5. Open `http://localhost:3000` in your browser.

## Step 4 — Use the app

- The app opens in the **sample workspace** with synthetic supply-chain data.
- You can explore the network graph, run simulations, generate recovery plans, compare scenarios, and export CSV/PDF reports — all without logging in.

## Optional — Enabling real login locally

Real Supabase login currently does not work because the saved Supabase key is invalid. To turn on real accounts and roles later, a valid Supabase **project URL** and **anon key** would need to be placed in both the backend and frontend `.env` files. Until then, the sample workspace is the intended local mode.

## Assumptions made in this guide

- You are comfortable using a terminal/command line.
- You will run the database, backend, and frontend on the same machine using the default ports (`27017`, `8001`, `3000`).
- Local use does not require real authentication; the sample workspace is acceptable for running and evaluating the app.
- No code changes are required to run locally — only `.env` values are pointed at local addresses.

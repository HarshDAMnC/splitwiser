# Splitwiser 🚀

Splitwiser is a lightweight Splitwise-like app — a single-page static frontend (served by Nginx) and a Flask backend that stores and simplifies group expense debts. This README explains the architecture, important algorithms, database concepts, and the DevOps work done (Docker images, CI/CD, and Minikube Kubernetes manifests) so you can run and extend the project locally or in a cluster.

Table of contents
- Overview
- Architecture (high-level)
- Important algorithms (debt simplification)
- Data model & DB concepts
- HTTP API (quick reference)
- DevOps & CI/CD (what's configured)
- Local development (docker-compose)
- Kubernetes on Minikube (manifests & how to run)
- Troubleshooting & debugging
- Next steps / improvements
- Contributing & License

---

Overview
--------
Splitwiser lets groups of users add expenses and automatically computes minimized transactions needed to settle debts. It uses:
- Frontend: static JS/HTML/CSS served by Nginx
- Backend: Python Flask API (listens on port 5000)
- Data storage: Supabase (Postgres-like service) — the repo also supports an in-memory MockDB for local dev
- Dockerized images for frontend + backend and a GitHub Actions CI/CD that builds & pushes the images to Docker Hub.

Emojis: 🧾 (expenses) • 👥 (groups/users) • 💸 (payments) • 🧠 (algorithm)

Architecture (high-level)
-------------------------
ASCII diagram:

Browser (client)
  └─→ GET http://<minikube-ip>:30080/ (frontend NodePort)  → Frontend Pod (nginx) 🟦
        • Serves HTML / JS / CSS
        • Optionally proxies /api → backend (recommended)
Frontend JS in browser
  └─→ fetch('/api/...') or fetch('<api-url>') → frontend Nginx proxy (in-cluster)
        └─→ resolves DNS "backend" → backend Service (ClusterIP) ☸️
              └─→ backend Pod (Flask) 🐍 (port 5000)
                    └─→ Supabase (external DB) 🌐

Key Kubernetes resources (what we created/used):
- Deployment (frontend) → runs nginx container from Docker Hub image
- Service (frontend, NodePort) → exposes frontend to host (e.g., port 30080)
- Deployment (backend) → runs Flask container from Docker Hub image
- Service (backend, ClusterIP) → internal service used by frontend backend-proxy
- Secret (supabase-env) → holds SUPABASE_URL & SUPABASE_KEY injected into backend env

Important algorithms — debt simplification 🧠
-------------------------------------------
The core algorithm is in backend/services/graph_algo.py — `simplify_debts(balances)`.

What it does:
- Input: mapping of user_id → net balance (positive = creditor, negative = debtor).
- Goal: produce a minimal set of payments (debtor → creditor, amount) to settle all balances.

Approach used:
- Greedy max-heap approach:
  - Build two heaps: creditors (largest positive balances first) and debtors (largest absolute negative balances first).
  - Repeatedly match the largest creditor with the largest debtor, settle the minimum of the two, and push back any residue.
- Complexity:
  - Time: O(V log V) where V = number of users (heap pushes/pops dominate).
  - Space: O(V) to store heaps.

Why this is good:
- Fast and simple; produces a minimal number of transactions for many practical cases.
- Deterministic and easy to reason about.

Limitations:
- This greedy approach does not guarantee the absolute minimum number of transactions in all pathological graphs (there are constrained NP-hard variants), but it is optimal for typical split/expense graphs and is standard for these applications.

Database concepts & data model
------------------------------
The project uses Supabase (hosted) as the production DB. The code also supports an in-memory MockDB for local testing without external credentials.

Primary collections/tables used by backend/services/db_service.py:
- users: { id, name, email, created_at }
- groups: { id, name, description, created_by, created_at }
- group_members: { id, group_id, user_id, joined_at }
- categories: (not heavily used; placeholder)
- expenses: { id, group_id, description, total_amount, created_by, created_at, ... }
- expense_payers: per-expense who paid how much (amount_paid)
- expense_splits: per-expense who owes how much (amount_owed)
- user_balances_cache: cache of net balances per user per group (used to compute simplify_debts input efficiently)
- transactions: cached system-generated simplified transactions
- settlements: manual settlements recorded by users (from_user_id, to_user_id, amount, status)

Key DB behaviors:
- add_expense() updates:
  - Creates expense, expense_payers, expense_splits
  - Calls update_balance_cache() to increment payer balances and decrement split balances (maintains net balances)
- get_group_balances(group_id):
  - Reads user_balances_cache to produce net balances quickly (avoids recomputing from all expenses)
- settle_all(group_id):
  - Uses simplify_debts() to generate transactions then persists settlements and clears cached system-generated transactions.

Note: When Supabase credentials (SUPABASE_URL & SUPABASE_KEY) are not present, the code falls back to an in-memory MockDB that mimics expected operations. This is useful for unit tests and offline development.

HTTP API (quick reference)
--------------------------
Implemented in backend/app.py (main endpoints):

- GET /health
  - Returns status and whether DB is mock or real.

- POST /api/seed
  - Seeds a sample group and users (helpful for testing).

- GET/POST /api/users
  - List users / create user

- DELETE /api/users/<user_id>
  - Delete user and associated records

- GET/POST /api/groups
  - List groups / create group

- DELETE /api/groups/<group_id>

- GET/POST /api/groups/<group_id>/members
  - List members / add member

- POST /api/expenses
  - Add expense. Payload: { group_id, description, total_amount, created_by, payers, splits }

- DELETE /api/expenses/<expense_id>?group_id=<group_id>

- GET /api/groups/<group_id>/expenses
  - List expenses for group

- GET /api/groups/<group_id>/settle
  - Compute simplified transactions using `simplify_debts()` and cache them

- POST /api/groups/<group_id>/settle-all
  - Create settlements for all minimized transactions and persist them

- POST /api/settlements
  - Record a manual settlement: { group_id, from_user, to_user, amount }

DevOps / CI-CD (what's in the repo) 🛠️
------------------------------------
CI workflow: .github/workflows/ci-cd.yml
- Jobs:
  1. test — runs backend unit tests with pytest on Python 3.11
  2. build-and-push — depends on tests; uses docker/build-push-action to build images for backend & frontend and push to Docker Hub.

Important environment & tags:
- Docker Hub username in workflow: `harshs3185`
- Images built & pushed:
  - Backend: `harshs3185/splitwiser-backend:${{ github.sha }}` and `harshs3185/splitwiser-backend:latest`
  - Frontend: `harshs3185/splitwiser-frontend:${{ github.sha }}` and `harshs3185/splitwiser-frontend:latest`
- Login uses `secrets.DOCKERHUB_TOKEN` (make sure this is configured in repository secrets)
- The workflow uses multi-platform buildx (linux/amd64, linux/arm64) and pushes both commit-SHA-tagged and `latest` tags.

Docker images & Dockerfiles
- backend/Dockerfile:
  - Base: python:3.11-slim
  - WORKDIR /app
  - Installs requirements and runs `python backend/app.py` which starts Flask on port 5000
  - Exposes container port 5000

- frontend/Dockerfile:
  - Base: nginx:alpine
  - Copies static files to /usr/share/nginx/html and exposes port 80
  - The static app currently hard-codes `API_BASE = 'http://localhost:5000/api'` in frontend/app.js (see "Frontend <-> Backend networking" below).

Local development (docker-compose)
---------------------------------
docker-compose.yml (root) is provided for quick local dev:

- backend: built from ./backend, container_name splitwise_backend, ports "5000:5000", env_file ./backend/.env (contains SUPABASE values)
- frontend: built from ./frontend, container_name splitwise_frontend, ports "8080:80", depends_on backend

To run locally with docker-compose:
1. Ensure you have Docker installed.
2. Optionally provide Supabase credentials in backend/.env (already present in repo — treat secrets carefully).
3. Start:
   docker-compose up --build
4. Access frontend at http://localhost:8080 and backend at http://localhost:5000

Kubernetes on Minikube (what was prepared) ☸️
--------------------------------------------
We prepared k8s manifests (put them under k8s/ when you add them to the repo). Resources created:

Files (suggested)
- k8s/backend-deployment.yaml — Deployment using image `harshs3185/splitwiser-backend:latest` (containerPort 5000), envFrom secretRef `supabase-env`
- k8s/backend-service.yaml — Service (ClusterIP) named `backend` on port 5000
- k8s/frontend-deployment.yaml — Deployment using image `harshs3185/splitwiser-frontend:latest` (containerPort 80). In the basic manifest we used a startup sed that replaces `http://localhost:5000` → `http://backend:5000` in `/usr/share/nginx/html/app.js` then starts nginx.
- k8s/frontend-service.yaml — Service (NodePort) named `frontend` exposing port 80 via nodePort `30080`
- Secret is created from your backend/.env (not stored in YAML unless you want it encoded there).

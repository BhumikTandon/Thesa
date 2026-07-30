# Thesa

A rewards-neutral spend management platform for field workforces — construction crews, home services, restaurants, film production, and trucking. Employees get scoped virtual cards in seconds at the point of sale; finance teams get spend routed across **all** their corporate cards for maximum rewards, not locked into one issuer's interchange.

## Why Thesa

Incumbent spend platforms (Ramp, Brex) monetize interchange on their own card — so they will never tell you to put your fuel spend on the card that earns 4x on gas. Thesa is issuer-neutral:

1. **Reward Router** (flagship) — analyzes recurring vendor spend and routes each purchase to whichever of the company's cards earns the highest multiplier. We charge a percentage of the rewards value we create, not interchange.
2. **Built for the field, not the desk** — the primary user is a crew lead at a merchant counter, not a finance manager at a dashboard. Scoped card issuance, per diem tracking, and receipt capture are all mobile-first.
3. **Database-enforced tenant isolation** — PostgreSQL Row-Level Security means the database is physically blind to other tenants' data.

## Architecture

| Layer | Stack |
|---|---|
| **Command Center** (Web) | React / Next.js |
| **Field Client** (Mobile) | Swift (iOS) |
| **Backend API** | Python / FastAPI |
| **Database** | PostgreSQL with Row-Level Security |
| **Card Issuing** | Marqeta (JIT funding) |
| **Auth** | Clerk |

### How Tenant Isolation Works

Every API request goes through Clerk auth middleware, which extracts the `company_id` from the session token. Before any database query executes, the backend runs:

```sql
SET LOCAL app.current_tenant = :tenant_id
```

PostgreSQL RLS policies evaluate this session variable to filter rows. The database is physically blind to other tenants' data — no application-layer `WHERE` clauses needed.

## What's Built

- [x] **FastAPI server** — health check, identity endpoint, and full CRUD APIs for the features below
- [x] **Clerk authentication middleware** — verifies session tokens via `clerk-backend-api`; tenancy and role are resolved from the **database** (not JWT metadata), so membership changes take effect immediately
- [x] **PostgreSQL schema** — companies, users, invites, portfolio cards, reward rules, budgets, per diems, transactions, routing decisions, spend policies, issued cards, authorization decisions, webhook events, audit log
- [x] **RLS on every tenant table** — `FORCE ROW LEVEL SECURITY`, fail-closed policies (no tenant context = zero rows), non-superuser `thesa_app` runtime role
- [x] **Immutable audit trail** — trigger-based `audit_log` capturing every budget/limit/card/routing change with actor attribution; append-only enforced by trigger
- [x] **Reward Router engine** — vendor spend aggregation, keyword merchant classifier, best-card recommendation with server-side uplift math, decision recording, rewards ledger
- [x] **Budgets & per diems** — job-site budgets with month-to-date spend tracking; per-employee daily allowances with remaining-today view
- [x] **Transactions** — manual entry (auto-categorized) and listing; seeds the Reward Router until the card feed lands
- [x] **Role-based access** — owner / office_manager / crew_lead with per-endpoint enforcement
- [x] **Security middleware** — security headers on every response, tiered rate limiting (per-user, per-IP, tighter on money-adjacent writes) with 429 + Retry-After
- [x] **Onboarding & team** — atomic company + owner creation; email invites with roles, revocation, and join flow (invitee's email verified server-side with Clerk, never client-supplied)
- [x] **Isolation verification** — `backend/db/verify_isolation.py` actively attempts cross-tenant reads/writes and audit tampering as the non-superuser role
- [x] **API flow verification** — `backend/verify_api_flows.py` runs 50 end-to-end HTTP checks across every feature with only the Clerk network boundary faked
- [x] **Command Center (web)** — Next.js 16 dashboard in `frontend/`: Clerk sign-in, onboarding (create company / join via invite), overview, Reward Router (recommendations, accept/dismiss, ledger), transactions, budgets, card portfolio, and team pages with role-aware UI
- [x] **CORS allowlist** — explicit single-origin allowlist on the API, bearer-token only (no cookies/credentials)
- [x] **Card Teller & issued cards** — scoped virtual card provisioning (stub issuer), spend policies, JIT webhook with HMAC + replay protection, fail-closed authorize/decline loop (status → expiry → limit → vendor/category → policy → budget → per diem)
- [x] **Configuration & workspace rules** — Pydantic settings, `.cursor/rules/` conventions

## What's Next

### Card Issuing — Marqeta (real issuer)
- [ ] Swap `issuing_stub` for Marqeta JIT funding (same Card Teller + webhook contract)
- [ ] Mutual TLS / IP allowlisting at the edge for webhook traffic
- [ ] Field card provisioning UX polish + physical card lifecycle
- [ ] Command Center issuance controls UI (API ready)

### Infrastructure
- [ ] Alembic migrations (replace create_all bootstrap)
- [ ] Redis-backed rate limiting for multi-replica deployments
- [ ] CI/CD pipeline — `bandit` for static analysis, `safety` for dependency scanning, `pytest` on every commit

### Receipt & Expense Automation
- [ ] Mobile receipt capture — photo upload from iOS app matched to transactions at the point of sale
- [ ] Zero-touch receipt parsing — Gmail API OAuth integration (minimum scope) to scan for fuel/lodging/supplier receipts
- [ ] Background worker to extract PDF receipts, parse totals, and match to transactions

### Command Center (Web)
- [x] Next.js dashboard for owners, office managers, and finance leads
- [x] Reward Router insights — rewards earned vs. baseline, routing recommendations awaiting approval
- [x] Company-wide transaction log viewer
- [x] Crew and job-level budget management (e.g., "$10,000/mo for the Henderson job site")
- [ ] Card issuance and limit controls UI (API ready; blocked on Marqeta swap for production)
- [ ] Flagged out-of-policy transaction review UI (authorization decisions API ready)

### Field Client (iOS)
- [ ] Scoped card request flow — crew lead picks a vendor, gets a funded card in seconds
- [ ] Per diem and job budget remaining views
- [ ] Receipt photo capture and upload at the counter

### Testing & Security
- [x] Tenant isolation verification — `verify_isolation.py` actively attempts cross-tenant data access (migrate to pytest with CI)
- [x] Webhook signature + replay + Card Teller decision checks in `verify_api_flows.py`
- [ ] Policy engine edge-case suite as pytest
- [ ] Reward Router regression tests — routing recommendations against known card portfolios

## Development

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Set environment variables (or use .env)
export CLERK_SECRET_KEY="sk_test_..."
# Runtime role: non-superuser so RLS binds
export DATABASE_URL="postgresql+asyncpg://thesa_app@localhost:5432/thesa"
# Privileged role for schema bootstrap only
export DATABASE_ADMIN_URL="postgresql+asyncpg://$(whoami)@localhost:5432/thesa"

# Create the database, apply schema + RLS + audit triggers + grants
createdb thesa
python -m backend.db.bootstrap

# Verify tenant isolation and audit immutability
python -m backend.db.verify_isolation

# Run the API server
uvicorn backend.main:app --reload

# Run the Command Center (separate terminal)
cd frontend
npm install
npm run dev   # http://localhost:3000, expects the API on :8000
```

The frontend reads `frontend/.env.local` for the Clerk publishable/secret keys and `NEXT_PUBLIC_API_URL`.

## Security

Thesa targets fintech-grade security: PCI-scope avoidance by design (issuer holds all PANs), PostgreSQL RLS with fail-closed policies, short-lived Clerk JWTs, webhook signature + replay protection, tiered rate limiting, and an immutable trigger-based audit log. Encryption at rest with KMS-managed keys is required before production (see [DOCUMENTATION.md § Security Standard](DOCUMENTATION.md#security-standard)).

## Project Rules

Workspace rules in `.cursor/rules/` enforce:

- **Zero-trust security** — all input assumed malicious, parameterized queries only, no raw PANs
- **Database-level tenant isolation** — RLS via `SET LOCAL`, never application-layer filtering
- **Audit logging** — every budget/limit/card status change recorded immutably
- **Dependency vetting** — no new third-party packages without explicit approval
- **Card issuing safety** — webhook events mapped to internal audit trail, no sensitive payloads logged

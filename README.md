# Thesa

A B2B expense management platform with JIT card funding, automated receipt parsing, and database-enforced tenant isolation.

## Architecture

| Layer | Stack |
|---|---|
| **Command Center** (Web) | React / Next.js |
| **Point-of-Sale Client** (Mobile) | Swift (iOS) |
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

- [x] **FastAPI server** — app entry point with health check and example authenticated endpoint
- [x] **Clerk authentication middleware** — verifies session tokens via `clerk-backend-api`, extracts `company_id` from public metadata, rejects unauthenticated/unauthorized requests
- [x] **RLS-aware database sessions** — SQLAlchemy async dependency that injects tenant context (`SET LOCAL`) before yielding
- [x] **Configuration** — Pydantic settings loading Clerk secret key and database URL from environment
- [x] **Workspace rules** — `.cursor/rules/` enforcing security, RLS, and card issuing conventions

## What's Next

### Infrastructure & Database
- [ ] PostgreSQL schema — companies, users, cards, transactions, budgets, audit log tables
- [ ] RLS policies on all tenant-scoped tables
- [ ] Immutable audit trail — trigger-based `audit_log` table that captures every budget/card/limit change with actor and timestamp
- [ ] Wire `company_id` lookup from database (replace public metadata extraction)
- [ ] CI/CD pipeline — `bandit` for static analysis, `safety` for dependency scanning, `pytest` on every commit

### Card Issuing & Policy Engine
- [ ] Marqeta integration — JIT funding webhook receiver
- [ ] **Card Teller policy engine** — the 2-second decision loop: vendor approval, budget check, policy evaluation, approve/decline response
- [ ] Virtual card provisioning — employee requests a card scoped to a vendor/category
- [ ] Physical card issuance and lifecycle management
- [ ] Reward optimization routing — recommend which corporate card to route recurring vendor spend to for maximum multiplier categories

### Receipt & Expense Automation
- [ ] Zero-touch receipt parsing — Gmail API OAuth integration (minimum scope) to scan for airline/hotel receipts
- [ ] Background worker to extract PDF receipts, parse totals, and match to transactions
- [ ] Mobile receipt capture — photo upload from iOS app matched to transactions

### Command Center (Web)
- [ ] Next.js dashboard for finance managers and company admins
- [ ] Company-wide transaction log viewer
- [ ] Departmental budget management (e.g., "$10,000/mo for Marketing")
- [ ] Card issuance and limit controls
- [ ] Flagged out-of-policy transaction review

### Point-of-Sale Client (iOS)
- [ ] Virtual card request flow — employee picks a vendor, gets a scoped card
- [ ] Per diem and budget remaining views
- [ ] Receipt photo capture and upload

### Testing & Security
- [ ] Tenant isolation test suite — Pytest cases that actively attempt cross-tenant data access
- [ ] Webhook signature verification tests
- [ ] Policy engine decision tests (approve, decline, flag edge cases)

## Development

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Set environment variables (or use .env)
export CLERK_SECRET_KEY="sk_test_..."
export DATABASE_URL="postgresql+asyncpg://localhost:5432/thesa"

# Run the server
uvicorn backend.main:app --reload
```

## Project Rules

Workspace rules in `.cursor/rules/` enforce:

- **Zero-trust security** — all input assumed malicious, parameterized queries only, no raw PANs
- **Database-level tenant isolation** — RLS via `SET LOCAL`, never application-layer filtering
- **Audit logging** — every budget/limit/card status change recorded immutably
- **Dependency vetting** — no new third-party packages without explicit approval
- **Card issuing safety** — webhook events mapped to internal audit trail, no sensitive payloads logged

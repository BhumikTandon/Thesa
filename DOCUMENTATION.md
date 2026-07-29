# Thesa — Project Documentation

> A rewards-neutral spend management platform for field workforces, with just-in-time scoped cards, reward-optimized spend routing, and database-enforced tenant isolation.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Positioning & Differentiators](#positioning--differentiators)
3. [Architecture](#architecture)
4. [Tech Stack](#tech-stack)
5. [Directory Structure](#directory-structure)
6. [Components in Detail](#components-in-detail)
7. [API Endpoints](#api-endpoints)
8. [Authentication & Authorization](#authentication--authorization)
9. [Security Standard](#security-standard)
10. [Database & Tenant Isolation](#database--tenant-isolation)
11. [Configuration](#configuration)
12. [Third-Party Integrations](#third-party-integrations)
13. [Developer Utilities](#developer-utilities)
14. [Current Status](#current-status)
15. [Roadmap](#roadmap)

---

## Project Overview

Thesa is a B2B spend management platform built for **field-workforce industries** — construction, home services, restaurants, film production, trucking — where the primary user is a crew lead at a merchant counter, not a finance manager at a dashboard.

Core capabilities:

- **Reward Router (flagship)** — routes each recurring vendor's spend to whichever of the company's corporate cards earns the highest reward multiplier. Because Thesa doesn't monetize its own card's interchange, it can optimize across the customer's entire card portfolio — something interchange-funded incumbents structurally cannot do.
- **Just-In-Time (JIT) scoped cards** — a crew lead picks a vendor and gets a funded, scoped virtual card in seconds, via Marqeta JIT funding
- **Card Teller policy engine** — a 2-second decision loop evaluating vendor approval, budget, per diem, and policy rules to approve or decline each authorization
- **Mobile-first receipt capture** — photo capture at the point of sale, plus Gmail/PDF parsing for emailed receipts
- **Database-enforced multi-tenant isolation** — PostgreSQL Row-Level Security (RLS) ensures tenants cannot access each other's data at the database layer
- **Command Center** — a web dashboard for owners and office managers covering budgets, cards, routing insights, and flagged transactions

**Business model:** Thesa charges a percentage of the rewards value created by the Reward Router, rather than competing on interchange with free incumbent platforms.

**Repository:** https://github.com/BhumikTandon/Thesa.git

---

## Positioning & Differentiators

| | Incumbents (Ramp, Brex) | Thesa |
|---|---|---|
| Primary user | Finance team at a dashboard | Crew lead at a merchant counter |
| Card strategy | Their card only (interchange revenue) | Issuer-neutral, optimizes across all the company's cards |
| Rewards | Flat cashback on their card | Routes spend to the highest-multiplier card in the portfolio |
| Target segment | Tech startups, mid-market SaaS | Field workforces: construction, home services, restaurants, film, trucking |
| Monetization | Interchange (product is free) | Take rate on rewards value created |

The structural moat: incumbents monetize their own card's interchange, so recommending a customer route spend to a *different* card cannibalizes their revenue. A rewards-neutral router has no such conflict.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Clients                              │
│   Next.js Command Center  │  iOS Field Client  │ Dev Token UI│
└─────────────────────────┬───────────────────────────────────┘
                          │ Authorization: Bearer <Clerk JWT>
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI Backend (backend/main.py)                           │
│    └── AuthMiddleware (backend/auth/middleware.py)           │
│          • Verifies Clerk session token                      │
│          • Extracts company_id + user_id from JWT            │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
   Public Routes                   Protected Routes
   /health, /docs                  e.g. GET /me
                                         │
                                         ▼
                          get_tenant_session (backend/db/session.py)
                            • SET LOCAL app.current_tenant = :tenant_id
                            • Yields AsyncSession
                                         ▼
                          PostgreSQL (RLS policies filter by tenant)
```

### Design Principles

| Principle | Implementation |
|-----------|---------------|
| Zero-trust input handling | Parameterized queries only; all input assumed malicious |
| Database-level isolation | RLS via `SET LOCAL`, never application-layer `WHERE` clauses |
| Immutable audit trail | Every budget/limit/card/routing change recorded (planned) |
| No raw sensitive data | Network tokens instead of raw PANs |
| Issuer neutrality | Reward Router optimizes across the customer's full card portfolio |

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.x |
| Web Framework | FastAPI | 0.115.6 |
| ASGI Server | Uvicorn | 0.34.0 |
| ORM | SQLAlchemy (async) | 2.0.44 |
| DB Driver | asyncpg | 0.30.0 |
| Configuration | pydantic-settings | 2.7.1 |
| Authentication | Clerk (clerk-backend-api) | 6.0.1 |
| Database | PostgreSQL with Row-Level Security | — |

### Planned additions

| Layer | Technology |
|-------|-----------|
| Card Issuing | Marqeta (JIT funding) |
| Web UI | React / Next.js |
| Mobile | Swift (iOS) |
| Receipt Parsing | Gmail API |
| Testing | pytest, bandit, safety |

---

## Directory Structure

```
Thesa/
├── .cursor/rules/               # AI workspace rules for security & conventions
│   ├── card-issuing.mdc         # Card issuing safety conventions
│   ├── global-security.mdc      # Zero-trust security rules
│   └── python-backend.mdc       # Python/FastAPI coding standards
├── .env                         # Local secrets (gitignored)
├── .gitignore                   # Ignores .env, __pycache__/, *.pyc, venv/
├── README.md                    # Project overview and roadmap
├── DOCUMENTATION.md             # This file
├── get-token.html               # Dev utility — Clerk sign-in to get bearer tokens
└── backend/
    ├── __init__.py              # Package marker
    ├── main.py                  # FastAPI app: middleware stack + router registration
    ├── config.py                # Pydantic settings (runtime + admin DB URLs, Clerk key)
    ├── models.py                # SQLAlchemy ORM models (9 tables)
    ├── schemas.py               # Pydantic request/response schemas (extra=forbid)
    ├── deps.py                  # Role-based access dependency (require_role)
    ├── security.py              # Security headers + tiered rate limiting middleware
    ├── requirements.txt         # Pinned Python dependencies
    ├── auth/
    │   └── middleware.py        # Clerk JWT verification + DB-backed tenancy/roles
    ├── db/
    │   ├── session.py           # Tenant-scoped sessions (set_config for RLS + audit actor)
    │   ├── rls.sql              # RLS policies, audit triggers, auth functions
    │   ├── grants.sql           # Least-privilege thesa_app role grants
    │   ├── bootstrap.py         # Apply schema + rls.sql + grants.sql
    │   └── verify_isolation.py  # Active cross-tenant attack verification
    ├── services/
    │   ├── vendor_classifier.py # Keyword merchant → category classifier
    │   └── reward_router.py     # Reward Router engine (flagship)
    └── routes/
        ├── onboarding.py        # POST /onboarding
        ├── portfolio.py         # /portfolio-cards
        ├── budgets.py           # /budgets
        ├── per_diems.py         # /per-diems
        ├── transactions.py      # /transactions
        └── routing.py           # /routing (recommendations, decisions, ledger)
```

---

## Components in Detail

### `backend/main.py` — Application Entry Point

The FastAPI application is created here with:
- App title set to "Thesa" with Swagger docs at `/docs`
- Middleware stack (execution order): `SecurityHeadersMiddleware` → `AuthMiddleware` → `RateLimitMiddleware` → routes, so headers are stamped on every response and rate limiting keys on the resolved identity
- Routers for onboarding, portfolio, budgets, per diems, transactions, and routing, plus `/health` and `/me`

### `backend/auth/middleware.py` — Clerk Authentication Middleware

Handles all authentication logic:
1. Intercepts every incoming request before it reaches route handlers
2. Bypasses auth for public paths: `/health`, `/docs`, `/openapi.json`, `/redoc`
3. For protected paths:
   - Extracts `Authorization: Bearer <token>` header
   - Validates the token via Clerk SDK's `authenticate_request()`
   - Resolves the `sub` claim to a Thesa user via the database (`resolve_user` function) — user UUID, company UUID, and role
   - Stores identity on `request.state`; users with no company may only reach `/onboarding`

**Error responses:**
- `401 Unauthorized` — missing/invalid header or Clerk validation failure
- `403 Forbidden` — authenticated but not a member of any company (outside `/onboarding`), or insufficient role for the endpoint

### `backend/db/session.py` — Tenant-Scoped Database Sessions

Manages the async database connection pool and tenant isolation:
- Creates a lazy singleton `AsyncEngine` with `pool_size=20`, `max_overflow=5`, `pool_pre_ping=True`
- Exposes `get_tenant_session` as a FastAPI dependency that:
  1. Reads `company_id` from `request.state`
  2. Executes `SET LOCAL app.current_tenant = :tenant_id` (parameterized)
  3. Yields an `AsyncSession` for the route handler
  4. Commits on success, rolls back on exception

This ensures PostgreSQL RLS policies automatically filter all queries to the authenticated tenant's data.

### `backend/config.py` — Application Configuration

Uses Pydantic's `BaseSettings` to load configuration from environment variables and `.env`:

| Variable | Required | Default |
|----------|----------|---------|
| `CLERK_SECRET_KEY` | Yes | — |
| `DATABASE_URL` | No | `postgresql+asyncpg://thesa_app@localhost:5432/thesa` (non-superuser so RLS binds) |
| `DATABASE_ADMIN_URL` | For bootstrap | Falls back to `DATABASE_URL`; privileged role for schema changes only |

---

## API Endpoints

All authenticated endpoints require a valid Clerk bearer token; tenancy and role come from the database. Roles: **any** = any company member, **mgr** = owner or office_manager.

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `GET` | `/health` | public | Health check |
| `POST` | `/onboarding` | authed, no company yet | Create company + owner atomically |
| `GET` | `/me` | any | Caller's identity and role (DB-resolved) |
| `GET` | `/portfolio-cards` | any | List the company's cards with reward rules |
| `POST` | `/portfolio-cards` | mgr | Register an existing corporate card (+ category earn rates) |
| `PATCH` | `/portfolio-cards/{id}` | mgr | Activate/deactivate a card |
| `GET` | `/budgets` | any | List budgets with month-to-date spend and remaining |
| `POST` | `/budgets` | mgr | Create a job-site/departmental budget |
| `PATCH` | `/budgets/{id}` | mgr | Change limit or active state (audited) |
| `GET` | `/per-diems` | mgr | List per diems |
| `POST` | `/per-diems` | mgr | Assign a daily allowance to an employee |
| `GET` | `/per-diems/me` | any | Caller's remaining allowance for today |
| `GET` | `/transactions` | any | List transactions (paginated) |
| `POST` | `/transactions` | any | Record a purchase (category auto-classified) |
| `GET` | `/routing/recommendations` | mgr | Reward Router: positive-uplift routing recommendations |
| `POST` | `/routing/decisions` | mgr | Accept/dismiss a recommendation (figures recomputed server-side) |
| `GET` | `/routing/decisions` | mgr | Decision history |
| `GET` | `/routing/ledger` | mgr | Rewards ledger: accepted decisions and estimated uplift |
| `GET` | `/docs`, `/redoc`, `/openapi.json` | public | API documentation (auto-generated) |

---

## Authentication & Authorization

### Authentication Flow (Clerk)

```
Client → sends Bearer token in Authorization header
  ↓
AuthMiddleware → validates token via Clerk SDK
  ↓
On success → resolves sub claim against the users table (resolve_user)
  ↓
Stores user_id, company_id, role on request.state → available to routes
```

### Authorization Model

- **Authenticated** = valid Clerk session token
- **Authorized** = user row exists in the database (JWT metadata is not trusted)
- **Role-enforced** = owner / office_manager / crew_lead checked per endpoint (`backend/deps.py`)
- **Tenant-scoped** = all DB queries automatically filtered by RLS
- **Rate-limited** = per-user and per-IP sliding windows (`backend/security.py`)

Not yet implemented:
- Per-resource permission checks beyond roles
- Step-up re-auth for sensitive actions

---

## Security Standard

This section defines the security bar Thesa is built to. Because Thesa moves company money and issues cards, the target is fintech-grade: PCI DSS-aligned card handling, SOC 2-ready controls, and OWASP ASVS Level 2 as a baseline. Each control below is marked **Implemented** (in the current codebase) or **Required** (must be in place before production launch — treat these as blocking).

### 1. Security Principles

| Principle | Meaning in practice |
|---|---|
| Zero trust | All input is assumed malicious; every request is authenticated and tenant-scoped |
| Least privilege | Each role, service, and DB credential gets the minimum access it needs |
| Defense in depth | Isolation enforced at the database (RLS), not just the app layer |
| Secure by default | New endpoints are authenticated unless explicitly added to the public allowlist |
| No sensitive data at rest | Raw PANs, CVVs, and full webhook payloads are never stored or logged |

### 2. Token & Session Security

| Control | Status | Detail |
|---|---|---|
| Short-lived access tokens | Implemented | Clerk session JWTs expire in ~60 seconds and are silently refreshed by the client SDK; a stolen token has a very small usable window |
| Signature verification via JWKS | Implemented | Clerk SDK validates the RS256 signature against Clerk's published JWKS; no shared-secret (HS256) verification anywhere |
| Claim validation | Implemented | `sub` is required and must resolve to a database user; unresolved users are rejected with 403 (except `/onboarding`) |
| `azp` / authorized-party check | Required | Configure the Clerk SDK's `authorized_parties` allowlist so tokens minted for another origin are rejected |
| Server-side revocation | Required | On employee offboarding or suspected compromise, revoke the Clerk session (not just the JWT) so refresh stops immediately |
| Tenant claim from database | Implemented | Tenancy and role are resolved per-request from the `users` table via the `resolve_user` function; JWT public metadata is no longer trusted, so membership changes take effect immediately |
| Bearer-token hygiene | Required | Tokens never appear in URLs, query strings, or logs; the `Authorization` header is excluded from access-log capture |
| Step-up auth for sensitive actions | Required | Card issuance, limit changes, and routing-rule changes require a recent (< 5 min) re-verification via Clerk before the API accepts them |

### 3. Cookie Policy

The API itself is bearer-token only and sets no cookies. Cookies exist only in the Next.js Command Center (Clerk session cookies) and must follow:

| Attribute | Requirement |
|---|---|
| `HttpOnly` | Always — session cookies are never readable from JavaScript |
| `Secure` | Always — cookies are never sent over plaintext HTTP |
| `SameSite` | `Lax` minimum; `Strict` for any cookie involved in state-changing flows |
| `__Host-` prefix | Use for first-party session cookies (forces `Secure`, no `Domain`, `Path=/`) |
| Scope | No cookies on the API domain; API auth is exclusively `Authorization: Bearer` |
| CSRF | Bearer-token APIs are not CSRF-exposed, but any future cookie-authenticated route must add CSRF tokens (double-submit or synchronizer pattern) before shipping |

### 4. Transport Security

| Control | Status | Detail |
|---|---|---|
| TLS 1.2+ everywhere, TLS 1.3 preferred | Required | Terminate at the load balancer; disable legacy ciphers |
| HSTS | Required | `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload` |
| HTTP → HTTPS redirect | Required | No API or web endpoint reachable over plaintext |
| Certificate pinning (iOS) | Required | The field client pins the API's certificate/public key; a MITM proxy at a job-site Wi-Fi network must not be able to intercept card requests |
| Internal traffic encryption | Required | Backend ↔ PostgreSQL over TLS (`sslmode=verify-full`); no plaintext DB connections even inside the VPC |

### 5. Security Headers (API and Web)

All responses must carry, via middleware:

```
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Cache-Control: no-store            (on all authenticated API responses)
Content-Security-Policy: default-src 'self'; frame-ancestors 'none'   (web; tightened per-page)
Permissions-Policy: camera=(), geolocation=(), microphone=()          (web; camera allowed only on receipt-capture routes)
```

Status: **Implemented** for the API (`backend/security.py`, `SecurityHeadersMiddleware`): HSTS, nosniff, frame denial, referrer and permissions policies on every response, `Cache-Control: no-store` on authenticated responses. CORS allowlisting and the web CSP land with the Command Center.

### 6. Rate Limiting & Abuse Prevention

Status: **Implemented (single instance)** — `RateLimitMiddleware` in `backend/security.py` enforces sliding-window limits: 300/min per IP (unauthenticated), 60/min per user, 30/min per user on money-adjacent writes (portfolio, budgets, per diems, routing), with `429` + `Retry-After`. The store is in-process; move it to Redis before running multiple API replicas. Remaining targets:

| Layer | Policy |
|---|---|
| Global per-IP | Baseline sliding-window limit at the edge (e.g. 300 req/min) to blunt scraping and floods |
| Per-user | Authenticated limit keyed on `user_id` (e.g. 60 req/min) so one stolen token can't hammer the API |
| Per-tenant | Aggregate limit keyed on `company_id` so a runaway integration in one company can't degrade others (multi-tenant fairness) |
| Sensitive endpoints | Much tighter limits on card issuance, limit changes, and token-adjacent routes (e.g. 5/min per user) with alerting on breach |
| Auth endpoints | Brute-force protection is delegated to Clerk (lockouts, bot detection) — verify it is enabled in the Clerk dashboard |
| Webhook receiver | Rate-limited per source with signature check *before* any parsing work, so forged floods are cheap to reject |
| Response behavior | `429` with `Retry-After`; limits enforced in Redis (sliding window) so they hold across API replicas |
| Cost controls | Per-tenant daily caps on expensive operations (receipt OCR, Gmail scans) to bound spend from abuse |

### 7. Data Protection & Encryption

| Control | Status | Detail |
|---|---|---|
| Encryption at rest | Required | AES-256 for the PostgreSQL volume and all backups; keys held in a KMS, never in app config |
| Field-level encryption | Required | Extra-sensitive columns (card metadata beyond last4, bank account references, Gmail OAuth refresh tokens) encrypted at the application layer with KMS-managed data keys, so a DB dump alone is not enough to read them |
| Key rotation | Required | Annual KMS key rotation minimum; immediate rotation on any suspected exposure |
| Data minimization | Required | Store only what the product needs: card last4 + network token, never full PAN/CVV/track data (see §8); receipt images retain totals and merchant, strip anything else |
| Retention & deletion | Required | Defined retention per data class (transactions: 7 years for audit; receipt images: configurable per tenant; logs: 90 days). Hard-delete pipelines for GDPR/CCPA erasure requests, with the immutable audit log retained as the lawful exception |
| Backups | Required | Encrypted, access-restricted, restore-tested quarterly; backups inherit the same RLS-bearing schema |
| PII in logs | Required | Structured logging with an explicit allowlist of fields; tokens, PANs, email bodies, and full webhook payloads are never logged (the card-issuing rule already mandates this) |

### 8. Card Data Handling (PCI DSS Scope)

The architecture is deliberately designed to keep Thesa **out of PCI DSS scope for PAN storage**:

- Marqeta is the issuer of record and holds all primary account numbers. Thesa stores only Marqeta card tokens, last4, expiry, and state.
- Raw PANs, CVVs, and magnetic-stripe/track data never transit or rest in Thesa systems. If a card number must be shown to a user (e.g. virtual card reveal in the iOS app), it is rendered via Marqeta's client-side widget/iframe so the PAN never touches Thesa's backend.
- Webhook payloads from Marqeta may contain sensitive fields — they are processed in memory, mapped to internal event records, and never persisted or logged raw.
- Target compliance posture: PCI DSS SAQ-A-equivalent footprint, validated annually.

### 9. Webhook Security (Marqeta JIT Funding)

The JIT funding webhook is the highest-value attack surface: a forged "approve" is stolen money. Requirements before the receiver ships:

1. **Signature verification first** — HMAC verification with constant-time comparison happens before JSON parsing or any DB access; unsigned or mis-signed requests get a 401 and a metric, nothing else.
2. **Replay protection** — reject events with timestamps outside a ±5 minute window; store processed event IDs and drop duplicates (idempotency).
3. **Mutual TLS or IP allowlisting** — accept webhook traffic only from Marqeta's published ranges at the edge.
4. **Fail closed** — if the policy engine cannot reach the database or exceeds its decision deadline, the authorization is *declined*, never defaulted to approve.
5. **Separate credentials** — the webhook path runs with a DB role that can write authorization decisions and audit rows but cannot read other tenants' data or mutate budgets.

### 10. Tenant Isolation Guarantees

| Control | Status | Detail |
|---|---|---|
| RLS session variable | Implemented | `set_config('app.current_tenant', ..., true)` (transaction-local, parameterized) plus `app.current_user` for audit attribution |
| RLS policies on every tenant table | Implemented | `FORCE ROW LEVEL SECURITY` on all tenant-scoped tables (`backend/db/rls.sql`) so even the table owner cannot bypass policies |
| Non-superuser app role | Implemented | The application connects as `thesa_app` (no `BYPASSRLS`, least-privilege grants in `backend/db/grants.sql`); bootstrap uses the separate `DATABASE_ADMIN_URL` role |
| Fail-closed default | Implemented | Policies compare against `NULLIF(current_setting(...), '')`, so an unset tenant matches zero rows — verified by `verify_isolation.py` |
| Cross-tenant test suite | Implemented (script) | `backend/db/verify_isolation.py` authenticates as tenant A and actively attempts to read/write tenant B's data as the non-superuser role; migrate to pytest in CI |

### 11. Input Validation & Injection Defense

- All request bodies validated by Pydantic models with strict types; unknown fields rejected (`extra="forbid"`), string lengths and numeric ranges bounded.
- SQL exclusively through SQLAlchemy with bound parameters — string-built SQL is banned and flagged in review (per workspace rule).
- UUIDs parsed with the `uuid` module before use (already done for `company_id`).
- File uploads (receipt images): content-type sniffed server-side, size-capped, image bytes re-encoded before storage, EXIF stripped, never served back from the API origin.
- Monetary values as integer cents, never floats.

### 12. Secrets Management

| Control | Status | Detail |
|---|---|---|
| No secrets in the repo | Implemented | `.env` is gitignored; `config.py` reads from the environment |
| Secrets manager in production | Required | Clerk secret key, DB credentials, Marqeta keys, and webhook HMAC secrets live in a secrets manager (AWS Secrets Manager / Vault) with rotation; never in env files on disk |
| Rotation on exposure | Required | Documented runbook: rotate Clerk secret, Marqeta credentials, and DB password within 1 hour of suspected leak |
| Dev-tool hygiene | Required | `get-token.html` contains a test publishable key and pre-filled email — acceptable only for `pk_test_` keys; it must never be deployed, and production publishable keys never appear in committed files |
| Per-environment isolation | Required | Test and production Clerk instances, Marqeta programs, and databases are fully separate; no shared credentials |

### 13. Audit Logging (Immutable)

Per the workspace security rule, every change to a budget, limit, card status, or routing rule must be recorded immutably:

- Trigger-based `audit_log` table written by PostgreSQL triggers, not application code, so no code path can skip it.
- Append-only: the application role has `INSERT` only — no `UPDATE`/`DELETE` grants; optionally shipped to WORM object storage for tamper evidence.
- Each row captures actor (`user_id`), tenant, action, before/after values, timestamp, and request ID for correlation with API logs.
- Audit reads are themselves tenant-scoped via RLS and restricted to admin roles.

Status: **Implemented** (`backend/db/rls.sql`): the `audit_row_change` trigger covers budgets, per diems, portfolio cards, reward rules, and routing decisions; a `BEFORE UPDATE OR DELETE` trigger raises on any mutation attempt, and the app role has no UPDATE/DELETE grants. Verified by `verify_isolation.py` (actor attribution and tamper rejection).

### 14. Dependency & Supply Chain Security

- All Python dependencies pinned to exact versions (already the case in `requirements.txt`); add hash-pinning (`--require-hashes`) before launch.
- `safety` (vulnerability scan) and `bandit` (static analysis) run in CI on every commit; builds fail on high-severity findings.
- New third-party packages require explicit human approval before addition (enforced by workspace rule).
- Dependabot/Renovate for patch alerts; SBOM generated per release.
- CI runners use short-lived, least-privilege credentials; no long-lived cloud keys in CI secrets.

### 15. Mobile Client Security (iOS)

- Tokens stored in the iOS Keychain (`kSecAttrAccessibleWhenUnlockedThisDeviceOnly`), never in `UserDefaults` or files.
- Certificate pinning against the API (see §4).
- Card reveal via Marqeta's SDK widget so PANs never enter app memory under Thesa's control; screenshots blocked on card-reveal screens.
- No sensitive data in app logs, crash reports, or analytics payloads.
- Biometric (Face ID) gate before card reveal or card-request submission.

### 16. Monitoring, Detection & Incident Response

- Structured, centralized logs with request IDs; security events (auth failures, 403s, rate-limit breaches, webhook signature failures) emitted as metrics.
- Alerts on anomalies: spike in declines for one tenant, webhook signature failure bursts, single token generating traffic from many IPs, RLS policy violations (which should be impossible and therefore page immediately).
- Documented incident response runbook: severity levels, on-call ownership, customer notification thresholds, and post-incident review within 5 business days.
- Quarterly access reviews of production, database, Clerk dashboard, and Marqeta program access.

### 17. Compliance Targets

| Framework | Posture |
|---|---|
| PCI DSS | Out-of-scope-by-design for PAN storage (SAQ-A-equivalent); validated annually |
| SOC 2 Type II | Controls above map to the Security and Confidentiality trust criteria; audit targeted post-launch |
| OWASP ASVS | Level 2 baseline for all application code; Level 3 for the webhook/authorization path |
| GDPR / CCPA | Data inventory, DPAs with Clerk/Marqeta/Google, erasure and export pipelines (§7 retention) |

### Pre-Launch Security Gate

The following are **blocking** for any production traffic. Done: RLS with fail-closed defaults and cross-tenant verification (§10), rate limiting (§6, single-instance), security headers (§5), immutable audit log (§13). Remaining: webhook signature + replay protection (§9, lands with Marqeta), TLS termination/HSTS at the edge (§4), secrets manager migration (§12), Redis rate-limit store for replicas (§6), and CI security scanning (§14).

---

## Database & Tenant Isolation

### How RLS Tenant Isolation Works

1. Every authenticated request has `company_id` extracted from the Clerk JWT
2. Before any query runs, the session executes:
   ```sql
   SET LOCAL app.current_tenant = :tenant_id
   ```
3. PostgreSQL RLS policies (to be defined) will reference `current_setting('app.current_tenant')` to filter rows
4. The database is physically blind to other tenants' data — no application-layer `WHERE` clauses needed

### Connection Pool Configuration

| Parameter | Value |
|-----------|-------|
| Pool size | 20 |
| Max overflow | 5 |
| Pool pre-ping | True |

### Schema (implemented in `backend/models.py`)

- `companies` — tenant organizations
- `users` — employees within companies (owner / office_manager / crew_lead), keyed to Clerk by `clerk_user_id`
- `portfolio_cards` — the company's existing corporate cards with default percent-back (input to the Reward Router)
- `reward_rules` — category-specific earn rates per portfolio card (e.g. fuel → 4%)
- `budgets` — job-site and departmental monthly spending limits (integer cents)
- `per_diems` — daily allowances for field employees
- `transactions` — purchase records, auto-categorized by the merchant classifier
- `routing_decisions` — Reward Router recommendations and outcomes; accepted rows form the rewards ledger for take-rate billing
- `audit_log` — immutable record of all changes to budgets, per diems, cards, reward rules, and routing decisions (trigger-written, append-only)

Schema, RLS policies (`backend/db/rls.sql`), and the least-privilege `thesa_app` role (`backend/db/grants.sql`) are applied by `python -m backend.db.bootstrap`. `backend/db/verify_isolation.py` verifies isolation and audit immutability against a live database.

A `cards` table for Thesa-issued cards arrives with the Marqeta integration.

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
CLERK_SECRET_KEY=sk_test_...
# Runtime role: non-superuser so RLS binds
DATABASE_URL=postgresql+asyncpg://thesa_app@localhost:5432/thesa
# Privileged role for schema bootstrap only
DATABASE_ADMIN_URL=postgresql+asyncpg://<local-superuser>@localhost:5432/thesa
```

### Running the Server

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Run with hot reload
uvicorn backend.main:app --reload
```

The server starts at `http://localhost:8000` with:
- Swagger UI at `/docs`
- ReDoc at `/redoc`

---

## Third-Party Integrations

### Active

| Service | Purpose | Files |
|---------|---------|-------|
| **Clerk** | JWT-based session authentication, user identity | `backend/auth/middleware.py`, `get-token.html` |
| **PostgreSQL** (asyncpg) | Async database with RLS tenant isolation | `backend/db/session.py` |

### Planned

| Service | Purpose |
|---------|---------|
| **Marqeta** | JIT card funding, virtual/physical card issuing, webhooks |
| **Gmail API** | OAuth-based receipt scanning from employee inboxes |

---

## Developer Utilities

### `get-token.html` — Clerk Token Helper

A standalone HTML page for local development that:
1. Loads Clerk JS from CDN
2. Provides email/password sign-in (with optional email 2FA support)
3. Retrieves and displays the Clerk session JWT
4. Allows copying the token for use in API testing (e.g., Postman, curl)

**Usage:** Open the file directly in a browser, sign in with test credentials, and copy the displayed token to use as `Authorization: Bearer <token>` in API requests.

---

## Current Status

### What's Built

| Component | Status | Description |
|-----------|--------|-------------|
| FastAPI server | Done | Health, identity, and full feature APIs (22 routes) |
| Clerk auth middleware | Done | JWT verification + database-backed tenancy and roles |
| PostgreSQL schema | Done | 9 tables in `backend/models.py`, applied by bootstrap |
| RLS policies | Done | FORCE RLS, fail-closed, on every tenant table |
| Non-superuser app role | Done | `thesa_app` with least-privilege grants |
| Immutable audit trail | Done | Trigger-written, append-only, actor-attributed |
| Reward Router engine | Done | Spend aggregation, classifier, recommendations, ledger |
| Budgets / per diems / transactions | Done | CRUD with month-to-date and remaining-today views |
| Role-based access | Done | owner / office_manager / crew_lead per endpoint |
| Security headers + rate limiting | Done | Per-user/IP sliding windows, tighter on sensitive writes |
| Onboarding | Done | Atomic company + owner via SECURITY DEFINER function |
| Isolation verification | Done | `verify_isolation.py` — 9 active attack checks, all passing |
| Configuration | Done | Pydantic settings; separate runtime/admin DB roles |
| Dev token helper | Done | Browser-based Clerk sign-in for testing |

### What's Not Built

| Component | Status |
|-----------|--------|
| Marqeta integration (JIT webhooks) | Deferred — next up |
| Card Teller policy engine | Deferred — next up |
| Thesa-issued card provisioning | Deferred — next up |
| Alembic migrations | Not started (bootstrap uses create_all) |
| Redis-backed rate limiting (multi-replica) | Not started |
| Receipt parsing workers | Not started |
| Next.js Command Center | Not started |
| iOS field client | Not started |
| pytest suite & CI/CD | Not started |
| Docker / deployment configs | Not started |

---

## Roadmap

### Phase 1 — Database Foundation (done, except migrations)
- [x] PostgreSQL schema (companies, users, portfolio_cards, reward_rules, transactions, budgets, per_diems, routing_decisions, audit_log)
- [x] RLS policies on all tenant-scoped tables (fail-closed, FORCE)
- [x] `company_id` lookup from database (public metadata extraction removed)
- [ ] Alembic migration setup (bootstrap currently uses create_all)

### Phase 2 — Reward Router (done; auto-routing awaits card issuing)
- [x] Card portfolio registration with reward multiplier categories
- [x] Vendor spend classification by merchant category (fuel, lodging, materials, food, travel)
- [x] Routing engine: recommend recurring vendor spend to the highest-multiplier card
- [x] Rewards ledger tracking value created per routing decision (billing basis)
- [ ] Automatic routing enforcement (requires Card Teller / issued cards)

### Phase 3 — Card Issuing & Policy Engine
- Marqeta JIT funding webhook receiver
- Card Teller policy engine (vendor approval → budget check → per diem check → policy eval → approve/decline)
- Field card provisioning (crew lead requests a scoped card, issued in seconds)
- Physical card lifecycle management

### Phase 4 — Receipt & Expense Automation
- Mobile receipt capture and upload at the point of sale
- Gmail API OAuth integration for receipt scanning
- Background worker for PDF extraction and transaction matching

### Phase 5 — Client Applications
- Next.js Command Center (Reward Router insights, transaction log, job-level budgets, card controls)
- iOS field client (scoped card requests, per diem and job budget views, receipt capture)

### Phase 6 — Testing & Hardening
- Tenant isolation test suite (cross-tenant access attempts)
- Webhook signature verification tests
- Policy engine decision tests
- Reward Router regression tests against known card portfolios
- CI/CD pipeline (bandit, safety, pytest)

---

*Last updated: July 28, 2026*

# Thesa — Project Documentation

> A B2B expense management platform with JIT card funding, automated receipt parsing, and database-enforced tenant isolation.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Directory Structure](#directory-structure)
5. [Components in Detail](#components-in-detail)
6. [API Endpoints](#api-endpoints)
7. [Authentication & Authorization](#authentication--authorization)
8. [Database & Tenant Isolation](#database--tenant-isolation)
9. [Configuration](#configuration)
10. [Third-Party Integrations](#third-party-integrations)
11. [Developer Utilities](#developer-utilities)
12. [Current Status](#current-status)
13. [Roadmap](#roadmap)

---

## Project Overview

Thesa is a B2B expense management platform targeting companies that need:

- **Just-In-Time (JIT) card funding** — cards are funded at the moment of purchase via Marqeta
- **Automated receipt parsing** — Gmail API scanning, PDF extraction, and mobile photo capture
- **Database-enforced multi-tenant isolation** — PostgreSQL Row-Level Security (RLS) ensures tenants cannot access each other's data at the database layer, not just the application layer
- **Policy engine (Card Teller)** — a 2-second decision loop that evaluates vendor approval, budget checks, and policy rules to approve or decline transactions
- **Command Center** — a web dashboard for finance managers to manage budgets, cards, and flagged transactions
- **iOS POS Client** — a mobile app for employees to request virtual cards and capture receipts

**Repository:** https://github.com/BhumikTandon/Thesa.git

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Clients                              │
│   Next.js Command Center  │  iOS Swift POS  │  Dev Token UI │
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
| Immutable audit trail | Every budget/limit/card change recorded (planned) |
| No raw sensitive data | Network tokens instead of raw PANs |

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.x |
| Web Framework | FastAPI | 0.115.6 |
| ASGI Server | Uvicorn | 0.34.0 |
| ORM | SQLAlchemy (async) | 2.0.36 |
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
    ├── main.py                  # FastAPI app entry point, route definitions
    ├── config.py                # Pydantic settings (env vars)
    ├── requirements.txt         # Pinned Python dependencies
    ├── auth/
    │   ├── __init__.py          # Package marker
    │   └── middleware.py        # Clerk JWT verification middleware
    └── db/
        ├── __init__.py          # Package marker
        └── session.py           # Async SQLAlchemy engine + tenant-scoped sessions
```

---

## Components in Detail

### `backend/main.py` — Application Entry Point

The FastAPI application is created here with:
- App title set to "Thesa" with Swagger docs at `/docs`
- Global registration of `AuthMiddleware`
- Two route definitions: `/health` (public) and `/me` (authenticated)

### `backend/auth/middleware.py` — Clerk Authentication Middleware

Handles all authentication logic:
1. Intercepts every incoming request before it reaches route handlers
2. Bypasses auth for public paths: `/health`, `/docs`, `/openapi.json`, `/redoc`
3. For protected paths:
   - Extracts `Authorization: Bearer <token>` header
   - Validates the token via Clerk SDK's `authenticate_request()`
   - Reads `company_id` from the JWT's `public_metadata` (must be a valid UUID)
   - Reads `user_id` from the `sub` claim
   - Stores both on `request.state` for downstream use

**Error responses:**
- `401 Unauthorized` — missing/invalid header or Clerk validation failure
- `403 Forbidden` — missing or invalid `company_id` in token metadata

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
| `DATABASE_URL` | No | `postgresql+asyncpg://localhost:5432/thesa` |

---

## API Endpoints

| Method | Path | Auth Required | Description | Response |
|--------|------|---------------|-------------|----------|
| `GET` | `/health` | No | Health check | `{"status": "ok"}` |
| `GET` | `/me` | Yes | Return authenticated user info | `{"company_id": "...", "user_id": "..."}` |
| `GET` | `/docs` | No | Swagger UI (auto-generated) | HTML |
| `GET` | `/redoc` | No | ReDoc (auto-generated) | HTML |
| `GET` | `/openapi.json` | No | OpenAPI schema | JSON |

---

## Authentication & Authorization

### Authentication Flow (Clerk)

```
Client → sends Bearer token in Authorization header
  ↓
AuthMiddleware → validates token via Clerk SDK
  ↓
On success → extracts company_id (from public_metadata) and user_id (from sub claim)
  ↓
Stores on request.state → available to all route handlers and dependencies
```

### Authorization Model

Currently minimal:
- **Authenticated** = valid Clerk session token
- **Authorized** = valid `company_id` UUID in token's public metadata
- **Tenant-scoped** = all DB queries automatically filtered by RLS

Not yet implemented:
- Role-based access control (admin vs. employee)
- Per-resource permission checks
- API rate limiting

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

### Planned Schema

Tables planned but not yet implemented:
- `companies` — tenant organizations
- `users` — employees within companies
- `cards` — virtual and physical cards
- `transactions` — purchase records
- `budgets` — departmental spending limits
- `audit_log` — immutable record of all changes to budgets, limits, and card status

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
CLERK_SECRET_KEY=sk_test_...
DATABASE_URL=postgresql+asyncpg://localhost:5432/thesa
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
| FastAPI server | Done | App entry point with health check and authenticated endpoint |
| Clerk auth middleware | Done | Full JWT verification, tenant extraction, error handling |
| RLS-aware DB sessions | Done | Async session factory with `SET LOCAL` tenant context |
| Configuration | Done | Pydantic settings with env var loading |
| Workspace rules | Done | Security, RLS, and card issuing conventions in `.cursor/rules/` |
| Dev token helper | Done | Browser-based Clerk sign-in for testing |

### What's Not Built

| Component | Status |
|-----------|--------|
| PostgreSQL schema & RLS policies | Not started |
| SQLAlchemy models | Not started |
| Alembic migrations | Not started |
| Marqeta integration | Not started |
| Card Teller policy engine | Not started |
| Receipt parsing workers | Not started |
| Next.js Command Center | Not started |
| iOS Swift client | Not started |
| Tests & CI/CD | Not started |
| Docker / deployment configs | Not started |

---

## Roadmap

### Phase 1 — Database Foundation
- PostgreSQL schema (companies, users, cards, transactions, budgets, audit_log)
- RLS policies on all tenant-scoped tables
- Alembic migration setup
- Wire `company_id` lookup from database (replace public metadata extraction)

### Phase 2 — Card Issuing & Policy Engine
- Marqeta JIT funding webhook receiver
- Card Teller policy engine (vendor approval → budget check → policy eval → approve/decline)
- Virtual card provisioning (employee requests scoped card)
- Physical card lifecycle management

### Phase 3 — Receipt & Expense Automation
- Gmail API OAuth integration for receipt scanning
- Background worker for PDF extraction and transaction matching
- Mobile receipt capture and upload

### Phase 4 — Client Applications
- Next.js Command Center (transaction log, budget management, card controls)
- iOS POS client (card requests, per diem views, receipt capture)

### Phase 5 — Testing & Hardening
- Tenant isolation test suite (cross-tenant access attempts)
- Webhook signature verification tests
- Policy engine decision tests
- CI/CD pipeline (bandit, safety, pytest)
- Reward optimization routing

---

*Last updated: July 25, 2026*

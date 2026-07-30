"""End-to-end API verification through the full HTTP stack.

Only the Clerk network boundary is faked (token verification and the
server-side email lookup); everything else is real — middleware ordering,
role enforcement, RLS-scoped queries against live PostgreSQL, audit triggers,
and the Reward Router.

Requires the local database to be bootstrapped:

    python -m backend.db.bootstrap
    python -m backend.verify_api_flows

Exits non-zero on any failure.
"""

import sys
import uuid
from datetime import date, timedelta
from types import SimpleNamespace

from clerk_backend_api import Clerk

# --- Fake the Clerk boundary BEFORE the app is imported -----------------

_RUN = uuid.uuid4().hex[:8]
_EMAILS: dict[str, str] = {}  # clerk_user_id -> verified email


def _fake_authenticate_request(self, httpx_request, options):
    token = httpx_request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token.startswith("clerk_"):
        return SimpleNamespace(is_signed_in=False, payload=None, reason="bad token")
    return SimpleNamespace(is_signed_in=True, payload={"sub": token}, reason=None)


Clerk.authenticate_request = _fake_authenticate_request

from fastapi.testclient import TestClient  # noqa: E402

from backend import main  # noqa: E402
from backend.routes import onboarding  # noqa: E402

onboarding._get_clerk_email = lambda clerk_user_id: _EMAILS.get(clerk_user_id)

_FAILURES: list[str] = []


def check(condition: bool, name: str) -> None:
    status = "ok" if condition else "FAIL"
    print(f"  [{status}] {name}")
    if not condition:
        _FAILURES.append(name)


def auth(user: str) -> dict:
    return {"Authorization": f"Bearer clerk_{user}_{_RUN}"}


def run() -> None:
    with TestClient(main.app) as client:
        # --- Auth basics -------------------------------------------------
        check(client.get("/health").status_code == 200, "health is public")
        check(client.get("/me").status_code == 401, "no token rejected")
        check(
            client.get("/me", headers={"Authorization": "Bearer junk"}).status_code
            == 401,
            "garbage token rejected",
        )
        r = client.get("/health")
        check(
            r.headers.get("X-Content-Type-Options") == "nosniff"
            and "Strict-Transport-Security" in r.headers,
            "security headers stamped",
        )

        # --- Onboarding + team -------------------------------------------
        r = client.post(
            "/onboarding",
            headers=auth("owner"),
            json={"company_name": f"Acme Concrete {_RUN}"},
        )
        check(r.status_code == 201 and r.json()["role"] == "owner", "owner onboards")

        r = client.get("/me", headers=auth("owner"))
        check(r.status_code == 200 and r.json()["role"] == "owner", "/me resolves role")

        crew_email = f"crew.{_RUN}@example.com"
        r = client.post(
            "/team/invites",
            headers=auth("owner"),
            json={"email": crew_email.upper(), "role": "crew_lead"},
        )
        check(
            r.status_code == 201 and r.json()["email"] == crew_email,
            "owner invites crew (email normalized)",
        )
        r = client.post(
            "/team/invites",
            headers=auth("owner"),
            json={"email": crew_email, "role": "crew_lead"},
        )
        check(r.status_code == 409, "duplicate pending invite rejected")

        # Crew joins: verified email fetched server-side, matched to invite.
        _EMAILS[f"clerk_crew_{_RUN}"] = crew_email
        r = client.post("/join", headers=auth("crew"))
        check(
            r.status_code == 201 and r.json()["role"] == "crew_lead",
            "crew joins via invite",
        )
        check(
            client.post("/join", headers=auth("crew")).status_code == 409,
            "second join rejected",
        )

        r = client.get("/team/members", headers=auth("crew"))
        check(
            r.status_code == 200 and len(r.json()) == 2,
            "members list shows owner + crew",
        )
        check(
            client.post(
                "/team/invites",
                headers=auth("crew"),
                json={"email": f"x.{_RUN}@example.com", "role": "crew_lead"},
            ).status_code
            == 403,
            "crew cannot invite (role enforced)",
        )
        check(
            client.post(
                "/team/invites",
                headers=auth("owner"),
                json={"email": crew_email, "role": "crew_lead"},
            ).status_code
            == 409,
            "cannot invite an existing member",
        )

        # Stranger with no invite cannot join or touch tenant data.
        _EMAILS[f"clerk_stranger_{_RUN}"] = f"stranger.{_RUN}@example.com"
        check(
            client.post("/join", headers=auth("stranger")).status_code == 404,
            "no invite: join returns 404",
        )
        check(
            client.get("/budgets", headers=auth("stranger")).status_code == 403,
            "company-less user blocked from tenant routes",
        )

        # Revoked invites are dead.
        revoked_email = f"revoked.{_RUN}@example.com"
        r = client.post(
            "/team/invites",
            headers=auth("owner"),
            json={"email": revoked_email, "role": "office_manager"},
        )
        invite_id = r.json()["id"]
        r = client.post(f"/team/invites/{invite_id}/revoke", headers=auth("owner"))
        check(
            r.status_code == 200 and r.json()["status"] == "revoked",
            "owner revokes an invite",
        )
        _EMAILS[f"clerk_revoked_{_RUN}"] = revoked_email
        check(
            client.post("/join", headers=auth("revoked")).status_code == 404,
            "revoked invite cannot be used",
        )

        # --- Portfolio + transactions ------------------------------------
        r = client.post(
            "/portfolio-cards",
            headers=auth("owner"),
            json={
                "label": "Generic Biz Card",
                "issuer": "BigBank",
                "last4": "1111",
                "default_reward_pct": "1.00",
            },
        )
        check(r.status_code == 201, "owner registers generic card")
        generic_id = r.json()["id"]

        r = client.post(
            "/portfolio-cards",
            headers=auth("owner"),
            json={
                "label": "Fuel Rewards Card",
                "issuer": "OtherBank",
                "last4": "2222",
                "default_reward_pct": "1.00",
                "rules": [{"category": "fuel", "reward_pct": "4.00"}],
            },
        )
        check(r.status_code == 201, "owner registers fuel card with 4% rule")
        fuel_id = r.json()["id"]

        check(
            client.post(
                "/portfolio-cards",
                headers=auth("crew"),
                json={"label": "Nope", "issuer": "X", "last4": "9999"},
            ).status_code
            == 403,
            "crew cannot register cards",
        )

        # 3 months of fuel spend on the WRONG (1%) card.
        for days_ago in (10, 40, 70):
            r = client.post(
                "/transactions",
                headers=auth("crew"),
                json={
                    "merchant_name": f"Shell Oil {_RUN}",
                    "amount_cents": 100000,
                    "occurred_on": str(date.today() - timedelta(days=days_ago)),
                    "portfolio_card_id": generic_id,
                },
            )
            check(r.status_code == 201, f"crew records fuel txn ({days_ago}d ago)")
        check(
            r.json()["category"] == "fuel", "merchant auto-classified as fuel"
        )

        # --- Budgets -------------------------------------------------------
        r = client.post(
            "/budgets",
            headers=auth("owner"),
            json={"name": f"Henderson site {_RUN}", "limit_cents": 1000000},
        )
        check(r.status_code == 201, "owner creates budget")
        budget_id = r.json()["id"]

        client.post(
            "/transactions",
            headers=auth("crew"),
            json={
                "merchant_name": f"Lunch Cafe {_RUN}",
                "amount_cents": 5000,
                "occurred_on": str(date.today()),
                "budget_id": budget_id,
            },
        )
        r = client.get("/budgets", headers=auth("crew"))
        budget = next(b for b in r.json() if b["id"] == budget_id)
        check(
            budget["spent_cents_this_month"] == 5000
            and budget["remaining_cents"] == 995000,
            "budget tracks month-to-date spend",
        )

        # --- Per diems ------------------------------------------------------
        crew_user_id = client.get("/me", headers=auth("crew")).json()["user_id"]
        r = client.post(
            "/per-diems",
            headers=auth("owner"),
            json={"user_id": crew_user_id, "daily_limit_cents": 15000},
        )
        check(r.status_code == 201, "owner assigns per diem to crew")
        r = client.get("/per-diems/me", headers=auth("crew"))
        check(
            r.status_code == 200
            and r.json()["spent_today_cents"] == 5000
            and r.json()["remaining_today_cents"] == 10000,
            "crew sees remaining per diem for today",
        )

        # --- Reward Router ---------------------------------------------------
        check(
            client.get("/routing/recommendations", headers=auth("crew")).status_code
            == 403,
            "crew cannot access routing",
        )
        r = client.get("/routing/recommendations", headers=auth("owner"))
        recs = r.json()
        fuel_recs = [x for x in recs if x["vendor_name"] == f"Shell Oil {_RUN}"]
        check(
            len(fuel_recs) == 1
            and fuel_recs[0]["recommended_card_id"] == fuel_id
            and fuel_recs[0]["est_monthly_uplift_cents"] == 3000,
            "router recommends fuel card with correct uplift",
        )

        r = client.post(
            "/routing/decisions",
            headers=auth("owner"),
            json={
                "vendor_name": f"Shell Oil {_RUN}",
                "recommended_card_id": fuel_id,
                "status": "accepted",
            },
        )
        check(r.status_code == 201, "owner accepts recommendation")
        check(
            client.post(
                "/routing/decisions",
                headers=auth("owner"),
                json={
                    "vendor_name": f"Shell Oil {_RUN}",
                    "recommended_card_id": fuel_id,
                    "status": "accepted",
                },
            ).status_code
            == 409,
            "double-accept rejected (no ledger double-count)",
        )
        r = client.get("/routing/ledger", headers=auth("owner"))
        check(
            r.json()["accepted_decisions"] == 1
            and r.json()["est_monthly_uplift_cents"] == 3000,
            "ledger shows accepted uplift once",
        )

        # --- Tenant isolation through the API --------------------------------
        client.post(
            "/onboarding",
            headers=auth("rival"),
            json={"company_name": f"Rival Paving {_RUN}"},
        )
        r = client.get("/transactions", headers=auth("rival"))
        check(r.json() == [], "new tenant sees zero transactions")
        r = client.get("/portfolio-cards", headers=auth("rival"))
        check(r.json() == [], "new tenant sees zero cards")
        r = client.get("/routing/ledger", headers=auth("rival"))
        check(r.json()["accepted_decisions"] == 0, "new tenant has empty ledger")

        # --- Rate limiting -----------------------------------------------------
        client.post(
            "/onboarding",
            headers=auth("spammer"),
            json={"company_name": f"Spam Co {_RUN}"},
        )
        statuses = [
            client.post("/budgets", headers=auth("spammer"), json={}).status_code
            for _ in range(31)
        ]
        check(
            statuses[-1] == 429 and 429 not in statuses[:29],
            "sensitive-write rate limit trips at 31st request",
        )

    if _FAILURES:
        print(f"\n{len(_FAILURES)} check(s) FAILED")
        sys.exit(1)
    print("\nAll API flow checks passed.")


if __name__ == "__main__":
    run()

-- Application role with least privilege. Applied by bootstrap after rls.sql.
--
-- The app must NOT connect as a superuser or table owner: superusers bypass
-- RLS entirely, and FORCE ROW LEVEL SECURITY only binds non-superuser roles.
-- `thesa_app` has no BYPASSRLS, so every query it runs is subject to the
-- tenant policies.
--
-- Local dev (Homebrew Postgres) uses trust auth, so no password is needed.
-- In production, set a password/credential via the secrets manager:
--   ALTER ROLE thesa_app PASSWORD '...';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thesa_app') THEN
        CREATE ROLE thesa_app LOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO thesa_app;

GRANT SELECT, INSERT, UPDATE ON
    companies, users, invites, portfolio_cards, reward_rules, budgets,
    per_diems, transactions, routing_decisions,
    spend_policies, issued_cards, authorization_decisions
TO thesa_app;

-- Webhook idempotency store: not tenant-scoped. INSERT/SELECT only — never
-- mutate or delete processed event IDs (replay protection).
-- Webhook idempotency store: not tenant-scoped. INSERT to claim an event_id,
-- UPDATE to fill decision/reason after Card Teller; DELETE revoked (replay
-- protection must not lose history).
GRANT SELECT, INSERT, UPDATE ON webhook_events TO thesa_app;
REVOKE DELETE ON webhook_events FROM thesa_app;

-- Audit log is append-only for everyone; the app role cannot even try to
-- UPDATE/DELETE (and the trigger blocks any role that can).
GRANT SELECT, INSERT ON audit_log TO thesa_app;
REVOKE UPDATE, DELETE ON audit_log FROM thesa_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO thesa_app;

GRANT EXECUTE ON FUNCTION resolve_user(text) TO thesa_app;
GRANT EXECUTE ON FUNCTION create_company_with_owner(text, text, text) TO thesa_app;
GRANT EXECUTE ON FUNCTION accept_invite(text, text) TO thesa_app;
GRANT EXECUTE ON FUNCTION resolve_issued_card(text) TO thesa_app;
GRANT EXECUTE ON FUNCTION current_tenant() TO thesa_app;

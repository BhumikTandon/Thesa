-- Row-Level Security policies, immutable audit triggers, and auth functions.
-- Applied by backend/db/bootstrap.py after tables are created.
--
-- Fail-closed design: current_setting('app.current_tenant', true) returns NULL
-- when the session variable is unset, and `company_id = NULL` matches zero
-- rows. A request that skips the tenant-session dependency reads NOTHING.
--
-- FORCE ROW LEVEL SECURITY means even the table owner is subject to policies
-- (superusers always bypass; production must connect as a non-superuser role
-- without BYPASSRLS).

-- ============================================================================
-- Tenant isolation helper
-- ============================================================================

CREATE OR REPLACE FUNCTION current_tenant() RETURNS uuid
LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('app.current_tenant', true), '')::uuid
$$;

-- ============================================================================
-- RLS: companies (scoped by primary key, not company_id)
-- ============================================================================

ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE companies FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS companies_tenant_isolation ON companies;
CREATE POLICY companies_tenant_isolation ON companies
    USING (id = current_tenant())
    WITH CHECK (id = current_tenant());

-- ============================================================================
-- RLS: all tenant-scoped tables (company_id column)
-- ============================================================================

DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'users', 'invites', 'portfolio_cards', 'reward_rules', 'budgets',
        'per_diems', 'transactions', 'routing_decisions',
        'spend_policies', 'issued_cards', 'authorization_decisions'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS %I_tenant_isolation ON %I', t, t);
        EXECUTE format(
            'CREATE POLICY %I_tenant_isolation ON %I '
            'USING (company_id = current_tenant()) '
            'WITH CHECK (company_id = current_tenant())',
            t, t
        );
    END LOOP;
END $$;

-- ============================================================================
-- RLS: audit_log (tenant-scoped SELECT and INSERT; no UPDATE/DELETE policy
-- exists, so both are denied under RLS regardless of grants)
-- ============================================================================

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS audit_log_tenant_select ON audit_log;
CREATE POLICY audit_log_tenant_select ON audit_log
    FOR SELECT USING (company_id = current_tenant());

DROP POLICY IF EXISTS audit_log_tenant_insert ON audit_log;
CREATE POLICY audit_log_tenant_insert ON audit_log
    FOR INSERT WITH CHECK (company_id = current_tenant());

-- ============================================================================
-- Immutable audit trail
-- ============================================================================

-- Belt-and-braces immutability: even roles with UPDATE/DELETE grants (or the
-- superuser in dev) cannot mutate audit rows.
CREATE OR REPLACE FUNCTION audit_log_block_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only';
END $$;

DROP TRIGGER IF EXISTS audit_log_no_update_delete ON audit_log;
CREATE TRIGGER audit_log_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_block_mutation();

-- Trigger function that records every change with actor and before/after
-- values. Written by the database, not application code, so no code path can
-- skip it.
CREATE OR REPLACE FUNCTION audit_row_change() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_company uuid;
    v_row_id uuid;
BEGIN
    IF TG_OP = 'DELETE' THEN
        v_company := OLD.company_id;
        v_row_id := OLD.id;
    ELSE
        v_company := NEW.company_id;
        v_row_id := NEW.id;
    END IF;

    INSERT INTO audit_log (
        company_id, table_name, row_id, action, actor_user_id, old_data, new_data
    )
    VALUES (
        v_company,
        TG_TABLE_NAME,
        v_row_id,
        TG_OP,
        NULLIF(current_setting('app.current_user', true), ''),
        CASE WHEN TG_OP IN ('UPDATE', 'DELETE') THEN to_jsonb(OLD) END,
        CASE WHEN TG_OP IN ('INSERT', 'UPDATE') THEN to_jsonb(NEW) END
    );

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END $$;

-- Audited tables per the security rule: every budget, limit, card, routing,
-- and membership/role change is recorded immutably.
DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'budgets', 'per_diems', 'portfolio_cards', 'reward_rules',
        'routing_decisions', 'users', 'invites',
        'spend_policies', 'authorization_decisions'
    ]
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I_audit ON %I', t, t);
        EXECUTE format(
            'CREATE TRIGGER %I_audit '
            'AFTER INSERT OR UPDATE OR DELETE ON %I '
            'FOR EACH ROW EXECUTE FUNCTION audit_row_change()',
            t, t
        );
    END LOOP;
END $$;

-- Issued cards: same audit trail, but strip external_token from the JSON
-- payload so network tokens never land in audit_log (PCI / card-issuing rule).
CREATE OR REPLACE FUNCTION audit_issued_card_change() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_old jsonb;
    v_new jsonb;
BEGIN
    IF TG_OP = 'DELETE' THEN
        v_old := to_jsonb(OLD) - 'external_token';
        INSERT INTO audit_log (
            company_id, table_name, row_id, action, actor_user_id, old_data, new_data
        ) VALUES (
            OLD.company_id, TG_TABLE_NAME, OLD.id, TG_OP,
            NULLIF(current_setting('app.current_user', true), ''),
            v_old, NULL
        );
        RETURN OLD;
    END IF;

    v_new := to_jsonb(NEW) - 'external_token';
    IF TG_OP = 'UPDATE' THEN
        v_old := to_jsonb(OLD) - 'external_token';
    END IF;
    INSERT INTO audit_log (
        company_id, table_name, row_id, action, actor_user_id, old_data, new_data
    ) VALUES (
        NEW.company_id, TG_TABLE_NAME, NEW.id, TG_OP,
        NULLIF(current_setting('app.current_user', true), ''),
        v_old, v_new
    );
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS issued_cards_audit ON issued_cards;
CREATE TRIGGER issued_cards_audit
    AFTER INSERT OR UPDATE OR DELETE ON issued_cards
    FOR EACH ROW EXECUTE FUNCTION audit_issued_card_change();

-- ============================================================================
-- Auth functions (SECURITY DEFINER)
--
-- These run before a tenant context exists, so they must bypass RLS. They are
-- owned by the role that runs bootstrap (dev: superuser). In production, own
-- them via a dedicated role with BYPASSRLS; the app role gets EXECUTE only.
-- ============================================================================

-- Resolve an authenticated Clerk user to their Thesa identity. Called by the
-- auth middleware on every request; replaces trusting company_id from JWT
-- public metadata.
CREATE OR REPLACE FUNCTION resolve_user(p_clerk_user_id text)
RETURNS TABLE (user_id uuid, company_id uuid, role text, email text)
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    SELECT u.id, u.company_id, u.role, u.email
    FROM users u
    WHERE u.clerk_user_id = p_clerk_user_id
$$;

-- One-time onboarding: create a company and its owner atomically. The only
-- path that inserts into companies.
CREATE OR REPLACE FUNCTION create_company_with_owner(
    p_company_name text,
    p_clerk_user_id text,
    p_email text
)
RETURNS TABLE (company_id uuid, user_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_company_id uuid;
    v_user_id uuid;
BEGIN
    IF EXISTS (SELECT 1 FROM users u WHERE u.clerk_user_id = p_clerk_user_id) THEN
        RAISE EXCEPTION 'user already belongs to a company'
            USING ERRCODE = 'unique_violation';
    END IF;

    INSERT INTO companies (name) VALUES (p_company_name)
    RETURNING id INTO v_company_id;

    INSERT INTO users (company_id, clerk_user_id, email, role)
    VALUES (v_company_id, p_clerk_user_id, p_email, 'owner')
    RETURNING id INTO v_user_id;

    RETURN QUERY SELECT v_company_id, v_user_id;
END $$;

-- Join a company via a pending invite. The email is the caller's *verified*
-- Clerk email fetched server-side, never client-supplied. Oldest pending
-- invite wins when multiple companies invited the same address.
CREATE OR REPLACE FUNCTION accept_invite(
    p_clerk_user_id text,
    p_email text
)
RETURNS TABLE (company_id uuid, user_id uuid, role text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_invite invites%ROWTYPE;
    v_user_id uuid;
BEGIN
    IF EXISTS (SELECT 1 FROM users u WHERE u.clerk_user_id = p_clerk_user_id) THEN
        RAISE EXCEPTION 'user already belongs to a company'
            USING ERRCODE = 'unique_violation';
    END IF;

    SELECT * INTO v_invite
    FROM invites i
    WHERE i.email = lower(p_email) AND i.status = 'pending'
    ORDER BY i.created_at ASC
    LIMIT 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'no pending invite for this email'
            USING ERRCODE = 'no_data_found';
    END IF;

    INSERT INTO users (company_id, clerk_user_id, email, role)
    VALUES (v_invite.company_id, p_clerk_user_id, lower(p_email), v_invite.role)
    RETURNING id INTO v_user_id;

    UPDATE invites
    SET status = 'accepted', accepted_at = now()
    WHERE id = v_invite.id;

    RETURN QUERY SELECT v_invite.company_id, v_user_id, v_invite.role::text;
END $$;

-- Resolve an issued card by its opaque issuer token (network token / stub id).
-- Called by the JIT webhook before a tenant context exists.
CREATE OR REPLACE FUNCTION resolve_issued_card(p_external_token text)
RETURNS TABLE (
    card_id uuid,
    company_id uuid,
    user_id uuid,
    budget_id uuid,
    status text,
    scoped_vendor text,
    scoped_category text,
    single_tx_limit_cents bigint,
    expires_at timestamptz
)
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    SELECT
        c.id,
        c.company_id,
        c.user_id,
        c.budget_id,
        c.status::text,
        c.scoped_vendor,
        c.scoped_category,
        c.single_tx_limit_cents,
        c.expires_at
    FROM issued_cards c
    WHERE c.external_token = p_external_token
$$;

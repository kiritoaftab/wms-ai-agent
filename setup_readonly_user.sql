-- ============================================================
-- HMS AI Agent — Read-Only PostgreSQL User Setup
-- Run this as a PostgreSQL superuser ONCE before starting the agent.
-- Usage: psql -U postgres -d hms_db -f setup_readonly_user.sql
-- ============================================================

-- Create read-only role (skip if already exists)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'hms_ai_readonly') THEN
    CREATE ROLE hms_ai_readonly WITH LOGIN PASSWORD 'HmsAiR3ad0nly!2026';
  END IF;
END
$$;

-- Allow the role to connect to the HMS database
GRANT CONNECT ON DATABASE hms_db TO hms_ai_readonly;

-- Allow schema access
GRANT USAGE ON SCHEMA public TO hms_ai_readonly;

-- Grant SELECT on all existing tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO hms_ai_readonly;

-- Ensure future tables are also readable (run as DB owner)
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO hms_ai_readonly;

-- ── Column-level restrictions on the users table ────────────
-- Revoke table-level SELECT first, then grant only safe columns.
-- This blocks password_hash, refresh_token_hash, failed_login_attempts, locked_until
-- even if the AI generates a SELECT * or targets those columns explicitly.

REVOKE SELECT ON users FROM hms_ai_readonly;

GRANT SELECT (
  id, first_name, last_name,
  role_id, department_id,
  email, phone,
  is_active, last_login, password_changed_at,
  created_by, created_at, updated_at, deleted_at
) ON users TO hms_ai_readonly;

-- ── Verify ──────────────────────────────────────────────────
-- \dp users               -- shows per-table and per-column privileges
-- \c hms_db hms_ai_readonly
-- SELECT id, first_name FROM users LIMIT 1;    -- should succeed
-- SELECT password_hash FROM users LIMIT 1;     -- should fail: permission denied

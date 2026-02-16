-- ============================================================
-- WMS AI Agent — Read-Only MySQL User Setup
-- Run this as MySQL root user ONCE before starting the agent
-- ============================================================

-- Create read-only user
CREATE USER IF NOT EXISTS 'wms_ai_readonly'@'localhost'
    IDENTIFIED BY 'WmsAiR3ad0nly!2026';

CREATE USER IF NOT EXISTS 'wms_ai_readonly'@'%'
    IDENTIFIED BY 'WmsAiR3ad0nly!2026';

-- Grant SELECT only on wms_db
GRANT SELECT ON wms_db.* TO 'wms_ai_readonly'@'localhost';
GRANT SELECT ON wms_db.* TO 'wms_ai_readonly'@'%';

-- Revoke access to sensitive tables
REVOKE SELECT ON wms_db.users FROM 'wms_ai_readonly'@'localhost';
REVOKE SELECT ON wms_db.users FROM 'wms_ai_readonly'@'%';

-- Note: If these REVOKE commands fail because the tables don't exist yet,
-- that's fine. The ALLOWED_TABLES whitelist in the validator will also
-- block access to sensitive tables at the application level.

FLUSH PRIVILEGES;

-- Verify
SHOW GRANTS FOR 'wms_ai_readonly'@'localhost';

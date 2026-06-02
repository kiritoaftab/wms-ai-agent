"""
SQL Validator — ensures generated SQL is safe to execute.
Blocks writes, restricts tables, enforces limits.
"""

import re
import sqlparse


# Tables the AI is allowed to query
ALLOWED_TABLES = {
    # Base module
    "roles", "departments", "users",
    "role_permissions", "role_field_definitions", "user_field_values", "role_field_access",
    "audit_logs", "hospital_settings", "notifications",
    # Billing module
    "price_items", "bills", "bill_items", "bill_payments", "invoices",
    # Clinical module
    "schedules", "schedule_overrides", "appointments", "doctor_token_queue",
    "encounters", "vitals", "diagnoses",
    "prescriptions", "prescription_items",
    "clinical_notes", "lab_test_orders", "lab_test_order_items",
    "patient_consents", "referrals",
    # Pharmacy module
    "medicines", "suppliers", "stock_batches", "stock_receipts",
    "stock_receipt_items", "stock_transactions", "dispenses", "dispense_items",
    # IPD module
    "artifacts", "rooms", "beds", "admissions", "bed_allocations",
}

# Tables explicitly blocked (no direct query access)
BLOCKED_TABLES: set = set()

# SQL keywords that indicate write operations
BLOCKED_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "REPLACE", "MERGE",
    "EXEC", "EXECUTE", "CALL", "COPY",
    "INTO OUTFILE", "INTO DUMPFILE", "LOAD DATA",
]

# Dangerous patterns (PostgreSQL-aware)
BLOCKED_PATTERNS = [
    r";\s*\w",                  # multiple statements
    r"--\s",                    # SQL comments (injection vector)
    r"/\*",                     # block comments
    r"PG_SLEEP\s*\(",           # PostgreSQL time-based injection
    r"SLEEP\s*\(",              # generic sleep
    r"BENCHMARK\s*\(",          # benchmark attack
    r"@@\w+",                   # MySQL system variables (extra defense)
    r"INFORMATION_SCHEMA",      # schema discovery
    r"pg_catalog\.",            # PostgreSQL system catalog
    r"pg_read_file\s*\(",       # file read function
    r"pg_ls_dir\s*\(",          # directory listing
    r"lo_import\s*\(",          # large object import
    r"lo_export\s*\(",          # large object export
]


class SQLValidationError(Exception):
    """Raised when SQL fails validation."""
    pass


def validate_sql(sql: str) -> str:
    """
    Validate and sanitize generated SQL.
    Returns cleaned SQL or raises SQLValidationError.
    """
    if not sql or sql.strip().upper() == "NONE":
        raise SQLValidationError("No SQL generated — question may not be answerable from the database.")

    # Normalize whitespace
    cleaned = " ".join(sql.strip().split())

    # Must start with SELECT
    if not cleaned.upper().lstrip().startswith("SELECT"):
        raise SQLValidationError("Only SELECT queries are allowed.")

    # Check for blocked keywords
    sql_upper = cleaned.upper()
    for keyword in BLOCKED_KEYWORDS:
        pattern = r'\b' + keyword.replace(' ', r'\s+') + r'\b'
        if re.search(pattern, sql_upper):
            raise SQLValidationError(f"Blocked operation detected: {keyword}")

    # Check for dangerous patterns
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            raise SQLValidationError("Potentially unsafe SQL pattern detected.")

    # Parse and validate table references
    parsed = sqlparse.parse(cleaned)
    if not parsed:
        raise SQLValidationError("Could not parse SQL statement.")

    if len(parsed) > 1:
        raise SQLValidationError("Multiple SQL statements are not allowed.")

    # Extract table names and validate against allowlist
    tables_referenced = _extract_table_names(cleaned)

    for table in tables_referenced:
        table_lower = table.lower()
        if table_lower in BLOCKED_TABLES:
            raise SQLValidationError(f"Access to table '{table}' is not permitted.")
        if table_lower not in ALLOWED_TABLES:
            raise SQLValidationError(
                f"Unknown table '{table}'. Available tables: {', '.join(sorted(ALLOWED_TABLES))}"
            )

    # Ensure LIMIT exists; add default if missing
    if "LIMIT" not in sql_upper:
        cleaned = cleaned.rstrip(";").strip() + " LIMIT 100"

    # Enforce max limit of 500
    limit_match = re.search(r'LIMIT\s+(\d+)', cleaned, re.IGNORECASE)
    if limit_match:
        limit_val = int(limit_match.group(1))
        if limit_val > 500:
            cleaned = re.sub(r'LIMIT\s+\d+', 'LIMIT 500', cleaned, flags=re.IGNORECASE)

    return cleaned.rstrip(";")


# Functions that use FROM as syntax (EXTRACT(field FROM expr)), not a table clause
_FUNCTIONS_WITH_INNER_FROM = (
    "EXTRACT", "TRIM", "SUBSTRING", "OVERLAY", "POSITION",
)

# Identifiers that are never table names (keywords, functions, literals)
_NON_TABLE_IDENTIFIERS = frozenset({
    "SELECT", "WHERE", "ON", "AND", "OR", "AS", "INNER", "LEFT", "RIGHT",
    "OUTER", "CROSS", "NATURAL", "FULL", "JOIN", "FROM", "GROUP", "ORDER",
    "BY", "HAVING", "LIMIT", "OFFSET", "UNION", "ALL", "DISTINCT", "NULL",
    "TRUE", "FALSE", "CASE", "WHEN", "THEN", "ELSE", "END", "IN", "NOT",
    "BETWEEN", "LIKE", "IS", "EXISTS", "ASC", "DESC", "SET", "LATERAL", "ONLY",
    "CURRENT_DATE", "CURRENT_TIMESTAMP", "CURRENT_TIME", "LOCALTIME",
    "LOCALTIMESTAMP", "CURDATE", "CURTIME", "NOW", "SYSDATE", "TODAY",
    "INTERVAL", "DATE_TRUNC", "COALESCE", "NULLIF", "CAST", "COUNT",
    "SUM", "AVG", "MIN", "MAX", "YEAR", "MONTH", "DAY", "HOUR", "MINUTE",
    "SECOND", "DATE", "TIME", "TIMESTAMP", "FIELD", "IFNULL", "CONCAT",
})


def _scrub_from_in_functions(sql: str) -> str:
    """
    Neutralize FROM inside function calls (e.g. EXTRACT(YEAR FROM col)).
    A naive (FROM|JOIN) regex otherwise treats alias.column and CURRENT_DATE as tables.
    """
    scrubbed = sql
    for func in _FUNCTIONS_WITH_INNER_FROM:
        scrubbed = re.sub(
            rf"(\b{func}\s*\([^)]*?)\s+FROM\s+",
            r"\1 , ",
            scrubbed,
            flags=re.IGNORECASE,
        )
    return scrubbed


def _extract_table_names(sql: str) -> set:
    """
    Extract real table names from FROM / JOIN clauses.
    Ignores table aliases and FROM tokens inside SQL functions.
    """
    scrubbed = _scrub_from_in_functions(sql)
    tables: set[str] = set()
    aliases: set[str] = set()

    clause_pattern = re.compile(
        r"\b(?:FROM|(?:INNER|LEFT|RIGHT|FULL|CROSS|NATURAL)?\s*JOIN)\s+"
        r"(\w+)"
        r"(?:\s+(?:AS\s+)?(\w+))?",
        re.IGNORECASE,
    )

    for match in clause_pattern.finditer(scrubbed):
        table_name, alias = match.group(1), match.group(2)
        table_upper = table_name.upper()
        alias_upper = alias.upper() if alias else None

        if table_upper in _NON_TABLE_IDENTIFIERS:
            continue

        tables.add(table_name)

        if alias and alias_upper not in _NON_TABLE_IDENTIFIERS:
            aliases.add(alias)

    return {
        t for t in tables
        if t.lower() not in aliases and t.upper() not in _NON_TABLE_IDENTIFIERS
    }

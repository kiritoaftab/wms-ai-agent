"""
SQL Validator — ensures generated SQL is safe to execute.
Blocks writes, restricts tables, enforces limits.
"""

import re
import sqlparse


# Tables the AI is allowed to query
ALLOWED_TABLES = {
    "inventory", "inventory_holds", "inventory_transactions",
    "skus", "asns", "asn_lines", "asn_line_pallets",
    "grns", "grn_lines", "pallets",
    "warehouses", "clients", "suppliers", "docks", "locations",
    "sales_orders", "sales_order_lines", "stock_allocations",
    "pick_waves", "pick_wave_orders", "pick_tasks", "cartons", "carton_items","shipments",
    "rate_cards","billable_events","invoices","payments"
}

# Tables explicitly blocked (sensitive data)
BLOCKED_TABLES = {
    "users", "roles", "permissions", "modules",
    "role_module", "user_role",
}

# SQL keywords that indicate write operations
BLOCKED_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "REPLACE", "MERGE",
    "EXEC", "EXECUTE", "CALL",
    "INTO OUTFILE", "INTO DUMPFILE", "LOAD DATA",
]

# Dangerous patterns
BLOCKED_PATTERNS = [
    r";\s*\w",            # multiple statements
    r"--\s",              # SQL comments (injection vector)
    r"/\*",               # block comments
    r"SLEEP\s*\(",        # time-based injection
    r"BENCHMARK\s*\(",    # benchmark attack
    r"@@\w+",             # system variables
    r"INFORMATION_SCHEMA", # schema discovery
    r"mysql\.\w+",        # mysql system tables
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
        # Word boundary check to avoid false positives
        pattern = r'\b' + keyword.replace(' ', r'\s+') + r'\b'
        if re.search(pattern, sql_upper):
            raise SQLValidationError(f"Blocked operation detected: {keyword}")

    # Check for dangerous patterns
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            raise SQLValidationError(f"Potentially unsafe SQL pattern detected.")

    # Parse and validate table references
    parsed = sqlparse.parse(cleaned)
    if not parsed:
        raise SQLValidationError("Could not parse SQL statement.")

    if len(parsed) > 1:
        raise SQLValidationError("Multiple SQL statements are not allowed.")

    # Extract table names (basic extraction)
    tables_referenced = _extract_table_names(cleaned)

    # Check against blocked tables
    for table in tables_referenced:
        table_lower = table.lower()
        if table_lower in BLOCKED_TABLES:
            raise SQLValidationError(f"Access to table '{table}' is not permitted.")
        if table_lower not in ALLOWED_TABLES:
            raise SQLValidationError(f"Unknown table '{table}'. Available tables: {', '.join(sorted(ALLOWED_TABLES))}")

    # Ensure LIMIT exists, add if missing
    if "LIMIT" not in sql_upper:
        cleaned = cleaned.rstrip(";").strip() + " LIMIT 100"

    # Enforce max limit
    limit_match = re.search(r'LIMIT\s+(\d+)', cleaned, re.IGNORECASE)
    if limit_match:
        limit_val = int(limit_match.group(1))
        if limit_val > 500:
            cleaned = re.sub(
                r'LIMIT\s+\d+', 'LIMIT 500', cleaned, flags=re.IGNORECASE
            )

    return cleaned.rstrip(";")


def _extract_table_names(sql: str) -> set:
    """
    Extract table names from SQL query.
    Handles FROM, JOIN, and subqueries.
    """
    tables = set()

    # Pattern: FROM table_name [alias] or JOIN table_name [alias]
    pattern = r'(?:FROM|JOIN)\s+(\w+)'
    matches = re.findall(pattern, sql, re.IGNORECASE)

    for match in matches:
        # Skip SQL keywords that might match
        if match.upper() not in ('SELECT', 'WHERE', 'ON', 'AND', 'OR', 'AS', 'INNER', 'LEFT', 'RIGHT', 'OUTER', 'CROSS', 'NATURAL'):
            tables.add(match)

    return tables

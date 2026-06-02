"""Tests for SQL table extraction — guards against EXTRACT(... FROM ...) false positives."""

import unittest

from app.services.sql_validator import (
    ALLOWED_TABLES,
    _extract_table_names,
    _scrub_from_in_functions,
    validate_sql,
)


class ExtractTableNamesTests(unittest.TestCase):
    """Regression tests from production threads (Orbit Care)."""

    def test_appointments_with_extract_year(self):
        sql = (
            "SELECT COUNT(*) AS completed_appointments FROM appointments a "
            "WHERE a.status = 'completed' "
            "AND EXTRACT(YEAR FROM a.appointment_date) = EXTRACT(YEAR FROM CURRENT_DATE) "
            "LIMIT 100"
        )
        self.assertEqual(_extract_table_names(sql), {"appointments"})

    def test_encounters_join_with_extract_year(self):
        sql = (
            "SELECT u.first_name || ' ' || u.last_name AS doctor_name, d.name AS department, "
            "COUNT(e.id) AS completed_encounters FROM encounters e "
            "JOIN users u ON e.doctor_id = u.id AND u.deleted_at IS NULL "
            "LEFT JOIN departments d ON u.department_id = d.id "
            "WHERE e.status = 'completed' "
            "AND EXTRACT(YEAR FROM e.encounter_date) = EXTRACT(YEAR FROM CURRENT_DATE) "
            "GROUP BY u.id, u.first_name, u.last_name, d.name "
            "ORDER BY completed_encounters DESC LIMIT 20"
        )
        self.assertEqual(
            _extract_table_names(sql),
            {"encounters", "users", "departments"},
        )

    def test_date_trunc_does_not_false_positive(self):
        sql = (
            "SELECT COUNT(e.id) FROM encounters e JOIN users u ON e.doctor_id = u.id "
            "WHERE DATE_TRUNC('month', e.encounter_date) = DATE_TRUNC('month', CURRENT_DATE) "
            "LIMIT 20"
        )
        self.assertEqual(_extract_table_names(sql), {"encounters", "users"})

    def test_scrub_replaces_inner_from_only(self):
        original = "EXTRACT(YEAR FROM e.encounter_date) = EXTRACT(YEAR FROM CURRENT_DATE)"
        scrubbed = _scrub_from_in_functions(original)
        self.assertNotIn(" FROM ", scrubbed.upper())
        self.assertIn("EXTRACT(YEAR , e.encounter_date)", scrubbed)


class ValidateSqlTests(unittest.TestCase):
    """End-to-end validation against Orbit Care allowlist."""

    def test_doctors_completed_encounters_this_year(self):
        sql = (
            "SELECT u.first_name || ' ' || u.last_name AS doctor_name, d.name AS department, "
            "COUNT(e.id) AS completed_encounters FROM encounters e "
            "JOIN users u ON e.doctor_id = u.id "
            "LEFT JOIN departments d ON u.department_id = d.id "
            "WHERE e.status = 'completed' "
            "AND EXTRACT(YEAR FROM e.encounter_date) = EXTRACT(YEAR FROM CURRENT_DATE) "
            "GROUP BY u.id, u.first_name, u.last_name, d.name "
            "ORDER BY completed_encounters DESC LIMIT 20"
        )
        result = validate_sql(sql)
        self.assertTrue(result.upper().startswith("SELECT"))
        for table in ("encounters", "users", "departments"):
            self.assertIn(table, ALLOWED_TABLES)


if __name__ == "__main__":
    unittest.main()

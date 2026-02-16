"""
SQL Generator — converts natural language to SQL using Azure OpenAI.
"""

import re
import time
from typing import Optional
from openai import AzureOpenAI

from app.config import get_settings
from app.prompts.system_prompt import build_messages
from app.services.sql_validator import validate_sql, SQLValidationError


class SQLGenerationError(Exception):
    """Raised when SQL generation fails."""
    pass


class SQLGenerator:
    def __init__(self):
        settings = get_settings()
        self.client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        self.deployment = settings.azure_openai_deployment

    def generate(
        self,
        question: str,
        context: Optional[dict] = None,
        conversation_history: Optional[list] = None,
    ) -> dict:
        """
        Generate SQL from natural language question.

        Returns dict with:
            - sql: validated SQL query
            - explanation: what the query does
            - chart_type: suggested visualization
            - chart_x: x-axis column
            - chart_y: y-axis column
            - chart_title: chart title
            - generation_time_ms: time taken
        """
        start_time = time.time()

        messages = build_messages(question, context, conversation_history)

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=0.1,     # low temp for deterministic SQL
                max_tokens=1000,
                top_p=0.95,
            )
        except Exception as e:
            raise SQLGenerationError(f"Azure OpenAI API error: {str(e)}")

        raw_response = response.choices[0].message.content.strip()
        generation_time = (time.time() - start_time) * 1000

        # Parse the structured response
        result = self._parse_response(raw_response)
        result["generation_time_ms"] = round(generation_time, 2)
        result["raw_response"] = raw_response

        # Validate the generated SQL
        if result["sql"] and result["sql"].upper() != "NONE":
            try:
                result["sql"] = validate_sql(result["sql"])
            except SQLValidationError as e:
                result["validation_error"] = str(e)
                result["sql"] = None

        return result

    def _parse_response(self, response: str) -> dict:
        """
        Parse the structured response from the LLM.
        Expected format:
            EXPLANATION: ...
            SQL: ...
            CHART: ...
            CHART_X: ...
            CHART_Y: ...
            CHART_TITLE: ...
        """
        result = {
            "explanation": "",
            "sql": None,
            "chart_type": "table",
            "chart_x": None,
            "chart_y": None,
            "chart_title": "",
        }

        # Extract EXPLANATION
        expl_match = re.search(r'EXPLANATION:\s*(.+?)(?=\nSQL:)', response, re.DOTALL)
        if expl_match:
            result["explanation"] = expl_match.group(1).strip()

        # Extract SQL (can be multiline)
        sql_match = re.search(r'SQL:\s*(.+?)(?=\nCHART:)', response, re.DOTALL)
        if sql_match:
            sql = sql_match.group(1).strip()
            # Remove markdown code fences if present
            sql = re.sub(r'```sql\s*', '', sql)
            sql = re.sub(r'```\s*', '', sql)
            if sql.upper() != "NONE":
                result["sql"] = sql

        # Extract CHART type
        chart_match = re.search(r'CHART:\s*(\w+)', response)
        if chart_match:
            result["chart_type"] = chart_match.group(1).strip().lower()

        # Extract CHART_X
        x_match = re.search(r'CHART_X:\s*(.+)', response)
        if x_match:
            val = x_match.group(1).strip().lower()
            result["chart_x"] = None if val == "none" else val

        # Extract CHART_Y
        y_match = re.search(r'CHART_Y:\s*(.+)', response)
        if y_match:
            val = y_match.group(1).strip().lower()
            result["chart_y"] = None if val == "none" else val

        # Extract CHART_TITLE
        title_match = re.search(r'CHART_TITLE:\s*(.+)', response)
        if title_match:
            result["chart_title"] = title_match.group(1).strip()

        return result

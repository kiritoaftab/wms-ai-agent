"""
Result Formatter — takes raw query results and generates:
1. Natural language summary
2. Follow-up question suggestions
"""

import json
from openai import AzureOpenAI

from app.config import get_settings


SUMMARIZER_PROMPT = """You are a warehouse data analyst assistant. Given a user's question, the SQL that was run, and the query results, provide:

1. A concise natural language summary of the results (2-4 sentences). Use specific numbers. Format currency in ₹ (Indian Rupees) when relevant.
2. Three suggested follow-up questions the user might want to ask next.

RESPONSE FORMAT (strictly follow this):
SUMMARY: <your summary here>
FOLLOWUP1: <first follow-up question>
FOLLOWUP2: <second follow-up question>
FOLLOWUP3: <third follow-up question>
"""


class ResultFormatter:
    def __init__(self):
        settings = get_settings()
        self.client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        self.deployment = settings.azure_openai_deployment

    def format_results(
        self,
        question: str,
        sql: str,
        data: list[dict],
        row_count: int,
        explanation: str,
    ) -> dict:
        """
        Generate a natural language summary and follow-up suggestions.
        """
        # For large result sets, only send first 20 rows to LLM
        sample_data = data[:20] if len(data) > 20 else data
        truncated = len(data) > 20

        user_content = f"""Question: {question}
SQL Executed: {sql}
Explanation: {explanation}
Total Rows: {row_count}
{"(Showing first 20 of " + str(row_count) + " rows)" if truncated else ""}

Results:
{json.dumps(sample_data, indent=2, default=str)}"""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": SUMMARIZER_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            raw = response.choices[0].message.content.strip()
            return self._parse_summary(raw)

        except Exception as e:
            # Fallback: generate basic summary without LLM
            return {
                "summary": f"Query returned {row_count} row(s)." + (
                    f" {explanation}" if explanation else ""
                ),
                "follow_ups": [
                    "Can you break this down further?",
                    "Show me the trend over time",
                    "Compare with last month",
                ],
            }

    def _parse_summary(self, raw: str) -> dict:
        """Parse the structured summary response."""
        import re

        summary = ""
        follow_ups = []

        # Extract summary
        summary_match = re.search(r'SUMMARY:\s*(.+?)(?=\nFOLLOWUP1:)', raw, re.DOTALL)
        if summary_match:
            summary = summary_match.group(1).strip()
        else:
            # Fallback: use everything before first FOLLOWUP
            summary = raw.split("FOLLOWUP")[0].replace("SUMMARY:", "").strip()

        # Extract follow-ups
        for i in range(1, 4):
            match = re.search(rf'FOLLOWUP{i}:\s*(.+?)(?=\n|$)', raw)
            if match:
                follow_ups.append(match.group(1).strip())

        # Ensure we always have 3 follow-ups
        defaults = [
            "Break this down by category",
            "Show me the trend over time",
            "Compare with the previous period",
        ]
        while len(follow_ups) < 3:
            follow_ups.append(defaults[len(follow_ups)])

        return {
            "summary": summary,
            "follow_ups": follow_ups,
        }

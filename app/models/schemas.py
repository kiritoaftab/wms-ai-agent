"""
Pydantic models for API request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ── Request Models ──────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    thread_id: Optional[str] = None  # null = new thread
    parent_node_id: Optional[str] = None  # which node this follows up on
    context: Optional[dict] = None   # optional filters like warehouse_id, client_id

    class Config:
        json_schema_extra = {
            "example": {
                "question": "What is the total inventory on hand by SKU?",
                "thread_id": None,
                "context": {"warehouse_id": 1}
            }
        }


class FollowUpRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    thread_id: str
    parent_node_id: str  # which node this follows up on


# ── Response Models ─────────────────────────────────────────

class ChartSuggestion(BaseModel):
    chart_type: str  # bar, line, pie, table, number
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    title: str
    description: Optional[str] = None


class QueryResponse(BaseModel):
    thread_id: str
    node_id: str
    question: str
    sql_generated: Optional[str] = None
    data: list[dict] = []
    row_count: int = 0
    summary: str
    chart_suggestion: Optional[ChartSuggestion] = None
    suggested_follow_ups: list[str] = []
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None


class ThreadSummary(BaseModel):
    thread_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    node_count: int


class ThreadDetail(BaseModel):
    thread_id: str
    title: str
    created_at: datetime
    nodes: list[dict]  # ordered list of query/response pairs


class HealthResponse(BaseModel):
    status: str
    db_connected: bool
    azure_configured: bool

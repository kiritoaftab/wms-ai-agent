"""
Query Router — handles NL query requests and orchestrates the full pipeline.
"""

import time
from fastapi import APIRouter, HTTPException

from app.models.schemas import QueryRequest, FollowUpRequest, QueryResponse, ChartSuggestion
from app.services.sql_generator import SQLGenerator, SQLGenerationError
from app.services.sql_validator import SQLValidationError
from app.services.query_executor import QueryExecutor, QueryExecutionError
from app.services.result_formatter import ResultFormatter
from app.services.thread_manager import ThreadManager

router = APIRouter(prefix="/api/ai", tags=["AI Query"])

# Initialize services (singleton-like for the module)
sql_generator = SQLGenerator()
query_executor = QueryExecutor()
result_formatter = ResultFormatter()
thread_manager = ThreadManager()


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Main endpoint: accepts natural language question, returns data + summary.

    Pipeline: NL → SQL Generation → Validation → Execution → Summarization
    """
    total_start = time.time()

    # ── Step 1: Resolve thread ────────────────────────────────
    thread_id = request.thread_id
    conversation_history = None

    parent_node_id = request.parent_node_id

    if thread_id:
        # Follow-up: load conversation history for context
        conversation_history = thread_manager.get_conversation_history(thread_id)
    else:
        # New thread: create one
        # Use first 60 chars of question as thread title
        title = request.question[:60] + ("..." if len(request.question) > 60 else "")
        thread_id = thread_manager.create_thread(title)

    # ── Step 2: Generate SQL ──────────────────────────────────
    try:
        generation_result = sql_generator.generate(
            question=request.question,
            context=request.context,
            conversation_history=conversation_history,
        )
    except SQLGenerationError as e:
        # Save error to thread and return
        node_id = thread_manager.add_node(
            thread_id=thread_id,
            parent_node_id=parent_node_id,
            question=request.question,
            error=str(e),
        )
        return QueryResponse(
            thread_id=thread_id,
            node_id=node_id,
            question=request.question,
            summary="I couldn't generate a query for that question.",
            error=str(e),
        )

    sql = generation_result.get("sql")
    explanation = generation_result.get("explanation", "")

    # Handle validation errors from generator
    if generation_result.get("validation_error"):
        node_id = thread_manager.add_node(
            thread_id=thread_id,
            parent_node_id=parent_node_id,
            question=request.question,
            sql_generated=generation_result.get("raw_response"),
            error=generation_result["validation_error"],
        )
        return QueryResponse(
            thread_id=thread_id,
            node_id=node_id,
            question=request.question,
            summary=f"Generated query didn't pass safety checks: {generation_result['validation_error']}",
            error=generation_result["validation_error"],
        )

    if not sql:
        node_id = thread_manager.add_node(
            thread_id=thread_id,
            parent_node_id=parent_node_id,
            question=request.question,
            summary="This question can't be answered from the warehouse database.",
            error="No SQL generated",
        )
        return QueryResponse(
            thread_id=thread_id,
            node_id=node_id,
            question=request.question,
            summary="This question can't be answered from the warehouse database. " + explanation,
        )

    # ── Step 3: Execute SQL ───────────────────────────────────
    try:
        exec_result = query_executor.execute(sql)
    except QueryExecutionError as e:
        node_id = thread_manager.add_node(
            thread_id=thread_id,
            parent_node_id=parent_node_id,
            question=request.question,
            sql_generated=sql,
            error=str(e),
        )
        return QueryResponse(
            thread_id=thread_id,
            node_id=node_id,
            question=request.question,
            sql_generated=sql,
            summary=f"Query failed to execute: {str(e)}",
            error=str(e),
        )

    data = exec_result["data"]
    row_count = exec_result["row_count"]

    # ── Step 4: Summarize results ─────────────────────────────
    format_result = result_formatter.format_results(
        question=request.question,
        sql=sql,
        data=data,
        row_count=row_count,
        explanation=explanation,
    )

    # ── Step 5: Build chart suggestion ────────────────────────
    chart_suggestion = None
    if generation_result.get("chart_type") and generation_result["chart_type"] != "none":
        chart_suggestion = ChartSuggestion(
            chart_type=generation_result["chart_type"],
            x_axis=generation_result.get("chart_x"),
            y_axis=generation_result.get("chart_y"),
            title=generation_result.get("chart_title", ""),
        )

    total_time = (time.time() - total_start) * 1000

    # ── Step 6: Save to thread ────────────────────────────────
    node_id = thread_manager.add_node(
        thread_id=thread_id,
        parent_node_id=parent_node_id,
        question=request.question,
        sql_generated=sql,
        data=data,
        row_count=row_count,
        summary=format_result["summary"],
        chart_suggestion=chart_suggestion.model_dump() if chart_suggestion else None,
        follow_ups=format_result["follow_ups"],
        execution_time_ms=total_time,
    )

    return QueryResponse(
        thread_id=thread_id,
        node_id=node_id,
        question=request.question,
        sql_generated=sql,
        data=data,
        row_count=row_count,
        summary=format_result["summary"],
        chart_suggestion=chart_suggestion,
        suggested_follow_ups=format_result["follow_ups"],
        execution_time_ms=round(total_time, 2),
    )


@router.post("/follow-up", response_model=QueryResponse)
async def follow_up(request: FollowUpRequest):
    """
    Follow-up question within an existing thread.
    Uses conversation history for context.
    """
    # Validate thread exists
    thread = thread_manager.get_thread(request.thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Delegate to the main query handler with thread context
    return await query(QueryRequest(
        question=request.question,
        thread_id=request.thread_id,
        parent_node_id=request.parent_node_id,
        context=None,
    ))

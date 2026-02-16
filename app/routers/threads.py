"""
Threads Router — list, view, and delete conversation threads.
"""

from fastapi import APIRouter, HTTPException

from app.services.thread_manager import ThreadManager

router = APIRouter(prefix="/api/ai/threads", tags=["Threads"])

thread_manager = ThreadManager()


@router.get("")
async def list_threads(limit: int = 50):
    """List recent conversation threads."""
    threads = thread_manager.list_threads(limit=limit)
    return {"threads": threads, "count": len(threads)}


@router.get("/{thread_id}")
async def get_thread(thread_id: str):
    """Get a thread with all its query/response nodes."""
    thread = thread_manager.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@router.delete("/{thread_id}")
async def delete_thread(thread_id: str):
    """Delete a thread and all its nodes."""
    deleted = thread_manager.delete_thread(thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"message": "Thread deleted", "thread_id": thread_id}

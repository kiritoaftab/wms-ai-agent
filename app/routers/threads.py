"""
Threads Router — list, view, and delete conversation threads.
"""

from fastapi import APIRouter, HTTPException, Depends
from app.utils.auth import verify_token

from app.services.thread_manager import ThreadManager

router = APIRouter(prefix="/api/ai/threads", tags=["Threads"])

thread_manager = ThreadManager()


@router.get("")
async def list_threads(limit: int = 50, token=Depends(verify_token)):
    """List recent conversation threads."""
    user_id = str(token.get("userId")) if token.get("userId") else None
    threads = thread_manager.list_threads(limit=limit, user_id=user_id)
    return {"threads": threads, "count": len(threads)}


@router.get("/{thread_id}")
async def get_thread(thread_id: str, _=Depends(verify_token)):
    """Get a thread with all its query/response nodes."""
    thread = thread_manager.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@router.delete("/{thread_id}")
async def delete_thread(thread_id: str, _=Depends(verify_token)):
    """Delete a thread and all its nodes."""
    deleted = thread_manager.delete_thread(thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"message": "Thread deleted", "thread_id": thread_id}

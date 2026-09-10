"""
WebSocket API for real-time job progress updates
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio
import json
import logging
import uuid

from app.core.database import get_db
from app.models.job import Job
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Store active WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
    
    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)
        logger.info(f"WebSocket connected for job {job_id}")
    
    def disconnect(self, job_id: str, websocket: WebSocket):
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]
        logger.info(f"WebSocket disconnected for job {job_id}")
    
    async def send_update(self, job_id: str, message: dict):
        if job_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[job_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send message to websocket: {e}")
                    disconnected.append(connection)
            
            # Remove disconnected clients
            for conn in disconnected:
                self.disconnect(job_id, conn)
    
    async def broadcast(self, job_id: str, message: dict):
        await self.send_update(job_id, message)


manager = ConnectionManager()


@router.websocket("/jobs/{job_id}/stream")
async def websocket_job_stream(
    websocket: WebSocket,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint for real-time job progress
    - Connects client to job stream
    - Sends updates every 2 seconds
    - Automatically disconnects when job completes
    """
    job_id_str = str(job_id)
    await manager.connect(job_id_str, websocket)
    
    try:
        while True:
            # Fetch job status from database
            result = await db.execute(
                select(Job).where(Job.id == job_id)
            )
            job = result.scalar_one_or_none()
            
            if not job:
                await websocket.send_json({
                    "event": "error",
                    "message": "Job not found"
                })
                break
            
            # Send progress update
            progress_data = {
                "event": "progress",
                "job_id": str(job.id),
                "status": job.status,
                "total_count": job.total_count,
                "success_count": job.success_count,
                "failed_count": job.failed_count,
                "cancelled_count": job.cancelled_count,
                "percentage": round((job.success_count + job.failed_count + job.cancelled_count) / job.total_count * 100, 2) if job.total_count > 0 else 0
            }
            
            await websocket.send_json(progress_data)
            
            # If job is complete, send completion event
            if job.status in ["done", "failed", "cancelled"]:
                await websocket.send_json({
                    "event": "job_complete",
                    "job_id": str(job.id),
                    "status": job.status,
                    "final_stats": {
                        "total_count": job.total_count,
                        "success_count": job.success_count,
                        "failed_count": job.failed_count,
                        "cancelled_count": job.cancelled_count
                    }
                })
                break
            
            # Wait 2 seconds before next update
            await asyncio.sleep(2)
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
    finally:
        manager.disconnect(job_id_str, websocket)


# Export manager for use in Celery tasks
def get_connection_manager():
    return manager

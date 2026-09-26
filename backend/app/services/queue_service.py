"""
Redis queue service.

Wraps rq (Redis Queue) for job enqueueing and dequeuing.
All Redis-specific code is isolated here.
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_redis_connection():
    """Return a Redis connection from the configured URL."""
    from redis import Redis
    from ..config import settings
    # protocol=2 ensures RESP2 compatibility with Redis 3.x–6.x
    # (redis-py 5+ sends HELLO by default, which requires Redis 6+)
    return Redis.from_url(settings.REDIS_URL, decode_responses=False, protocol=2)


def get_queue(name: str = "video_processing"):
    """Return an rq Queue."""
    from rq import Queue
    conn = get_redis_connection()
    return Queue(name, connection=conn)


def enqueue_job(job_id: str, queue_name: str = "video_processing") -> str:
    """
    Push job_id onto the Redis queue.
    Returns the rq job ID (same as job_id for traceability).
    """
    from rq import Queue
    from ..config import settings

    conn = get_redis_connection()
    q = Queue(queue_name, connection=conn)

    # We enqueue the worker task function with job_id as argument.
    # Import here to avoid circular imports at module load time.
    from ..worker.tasks import process_job

    rq_job = q.enqueue(
        process_job,
        job_id,
        job_timeout=660,  # 11 min max per job
        result_ttl=3600,
        failure_ttl=86400,
    )
    logger.info("Enqueued job %s as rq job %s", job_id, rq_job.id)
    return rq_job.id


def is_redis_available() -> bool:
    """Return True if Redis is reachable."""
    try:
        conn = get_redis_connection()
        conn.ping()
        return True
    except Exception:
        return False

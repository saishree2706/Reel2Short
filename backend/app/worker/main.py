"""
Worker entry point.

Run from the project root:
    .venv/Scripts/python.exe -m app.worker.main

Or from the backend/ directory:
    ../.venv/Scripts/python.exe -m app.worker.main
"""
import logging
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger("reel2short.worker")


def main() -> None:
    from ..database import init_db
    from ..services.queue_service import get_queue, get_redis_connection
    from ..services.job_service import JobService
    from ..database import SessionLocal

    # Ensure DB tables exist
    init_db()

    logger.info("Reel2Short video worker starting...")

    # Verify Redis
    try:
        conn = get_redis_connection()
        conn.ping()
        logger.info("Redis connection OK")
    except Exception as e:
        logger.critical("Cannot connect to Redis: %s", e)
        sys.exit(1)

    # Recover any stale jobs from a previous crash
    db = SessionLocal()
    try:
        recovered = JobService.recover_stale_jobs(db)
        if recovered:
            logger.info("Recovered %d stale jobs", recovered)
    finally:
        db.close()

    # Start rq worker
    # On Windows, os.fork does not exist, so use SimpleWorker instead of Worker
    if hasattr(os, "fork"):
        from rq import Worker
        worker_cls = Worker
    else:
        from rq import SimpleWorker
        worker_cls = SimpleWorker
    from rq.timeouts import JobTimeoutException

    queue = get_queue()
    worker = worker_cls([queue], connection=conn)

    logger.info("Worker (%s) listening on queue: %s", worker_cls.__name__, queue.name)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()


from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "aac_worker",
    broker=settings.REDIS_CELERY_BROKER,
    backend=settings.REDIS_CELERY_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=settings.CELERY_TASK_TRACK_STARTED,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
    worker_max_tasks_per_child=settings.CELERY_WORKER_MAX_TASKS_PER_CHILD,
    task_routes={
        "app.workers.tasks.create_accounts_task": {"queue": "normal"},
        "app.workers.tasks.health_check_proxies_task": {"queue": "low"},
        "app.workers.tasks.cleanup_old_logs_task": {"queue": "low"},
    },
    task_default_queue="normal",
    task_create_missing_queues=True,
    result_expires=3600,
    worker_send_task_events=True,
    task_send_sent_event=True,
)

celery_app.autodiscover_tasks(["app.workers"])

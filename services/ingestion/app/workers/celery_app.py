"""
Celery application configuration.
"""

import os
import sys

# Add shared module to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from celery import Celery

from app.config import settings

celery_app = Celery(
    "ingestion",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Performance
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    
    # Concurrency
    worker_concurrency=4,
    
    # Task routing
    task_routes={
        "app.workers.tasks.ingest_source": {"queue": "ingestion"},
        "app.workers.tasks.process_document": {"queue": "processing"},
        "app.workers.tasks.scheduled_sync": {"queue": "scheduling"},
    },
    
    # Result expiration
    result_expires=3600,  # 1 hour
    
    # Task limits
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3300,  # 55 minutes soft limit
    
    # Retry
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Beat schedule for periodic tasks
    beat_schedule={
        "sync-active-sources": {
            "task": "app.workers.tasks.scheduled_sync",
            "schedule": 300.0,  # Every 5 minutes
        },
        "cleanup-old-jobs": {
            "task": "app.workers.tasks.cleanup_old_jobs",
            "schedule": 86400.0,  # Daily
        },
    },
)

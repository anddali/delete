"""
Query API Service - FastAPI Application
"""

import os
import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add shared module to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.api import router as api_router
from shared.database.connection import session_manager

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(settings.LOG_LEVEL),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Query API service", version="1.0.0")
    
    # Initialize database
    session_manager.init(settings.DATABASE_URL)
    
    # Initialize Redis
    from app.services.cache import cache_service
    await cache_service.initialize()
    
    yield
    
    # Cleanup
    await session_manager.close()
    await cache_service.close()
    
    logger.info("Query API service stopped")


# Create FastAPI application
app = FastAPI(
    title="RAG Query API",
    description="Semantic search API with sliding window context retrieval",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router)


@app.get("/health")
async def health():
    """Basic health check."""
    return {"status": "healthy", "service": "query-api"}

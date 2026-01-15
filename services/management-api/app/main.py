"""
Management API Service - FastAPI Application
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
from app.api import auth, sources, tokens, jobs, dashboard, audit, system_settings, documents
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
    logger.info("Starting Management API service", version="1.0.0")
    
    # Initialize database
    session_manager.init(settings.DATABASE_URL)
    
    yield
    
    # Cleanup
    await session_manager.close()
    
    logger.info("Management API service stopped")


# Create FastAPI application
app = FastAPI(
    title="RAG Management API",
    description="Admin management API for the RAG Knowledge Indexing System",
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
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(sources.router, prefix="/sources", tags=["Sources"])
app.include_router(documents.router, prefix="/documents", tags=["Documents"])
app.include_router(tokens.router, prefix="/tokens", tags=["API Tokens"])
app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(audit.router, prefix="/audit", tags=["Audit"])
app.include_router(system_settings.router, prefix="/settings", tags=["Settings"])


@app.get("/health")
async def health():
    """Basic health check."""
    return {"status": "healthy", "service": "management-api"}

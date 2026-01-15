"""
Schemas for API request/response validation using Pydantic.
"""

from .auth import (
    LoginRequest,
    LoginResponse,
    TokenPayload,
    UserCreate,
    UserUpdate,
    UserResponse,
)
from .source import (
    SourceCreate,
    SourceUpdate,
    SourceResponse,
    SourceListResponse,
    ChunkingConfig,
    ConfluenceConfig,
    SlackConfig,
    FileUploadConfig,
)
from .token import (
    TokenCreate,
    TokenUpdate,
    TokenResponse,
    TokenListResponse,
    TokenScopes,
    TokenRateLimit,
)
from .job import (
    JobResponse,
    JobListResponse,
    JobProgress,
    JobResult,
    TriggerIngestionRequest,
)
from .search import (
    SearchRequest,
    SearchResponse,
    SearchResult,
    SearchFilters,
    SearchOptions,
    DocumentInfo,
)
from .common import (
    PaginatedResponse,
    HealthResponse,
    ErrorResponse,
)

__all__ = [
    # Auth
    "LoginRequest",
    "LoginResponse",
    "TokenPayload",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    # Source
    "SourceCreate",
    "SourceUpdate",
    "SourceResponse",
    "SourceListResponse",
    "ChunkingConfig",
    "ConfluenceConfig",
    "SlackConfig",
    "FileUploadConfig",
    # Token
    "TokenCreate",
    "TokenUpdate",
    "TokenResponse",
    "TokenListResponse",
    "TokenScopes",
    "TokenRateLimit",
    # Job
    "JobResponse",
    "JobListResponse",
    "JobProgress",
    "JobResult",
    "TriggerIngestionRequest",
    # Search
    "SearchRequest",
    "SearchResponse",
    "SearchResult",
    "SearchFilters",
    "SearchOptions",
    "DocumentInfo",
    # Common
    "PaginatedResponse",
    "HealthResponse",
    "ErrorResponse",
]

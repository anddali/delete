# Management API - Requirements & Features

## Overview
Administrative API for managing knowledge sources, tokens, users, and system configuration. Provides CRUD operations and control plane functionality for the RAG system.

## Core Responsibilities
- Source management (create, read, update, delete)
- Token generation and lifecycle management
- User and permission management
- Ingestion job control and monitoring
- System configuration and settings
- Audit logging and activity tracking

## Technology Stack
- **Runtime**: Python 3.11+
- **Framework**: FastAPI (async/await)
- **Database**: asyncpg + SQLAlchemy 2.0 (async)
- **Authentication**: JWT tokens
- **Password Hashing**: Argon2
- **Validation**: Pydantic v2

## Performance Requirements

### Latency Targets
- **CRUD Operations**: <100ms
- **Token Generation**: <200ms
- **List Operations**: <150ms
- **Bulk Operations**: <500ms for 100 items

### Optimization Strategies
- Database indexes on frequently queried fields
- Connection pooling (15 connections)
- Async I/O throughout
- Efficient pagination using keyset pagination
- Background tasks for non-critical operations

## Authentication & Authorization

### Admin User Model
```python
class AdminUser:
    id: UUID
    email: str
    password_hash: str  # Argon2
    full_name: str
    role: str  # admin, operator, viewer
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]
```

### Role-Based Access Control (RBAC)
```python
ROLES = {
    'admin': {
        'sources': ['create', 'read', 'update', 'delete'],
        'tokens': ['create', 'read', 'update', 'delete'],
        'users': ['create', 'read', 'update', 'delete'],
        'jobs': ['read', 'cancel'],
        'settings': ['read', 'update']
    },
    'operator': {
        'sources': ['read', 'update'],
        'tokens': ['create', 'read', 'update'],
        'users': ['read'],
        'jobs': ['read', 'cancel'],
        'settings': ['read']
    },
    'viewer': {
        'sources': ['read'],
        'tokens': ['read'],
        'users': ['read'],
        'jobs': ['read'],
        'settings': ['read']
    }
}
```

### JWT Authentication
```python
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.hash import argon2

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def create_access_token(user_id: str, role: str) -> str:
    """Create JWT access token"""
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using Argon2"""
    return argon2.verify(plain_password, hashed_password)

async def get_password_hash(password: str) -> str:
    """Hash password using Argon2"""
    return argon2.hash(password)
```

### Authentication Dependency
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db)
) -> AdminUser:
    """Validate JWT and return current user"""
    
    token = credentials.credentials
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    # Get user from database
    user = await get_user_by_id(db, user_id)
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    return user

def require_permission(resource: str, action: str):
    """Decorator to check permissions"""
    
    def decorator(func):
        async def wrapper(
            *args,
            current_user: AdminUser = Depends(get_current_user),
            **kwargs
        ):
            permissions = ROLES.get(current_user.role, {})
            allowed_actions = permissions.get(resource, [])
            
            if action not in allowed_actions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions for {action} on {resource}"
                )
            
            return await func(*args, current_user=current_user, **kwargs)
        
        return wrapper
    
    return decorator
```

## API Endpoints

### Authentication
```
POST /api/v1/auth/login
  - Body: {email, password}
  - Returns: {access_token, token_type, expires_in}

POST /api/v1/auth/refresh
  - Body: {refresh_token}
  - Returns: {access_token, token_type}

POST /api/v1/auth/logout
  - Invalidates current token

GET /api/v1/auth/me
  - Returns current user info
```

### User Management
```
POST /api/v1/users
  - Create new admin user
  - Requires: admin role

GET /api/v1/users
  - List all users with pagination
  - Query params: page, limit, role, search

GET /api/v1/users/{user_id}
  - Get user by ID

PATCH /api/v1/users/{user_id}
  - Update user (email, role, is_active)
  - Requires: admin role

DELETE /api/v1/users/{user_id}
  - Soft delete user
  - Requires: admin role

POST /api/v1/users/{user_id}/reset-password
  - Generate password reset token
  - Requires: admin role
```

### Source Management

#### Source Model
```python
class Source(BaseModel):
    id: UUID
    name: str
    type: str  # confluence, slack, file_upload
    description: Optional[str]
    config: Dict[str, Any]  # Plugin-specific configuration
    is_active: bool
    sync_frequency: str  # cron expression
    last_sync_at: Optional[datetime]
    next_sync_at: Optional[datetime]
    document_count: int
    created_by: UUID
    created_at: datetime
    updated_at: datetime
```

#### Endpoints
```
POST /api/v1/sources
  - Create new knowledge source
  - Body: {name, type, description, config, sync_frequency}
  - Triggers initial ingestion
  - Returns: Source object

GET /api/v1/sources
  - List all sources with pagination
  - Query params: page, limit, type, is_active, search
  - Returns: {items: [...], total, page, pages}

GET /api/v1/sources/{source_id}
  - Get source by ID
  - Includes: statistics, last sync status

PATCH /api/v1/sources/{source_id}
  - Update source configuration
  - Body: {name, description, config, sync_frequency, is_active}

DELETE /api/v1/sources/{source_id}
  - Delete source and all associated documents
  - Requires confirmation
  - Background job for cleanup

POST /api/v1/sources/{source_id}/sync
  - Trigger manual sync
  - Query param: full_sync (bool)
  - Returns: job_id

POST /api/v1/sources/{source_id}/test
  - Test source configuration
  - Validates credentials and connectivity
  - Returns: {valid: bool, error: Optional[str]}

GET /api/v1/sources/{source_id}/documents
  - List documents from source
  - Query params: page, limit, search

GET /api/v1/sources/{source_id}/stats
  - Get source statistics
  - Returns: {
      document_count,
      chunk_count,
      last_sync,
      sync_history: [...],
      error_count
    }
```

### Token Management

#### Token Model
```python
class APIToken(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    type: str  # query, admin, service
    token_hash: str  # Argon2 hash
    token_preview: str  # First 8 chars for display
    scopes: Dict[str, Any]
    rate_limit: Dict[str, int]
    is_active: bool
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    usage_count: int
    created_by: UUID
    created_at: datetime
```

#### Endpoints
```
POST /api/v1/tokens
  - Create new API token
  - Body: {
      name,
      description,
      type,
      scopes: {
        source_ids: [uuid1, uuid2],
        operations: ['read']
      },
      rate_limit: {
        per_minute: 100,
        per_day: 10000
      },
      expires_at: "2025-01-01T00:00:00Z"
    }
  - Returns: {token: "full_token", id: uuid, ...}
  - NOTE: Full token shown ONCE only

GET /api/v1/tokens
  - List all tokens with pagination
  - Query params: page, limit, type, is_active, created_by

GET /api/v1/tokens/{token_id}
  - Get token details (no full token)
  - Includes: usage statistics, last used

PATCH /api/v1/tokens/{token_id}
  - Update token (name, scopes, rate_limit, is_active)
  - Cannot change token type

DELETE /api/v1/tokens/{token_id}
  - Revoke token immediately

POST /api/v1/tokens/{token_id}/rotate
  - Generate new token, invalidate old one
  - Returns new full token

GET /api/v1/tokens/{token_id}/usage
  - Get usage statistics
  - Query params: start_date, end_date
  - Returns: {
      total_requests,
      requests_by_day: [...],
      top_queries: [...],
      error_rate
    }

GET /api/v1/tokens/{token_id}/audit-log
  - Get audit log for token usage
  - Paginated list of requests
```

### Job Management

#### Job Model
```python
class IngestionJob(BaseModel):
    id: UUID  # Celery task ID
    source_id: UUID
    type: str  # full_sync, incremental
    status: str  # pending, running, completed, failed, cancelled
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    progress: Dict[str, Any]  # {processed: int, total: Optional[int]}
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    created_by: UUID
    created_at: datetime
```

#### Endpoints
```
GET /api/v1/jobs
  - List ingestion jobs
  - Query params: page, limit, source_id, status, start_date, end_date
  - Sorted by created_at DESC

GET /api/v1/jobs/{job_id}
  - Get job details
  - Includes: real-time progress

POST /api/v1/jobs/{job_id}/cancel
  - Cancel running job
  - Requires: operator or admin role

GET /api/v1/jobs/stats
  - Get job statistics
  - Returns: {
      total_jobs,
      by_status: {...},
      average_duration,
      success_rate
    }
```

### Settings Management

#### System Settings
```python
class SystemSettings(BaseModel):
    # Embedding configuration
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    
    # Chunking configuration (defaults)
    default_chunk_size_chars: int = 1000
    default_respect_boundaries: bool = True
    default_min_chunk_size_chars: int = 200
    chunk_size_range: tuple = (500, 4000)  # Min, max allowed
    
    # Search configuration
    default_top_k: int = 10
    max_top_k: int = 100
    min_similarity_score: float = 0.7
    default_sliding_window: int = 0
    max_sliding_window: int = 3  # Maximum adjacent chunks to retrieve
    
    # Rate limiting defaults
    default_rate_limit_per_minute: int = 100
    default_rate_limit_per_day: int = 10000
    
    # Sync scheduling
    default_sync_frequency: str = "0 */6 * * *"  # Every 6 hours
    
    # Retention policies
    document_retention_days: Optional[int] = None
    audit_log_retention_days: int = 90
    job_log_retention_days: int = 30
```

#### Endpoints
```
GET /api/v1/settings
  - Get all system settings
  - Requires: operator or admin role

PATCH /api/v1/settings
  - Update system settings
  - Body: Partial settings object
  - Requires: admin role
  - Triggers background validation

POST /api/v1/settings/reset
  - Reset to default settings
  - Requires: admin role
```

### Analytics & Reporting

```
GET /api/v1/analytics/overview
  - System overview dashboard data
  - Returns: {
      total_sources,
      total_documents,
      total_chunks,
      total_tokens,
      active_tokens,
      storage_size_mb,
      last_7_days_queries
    }

GET /api/v1/analytics/sources
  - Per-source analytics
  - Returns: Array of source statistics

GET /api/v1/analytics/tokens
  - Token usage analytics
  - Query params: start_date, end_date
  - Returns: Usage trends by token

GET /api/v1/analytics/queries
  - Query analytics
  - Returns: {
      total_queries,
      queries_by_day,
      average_latency,
      cache_hit_rate,
      top_queries
    }
```

### Audit Logging

```
GET /api/v1/audit-logs
  - List audit log entries
  - Query params: page, limit, user_id, resource_type, action, start_date
  - Returns: Paginated audit logs

POST /api/v1/audit-logs/export
  - Export audit logs
  - Query params: start_date, end_date, format (csv, json)
  - Returns: Download link or file
```

## Source Configuration Schemas

### Confluence
```json
{
  "type": "confluence",
  "base_url": "https://company.atlassian.net",
  "space_keys": ["DOCS", "ENG"],
  "credentials": {
    "email": "user@company.com",
    "api_token": "encrypted_token"
  },
  "options": {
    "include_attachments": true,
    "include_archived": false,
    "max_page_size": 1000
  },
  "chunking": {
    "chunk_size_chars": 1000,
    "respect_boundaries": true,
    "min_chunk_size_chars": 200
  }
}
```

### Slack
```json
{
  "type": "slack",
  "workspace_id": "T1234567890",
  "channel_ids": ["C1234567890", "C0987654321"],
  "credentials": {
    "bot_token": "xoxb-encrypted"
  },
  "options": {
    "include_threads": true,
    "include_files": true,
    "min_message_length": 10,
    "max_age_days": 365
  },
  "chunking": {
    "chunk_size_chars": 800,
    "respect_boundaries": true,
    "min_chunk_size_chars": 150
  }
}
```

### File Upload
```json
{
  "type": "file_upload",
  "storage": {
    "type": "s3",
    "bucket": "rag-knowledge-uploads",
    "prefix": "uploads/",
    "region": "us-east-1"
  },
  "processing": {
    "max_file_size_mb": 100,
    "allowed_extensions": [".pdf", ".docx", ".txt", ".md"],
    "ocr_enabled": false
  },
  "chunking": {
    "chunk_size_chars": 1200,
    "respect_boundaries": true,
    "min_chunk_size_chars": 250
  }
}
```

## Configuration Validation

### Plugin Config Validator
```python
from pydantic import BaseModel, validator
from typing import Dict, Any

class ConfluenceConfig(BaseModel):
    base_url: str
    space_keys: List[str]
    credentials: Dict[str, str]
    options: Dict[str, Any] = {}
    
    @validator('base_url')
    def validate_url(cls, v):
        if not v.startswith('https://'):
            raise ValueError('base_url must use HTTPS')
        return v
    
    @validator('space_keys')
    def validate_space_keys(cls, v):
        if not v:
            raise ValueError('At least one space key required')
        return v

CONFIG_VALIDATORS = {
    'confluence': ConfluenceConfig,
    'slack': SlackConfig,
    'file_upload': FileUploadConfig
}

async def validate_source_config(source_type: str, config: Dict) -> None:
    """Validate source configuration"""
    
    validator = CONFIG_VALIDATORS.get(source_type)
    if not validator:
        raise ValueError(f"Unknown source type: {source_type}")
    
    try:
        validated = validator(**config)
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid configuration: {e.errors()}"
        )
    
    # Test connection
    plugin = get_plugin(source_type, validated.dict())
    
    try:
        is_valid = await plugin.validate_config()
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail="Failed to validate credentials or connectivity"
            )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Configuration test failed: {str(e)}"
        )
```

## Credential Encryption

### Encryption Utilities
```python
from cryptography.fernet import Fernet
import base64

ENCRYPTION_KEY = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
cipher = Fernet(ENCRYPTION_KEY)

def encrypt_credential(plain_text: str) -> str:
    """Encrypt sensitive credential"""
    encrypted = cipher.encrypt(plain_text.encode())
    return base64.b64encode(encrypted).decode()

def decrypt_credential(encrypted_text: str) -> str:
    """Decrypt credential"""
    encrypted = base64.b64decode(encrypted_text.encode())
    decrypted = cipher.decrypt(encrypted)
    return decrypted.decode()

# Automatic encryption for source configs
async def store_source_config(config: Dict) -> Dict:
    """Encrypt credentials in config before storage"""
    
    if 'credentials' in config:
        encrypted_creds = {}
        for key, value in config['credentials'].items():
            encrypted_creds[key] = encrypt_credential(value)
        
        config['credentials'] = encrypted_creds
    
    return config

async def load_source_config(config: Dict) -> Dict:
    """Decrypt credentials when loading config"""
    
    if 'credentials' in config:
        decrypted_creds = {}
        for key, value in config['credentials'].items():
            decrypted_creds[key] = decrypt_credential(value)
        
        config['credentials'] = decrypted_creds
    
    return config
```

## Pagination Implementation

### Keyset Pagination (Efficient for Large Datasets)
```python
from typing import Optional, List, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    pages: int
    has_next: bool
    has_prev: bool

async def paginate_query(
    query: Select,
    page: int = 1,
    limit: int = 20,
    max_limit: int = 100
) -> PaginatedResponse:
    """Efficient offset-based pagination"""
    
    # Enforce max limit
    limit = min(limit, max_limit)
    
    # Get total count (cached for 1 minute)
    count_query = select(func.count()).select_from(query.alias())
    total = await db.scalar(count_query)
    
    # Calculate offset
    offset = (page - 1) * limit
    
    # Get page items
    paginated_query = query.offset(offset).limit(limit)
    result = await db.execute(paginated_query)
    items = result.fetchall()
    
    # Calculate metadata
    pages = (total + limit - 1) // limit
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1
    )
```

## Audit Logging

### Audit Log Model
```python
class AuditLog(BaseModel):
    id: UUID
    user_id: UUID
    user_email: str
    action: str  # create, update, delete, read
    resource_type: str  # source, token, user, job
    resource_id: Optional[UUID]
    resource_name: Optional[str]
    changes: Optional[Dict[str, Any]]  # Before/after values
    ip_address: str
    user_agent: str
    status: str  # success, failure
    error: Optional[str]
    created_at: datetime
```

### Audit Logging Decorator
```python
from functools import wraps
import inspect

def audit_log(resource_type: str, action: str):
    """Decorator to automatically log actions"""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user and request from args
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            
            user = bound_args.arguments.get('current_user')
            request = bound_args.arguments.get('request')
            
            start_time = time.time()
            error = None
            status = 'success'
            
            try:
                result = await func(*args, **kwargs)
                return result
            
            except Exception as e:
                error = str(e)
                status = 'failure'
                raise
            
            finally:
                # Log action
                if user and request:
                    await create_audit_log(
                        user_id=user.id,
                        user_email=user.email,
                        action=action,
                        resource_type=resource_type,
                        resource_id=bound_args.arguments.get('id'),
                        ip_address=request.client.host,
                        user_agent=request.headers.get('user-agent'),
                        status=status,
                        error=error,
                        duration_ms=(time.time() - start_time) * 1000
                    )
        
        return wrapper
    
    return decorator

# Usage
@router.post("/api/v1/sources")
@audit_log(resource_type='source', action='create')
async def create_source(
    source_data: SourceCreate,
    current_user: AdminUser = Depends(get_current_user),
    request: Request = None
):
    # ... implementation
    pass
```

## Background Tasks

### Celery Integration
```python
from celery import Celery

celery_app = Celery('management')

@celery_app.task
async def cleanup_deleted_sources(source_id: str):
    """Background cleanup of deleted source data"""
    
    # Delete all documents
    await delete_documents_by_source(source_id)
    
    # Delete all chunks and embeddings
    await delete_chunks_by_source(source_id)
    
    # Remove from audit logs (optional, based on retention)
    # await cleanup_audit_logs(source_id)

@celery_app.task
async def generate_analytics_report(start_date: str, end_date: str):
    """Generate periodic analytics report"""
    
    report = {
        'period': {'start': start_date, 'end': end_date},
        'sources': await get_source_stats(start_date, end_date),
        'tokens': await get_token_stats(start_date, end_date),
        'queries': await get_query_stats(start_date, end_date)
    }
    
    # Store report
    await save_analytics_report(report)
    
    return report
```

## Error Handling

### Custom Exceptions
```python
class ManagementAPIException(Exception):
    """Base exception"""
    pass

class SourceNotFoundError(ManagementAPIException):
    status_code = 404
    detail = "Source not found"

class TokenNotFoundError(ManagementAPIException):
    status_code = 404
    detail = "Token not found"

class InvalidConfigurationError(ManagementAPIException):
    status_code = 400
    detail = "Invalid configuration"

class DuplicateResourceError(ManagementAPIException):
    status_code = 409
    detail = "Resource already exists"
```

## Monitoring

### Metrics
```python
from prometheus_client import Counter, Histogram

api_requests = Counter(
    'management_api_requests_total',
    'Total API requests',
    ['endpoint', 'method', 'status']
)

api_duration = Histogram(
    'management_api_duration_seconds',
    'Request duration',
    ['endpoint', 'method']
)

sources_count = Gauge(
    'management_sources_total',
    'Total number of sources'
)

active_tokens_count = Gauge(
    'management_active_tokens',
    'Number of active API tokens'
)
```

## Configuration

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/ragdb

# JWT
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Encryption
CREDENTIAL_ENCRYPTION_KEY=your-encryption-key

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# CORS
ALLOWED_ORIGINS=http://localhost:3000,https://app.company.com

# Monitoring
LOG_LEVEL=INFO
```

## File Structure
```
services/management-api/
├── Dockerfile
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── sources.py
│   │   │   ├── tokens.py
│   │   │   ├── jobs.py
│   │   │   ├── settings.py
│   │   │   ├── analytics.py
│   │   │   └── audit.py
│   │   └── dependencies.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── source.py
│   │   ├── token.py
│   │   ├── job.py
│   │   └── audit.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── source.py
│   │   ├── token.py
│   │   └── encryption.py
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   └── audit.py
│   └── utils/
│       ├── __init__.py
│       ├── pagination.py
│       └── validation.py
└── tests/
    ├── unit/
    └── integration/
```

## Dependencies
```
# Core
fastapi==0.109.0
uvicorn[standard]==0.27.0

# Database
sqlalchemy[asyncio]==2.0.25
asyncpg==0.29.0

# Authentication
python-jose[cryptography]==3.3.0
passlib[argon2]==1.7.4

# Encryption
cryptography==42.0.0

# Background tasks
celery==5.3.6
redis==5.0.1

# Utilities
pydantic==2.5.3
pydantic-settings==2.1.0

# Monitoring
structlog==24.1.0
prometheus-client==0.19.0
```

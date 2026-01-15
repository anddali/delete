# Environment Configuration

## .env.example

Copy this file to `.env` and fill in the appropriate values for your environment.

```bash
#############################################
# ENVIRONMENT
#############################################
ENVIRONMENT=production  # development, staging, production

#############################################
# DATABASE CONFIGURATION
#############################################
# Primary database (read/write)
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname

# Read replica (optional, for query API)
DATABASE_READ_REPLICA_URL=postgresql+asyncpg://user:password@replica-host:5432/dbname

# Database pool settings
DATABASE_POOL_SIZE=25
DATABASE_MAX_OVERFLOW=10

#############################################
# REDIS CONFIGURATION
#############################################
REDIS_URL=redis://redis:6379/0
REDIS_MAX_CONNECTIONS=50

#############################################
# SECURITY & AUTHENTICATION
#############################################
# JWT Configuration
JWT_SECRET_KEY=  # Generate with: openssl rand -hex 32
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# Credential encryption
CREDENTIAL_ENCRYPTION_KEY=  # Generate with: openssl rand -base64 32

#############################################
# OPENAI CONFIGURATION
#############################################
OPENAI_API_KEY=sk-...
OPENAI_ORG_ID=org-...
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536

#############################################
# AWS CONFIGURATION
#############################################
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...

# S3 Configuration
S3_BUCKET=rag-knowledge-uploads
S3_ENDPOINT=  # Leave empty for AWS S3, set for MinIO in dev

#############################################
# CELERY CONFIGURATION
#############################################
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

#############################################
# APPLICATION SETTINGS
#############################################
# CORS
ALLOWED_ORIGINS=https://admin.your-domain.com,https://your-domain.com

# API URLs
NEXT_PUBLIC_API_URL=https://api.your-domain.com
NEXT_PUBLIC_APP_NAME=RAG Knowledge Admin

#############################################
# PERFORMANCE TUNING
#############################################
# Ingestion settings
MAX_WORKERS=5
BATCH_SIZE=100
EMBEDDING_BATCH_SIZE=100

# Caching settings (seconds)
QUERY_CACHE_TTL=900          # 15 minutes
EMBEDDING_CACHE_TTL=3600     # 1 hour
TOKEN_CACHE_TTL=300          # 5 minutes

# Search settings
SEARCH_TIMEOUT_SECONDS=5
MAX_RESULTS_PER_QUERY=100

#############################################
# MONITORING & LOGGING
#############################################
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Sentry (optional)
SENTRY_DSN=

# Prometheus (optional)
METRICS_ENABLED=true

# Grafana (optional)
GRAFANA_ADMIN_PASSWORD=admin

#############################################
# RATE LIMITING DEFAULTS
#############################################
DEFAULT_RATE_LIMIT_PER_MINUTE=100
DEFAULT_RATE_LIMIT_PER_DAY=10000

#############################################
# DATA RETENTION
#############################################
DOCUMENT_RETENTION_DAYS=  # Leave empty for no limit
AUDIT_LOG_RETENTION_DAYS=90
JOB_LOG_RETENTION_DAYS=30
QUERY_LOG_RETENTION_DAYS=30
```

## Development Environment (.env.dev)

```bash
ENVIRONMENT=development

# Local PostgreSQL
DATABASE_URL=postgresql+asyncpg://raguser:ragpassword@postgres:5432/ragdb
DATABASE_READ_REPLICA_URL=postgresql+asyncpg://raguser:ragpassword@postgres:5432/ragdb

# Local Redis
REDIS_URL=redis://redis:6379/0

# Security (dev keys - DO NOT USE IN PRODUCTION)
JWT_SECRET_KEY=dev-secret-key-change-in-production-use-openssl-rand-hex-32
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480  # 8 hours for dev convenience
CREDENTIAL_ENCRYPTION_KEY=dev-encryption-key-32-chars!!

# OpenAI (use your own key)
OPENAI_API_KEY=sk-...
OPENAI_ORG_ID=org-...

# Local MinIO (S3-compatible)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET=rag-uploads
S3_ENDPOINT=http://minio:9000

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# CORS (allow localhost)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8001

# API URLs
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_APP_NAME=RAG Knowledge Admin (Dev)

# Reduced workers for dev
MAX_WORKERS=2
BATCH_SIZE=50
EMBEDDING_BATCH_SIZE=50

# Shorter cache TTLs for testing
QUERY_CACHE_TTL=60
EMBEDDING_CACHE_TTL=300
TOKEN_CACHE_TTL=60

# Logging
LOG_LEVEL=DEBUG
METRICS_ENABLED=false

# Rate limiting (relaxed for dev)
DEFAULT_RATE_LIMIT_PER_MINUTE=1000
DEFAULT_RATE_LIMIT_PER_DAY=100000
```

## Staging Environment (.env.staging)

```bash
ENVIRONMENT=staging

# Staging database
DATABASE_URL=postgresql+asyncpg://staginguser:password@staging-db.xxxxx.rds.amazonaws.com:5432/ragdb_staging
DATABASE_READ_REPLICA_URL=postgresql+asyncpg://staginguser:password@staging-db-replica.xxxxx.rds.amazonaws.com:5432/ragdb_staging

# Staging Redis
REDIS_URL=redis://staging-redis.xxxxx.cache.amazonaws.com:6379/0

# Security
JWT_SECRET_KEY=  # Use AWS Secrets Manager
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
CREDENTIAL_ENCRYPTION_KEY=  # Use AWS Secrets Manager

# OpenAI
OPENAI_API_KEY=  # Separate staging key
OPENAI_ORG_ID=org-...

# AWS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=  # IAM role preferred
AWS_SECRET_ACCESS_KEY=
S3_BUCKET=rag-knowledge-uploads-staging

# Celery
CELERY_BROKER_URL=redis://staging-redis.xxxxx.cache.amazonaws.com:6379/0
CELERY_RESULT_BACKEND=redis://staging-redis.xxxxx.cache.amazonaws.com:6379/0

# CORS
ALLOWED_ORIGINS=https://staging-admin.your-domain.com

# API URLs
NEXT_PUBLIC_API_URL=https://staging-api.your-domain.com
NEXT_PUBLIC_APP_NAME=RAG Knowledge Admin (Staging)

# Performance settings
MAX_WORKERS=3
BATCH_SIZE=100
EMBEDDING_BATCH_SIZE=100

# Caching
QUERY_CACHE_TTL=600          # 10 minutes
EMBEDDING_CACHE_TTL=1800     # 30 minutes
TOKEN_CACHE_TTL=300

# Logging
LOG_LEVEL=INFO
SENTRY_DSN=https://...@sentry.io/staging

# Rate limiting
DEFAULT_RATE_LIMIT_PER_MINUTE=100
DEFAULT_RATE_LIMIT_PER_DAY=10000
```

## Production Environment (.env.prod)

```bash
ENVIRONMENT=production

# Production database (use AWS Secrets Manager for credentials)
DATABASE_URL=postgresql+asyncpg://produser:${DB_PASSWORD}@prod-db.xxxxx.rds.amazonaws.com:5432/ragdb
DATABASE_READ_REPLICA_URL=postgresql+asyncpg://produser:${DB_PASSWORD}@prod-db-replica.xxxxx.rds.amazonaws.com:5432/ragdb
DATABASE_POOL_SIZE=25
DATABASE_MAX_OVERFLOW=10

# Production Redis (ElastiCache)
REDIS_URL=redis://prod-redis.xxxxx.cache.amazonaws.com:6379/0
REDIS_MAX_CONNECTIONS=50

# Security (NEVER commit these values - use AWS Secrets Manager)
JWT_SECRET_KEY=${JWT_SECRET_FROM_SECRETS_MANAGER}
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
CREDENTIAL_ENCRYPTION_KEY=${ENCRYPTION_KEY_FROM_SECRETS_MANAGER}

# OpenAI
OPENAI_API_KEY=${OPENAI_KEY_FROM_SECRETS_MANAGER}
OPENAI_ORG_ID=org-...
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536

# AWS (use IAM roles instead of keys when possible)
AWS_REGION=us-east-1
S3_BUCKET=rag-knowledge-uploads-prod

# Celery
CELERY_BROKER_URL=redis://prod-redis.xxxxx.cache.amazonaws.com:6379/0
CELERY_RESULT_BACKEND=redis://prod-redis.xxxxx.cache.amazonaws.com:6379/0

# CORS
ALLOWED_ORIGINS=https://admin.your-domain.com,https://www.your-domain.com

# API URLs
NEXT_PUBLIC_API_URL=https://api.your-domain.com
NEXT_PUBLIC_APP_NAME=RAG Knowledge Admin

# Performance settings (optimized for production)
MAX_WORKERS=5
BATCH_SIZE=100
EMBEDDING_BATCH_SIZE=100

# Caching (longer TTLs for production)
QUERY_CACHE_TTL=900          # 15 minutes
EMBEDDING_CACHE_TTL=3600     # 1 hour
TOKEN_CACHE_TTL=300          # 5 minutes

# Search settings
SEARCH_TIMEOUT_SECONDS=5
MAX_RESULTS_PER_QUERY=100

# Monitoring
LOG_LEVEL=INFO
SENTRY_DSN=https://...@sentry.io/production
METRICS_ENABLED=true

# Rate limiting (production limits)
DEFAULT_RATE_LIMIT_PER_MINUTE=100
DEFAULT_RATE_LIMIT_PER_DAY=10000

# Data retention
DOCUMENT_RETENTION_DAYS=  # No limit
AUDIT_LOG_RETENTION_DAYS=90
JOB_LOG_RETENTION_DAYS=30
QUERY_LOG_RETENTION_DAYS=30
```

## Environment-Specific Configuration Files

### docker-compose.override.yml (for local overrides)

```yaml
version: '3.8'

services:
  management-api:
    volumes:
      - ./services/management-api/app:/app/app:ro
    environment:
      - DEBUG=true

  query-api:
    volumes:
      - ./services/query-api/app:/app/app:ro
    environment:
      - DEBUG=true
```

### .dockerignore

```
# Git
.git
.gitignore

# Environment
.env
.env.*
!.env.example

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
*.egg-info/

# Node
node_modules/
.next/
npm-debug.log*

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Documentation
docs/
*.md
!README.md

# Tests
tests/
*.test.js
*.spec.ts

# Logs
*.log
logs/

# Temporary files
tmp/
temp/
```

## AWS Secrets Manager Integration

### Store secrets in AWS Secrets Manager:

```bash
# Create secret
aws secretsmanager create-secret \
  --name rag-knowledge/production \
  --description "Production secrets for RAG Knowledge System" \
  --secret-string '{
    "DATABASE_PASSWORD": "your-db-password",
    "JWT_SECRET_KEY": "your-jwt-secret",
    "CREDENTIAL_ENCRYPTION_KEY": "your-encryption-key",
    "OPENAI_API_KEY": "sk-your-openai-key"
  }'
```

### Retrieve secrets in startup script:

```bash
#!/bin/bash
# scripts/load-secrets.sh

SECRET_NAME="rag-knowledge/production"
REGION="us-east-1"

# Retrieve secret
SECRET_JSON=$(aws secretsmanager get-secret-value \
  --secret-id $SECRET_NAME \
  --region $REGION \
  --query SecretString \
  --output text)

# Parse and export
export DATABASE_PASSWORD=$(echo $SECRET_JSON | jq -r '.DATABASE_PASSWORD')
export JWT_SECRET_KEY=$(echo $SECRET_JSON | jq -r '.JWT_SECRET_KEY')
export CREDENTIAL_ENCRYPTION_KEY=$(echo $SECRET_JSON | jq -r '.CREDENTIAL_ENCRYPTION_KEY')
export OPENAI_API_KEY=$(echo $SECRET_JSON | jq -r '.OPENAI_API_KEY')

# Load remaining config from .env
set -a
source .env
set +a

# Start services
docker-compose up -d
```

## Configuration Validation

### Validate configuration before deployment:

```python
# scripts/validate_config.py
import os
import sys
from typing import List, Tuple

def validate_env() -> Tuple[bool, List[str]]:
    """Validate all required environment variables"""
    required_vars = [
        'DATABASE_URL',
        'REDIS_URL',
        'JWT_SECRET_KEY',
        'CREDENTIAL_ENCRYPTION_KEY',
        'OPENAI_API_KEY',
        'S3_BUCKET',
    ]
    
    errors = []
    
    for var in required_vars:
        if not os.getenv(var):
            errors.append(f"Missing required environment variable: {var}")
    
    # Validate JWT secret length
    jwt_secret = os.getenv('JWT_SECRET_KEY', '')
    if len(jwt_secret) < 32:
        errors.append("JWT_SECRET_KEY must be at least 32 characters")
    
    # Validate encryption key
    encryption_key = os.getenv('CREDENTIAL_ENCRYPTION_KEY', '')
    if len(encryption_key) != 44:  # Base64 encoded 32 bytes
        errors.append("CREDENTIAL_ENCRYPTION_KEY must be 44 characters (base64 encoded 32 bytes)")
    
    return len(errors) == 0, errors

if __name__ == '__main__':
    valid, errors = validate_env()
    
    if not valid:
        print("❌ Configuration validation failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    
    print("✅ Configuration validation passed")
```

Run validation:
```bash
python scripts/validate_config.py
```

## Security Best Practices

1. **Never commit secrets to Git**
   - Use `.env` files (add to `.gitignore`)
   - Use AWS Secrets Manager for production
   - Rotate secrets regularly

2. **Use strong secrets**
   ```bash
   # Generate JWT secret
   openssl rand -hex 32
   
   # Generate encryption key
   openssl rand -base64 32
   
   # Generate passwords
   openssl rand -base64 24
   ```

3. **Restrict access**
   - Use IAM roles instead of access keys
   - Limit security group access
   - Enable VPC for RDS

4. **Enable encryption**
   - RDS encryption at rest
   - S3 bucket encryption
   - SSL/TLS for all connections

5. **Monitor and audit**
   - Enable CloudWatch logs
   - Set up CloudTrail
   - Review audit logs regularly

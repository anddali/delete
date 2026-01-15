# Management API Service

Admin management API for the RAG Knowledge Indexing System.

## Features

- **Admin Authentication**: JWT-based authentication with RBAC (Super Admin, Editor, Viewer)
- **Source Management**: Full CRUD for knowledge sources
- **Token Management**: Create, revoke, and scope API tokens
- **Job Monitoring**: View ingestion job status and history
- **Audit Logging**: Track all administrative actions
- **System Settings**: Manage global configuration

## API Endpoints

### Authentication

- `POST /auth/login` - Admin login
- `POST /auth/logout` - Logout and invalidate session
- `GET /auth/me` - Get current user info
- `PUT /auth/password` - Change password

### Sources

- `GET /sources` - List all sources
- `POST /sources` - Create new source
- `GET /sources/{id}` - Get source details
- `PUT /sources/{id}` - Update source
- `DELETE /sources/{id}` - Delete source (soft delete)
- `POST /sources/{id}/sync` - Trigger sync
- `POST /sources/{id}/test` - Test connection

### API Tokens

- `GET /tokens` - List API tokens
- `POST /tokens` - Create new token
- `GET /tokens/{id}` - Get token details
- `PUT /tokens/{id}` - Update token
- `DELETE /tokens/{id}` - Revoke token

### Jobs

- `GET /jobs` - List ingestion jobs
- `GET /jobs/{id}` - Get job details
- `POST /jobs/{id}/cancel` - Cancel job

### Dashboard

- `GET /dashboard/stats` - System statistics
- `GET /dashboard/activity` - Recent activity

### Audit

- `GET /audit` - Audit log entries

### Settings

- `GET /settings` - Get system settings
- `PUT /settings` - Update settings

## Running Locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

## Docker

```bash
docker build -t management-api .
docker run -p 8002:8002 --env-file .env management-api
```

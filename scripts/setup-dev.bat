@echo off
REM Setup script for development environment (Windows)
REM Run this script to initialize the development environment

echo 🚀 Setting up RAG Knowledge Indexing System development environment...

REM Check Docker
where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker is not installed. Please install Docker first.
    exit /b 1
)

echo ✅ Docker is installed

REM Create .env file if it doesn't exist
if not exist .env (
    echo 📝 Creating .env file from template...
    copy .env.example .env
    echo ⚠️  Please update .env with your OpenAI API key
)

REM Create necessary directories
echo 📁 Creating necessary directories...
if not exist nginx\ssl mkdir nginx\ssl
if not exist monitoring\grafana\dashboards mkdir monitoring\grafana\dashboards
if not exist monitoring\grafana\datasources mkdir monitoring\grafana\datasources

REM Start infrastructure services
echo 🐳 Starting infrastructure services (PostgreSQL, Redis, MinIO)...
docker compose -f docker-compose.dev.yml up -d postgres redis minio

REM Wait for PostgreSQL to be ready
echo ⏳ Waiting for PostgreSQL to be ready...
:wait_postgres
docker compose -f docker-compose.dev.yml exec -T postgres pg_isready -U raguser -d ragdb >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    timeout /t 2 /nobreak >nul
    goto wait_postgres
)

echo ✅ PostgreSQL is ready

REM Run database migrations
echo 🔄 Running database migrations...
docker compose -f docker-compose.dev.yml run --rm management-api python -m alembic upgrade head

REM Create default admin user
echo 👤 Creating default admin user...
docker compose -f docker-compose.dev.yml run --rm management-api python /app/scripts/create-admin.py --email admin@example.com --password admin123! --name "Default Admin"

REM Start all services
echo 🚀 Starting all services...
docker compose -f docker-compose.dev.yml up -d

echo.
echo ✅ Development environment is ready!
echo.
echo 📍 Service URLs:
echo    Admin UI:       http://localhost:3000
echo    Management API: http://localhost:8001
echo    Query API:      http://localhost:8002
echo    Ingestion API:  http://localhost:8003
echo    MinIO Console:  http://localhost:9001
echo.
echo 🔐 Default admin credentials:
echo    Email:    admin@example.com
echo    Password: admin123!
echo.
echo 📊 Optional tools (start with: docker compose -f docker-compose.dev.yml --profile tools up -d):
echo    pgAdmin:         http://localhost:5050
echo    Redis Commander: http://localhost:8081
echo    Flower:          http://localhost:5555
echo.

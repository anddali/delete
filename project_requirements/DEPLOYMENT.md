# Deployment Guide

## Overview
This guide covers deploying the RAG Knowledge Indexing System to AWS EC2 with RDS PostgreSQL using Docker Compose.

## Prerequisites

### Local Requirements
- Docker 24.0+
- Docker Compose 2.20+
- Git
- AWS CLI configured

### AWS Requirements
- AWS Account with appropriate permissions
- EC2 instance (recommended: t3.xlarge or larger)
- RDS PostgreSQL 15+ instance with pgvector extension
- S3 bucket for file uploads
- Security groups configured

## Architecture

```
┌─────────────────────────────────────────┐
│             CloudWatch                  │
│         (Logs & Metrics)               │
└─────────────────────────────────────────┘
                    ▲
                    │
┌───────────────────┴─────────────────────┐
│          EC2 Instance (Docker)          │
│  ┌──────────────────────────────────┐   │
│  │  Nginx (80/443)                  │   │
│  └────┬──────────────────────┬──────┘   │
│       │                      │          │
│  ┌────▼─────────┐      ┌────▼──────┐   │
│  │ Admin UI     │      │ Query API │   │
│  │ (Next.js)    │      │ (x2)      │   │
│  └──────────────┘      └───────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │  Management API                 │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │  Ingestion Service              │   │
│  │  - API                          │   │
│  │  - Workers (x2)                 │   │
│  │  - Beat Scheduler               │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │  Redis (Cache/Queue)            │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
┌───────▼──────────┐   ┌────────▼────────┐
│  RDS PostgreSQL  │   │   S3 Bucket     │
│  + pgvector      │   │  (File Upload)  │
└──────────────────┘   └─────────────────┘
```

## Step 1: Provision AWS Resources

### 1.1 Create RDS PostgreSQL Instance

```bash
aws rds create-db-instance \
  --db-instance-identifier rag-knowledge-db \
  --db-instance-class db.t3.large \
  --engine postgres \
  --engine-version 15.4 \
  --master-username ragadmin \
  --master-user-password <STRONG_PASSWORD> \
  --allocated-storage 100 \
  --storage-type gp3 \
  --storage-encrypted \
  --backup-retention-period 7 \
  --vpc-security-group-ids sg-xxxxx \
  --db-subnet-group-name rag-db-subnet \
  --multi-az \
  --publicly-accessible false
```

### 1.2 Enable pgvector Extension

Connect to RDS and run:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;
```

### 1.3 Create Read Replica (Optional but Recommended)

```bash
aws rds create-db-instance-read-replica \
  --db-instance-identifier rag-knowledge-db-replica \
  --source-db-instance-identifier rag-knowledge-db \
  --db-instance-class db.t3.large
```

### 1.4 Create S3 Bucket

```bash
aws s3 mb s3://rag-knowledge-uploads --region us-east-1
```

### 1.5 Launch EC2 Instance

```bash
# Create security group
aws ec2 create-security-group \
  --group-name rag-app-sg \
  --description "Security group for RAG application"

# Add inbound rules
aws ec2 authorize-security-group-ingress \
  --group-name rag-app-sg \
  --protocol tcp --port 22 --cidr 0.0.0.0/0  # SSH
aws ec2 authorize-security-group-ingress \
  --group-name rag-app-sg \
  --protocol tcp --port 80 --cidr 0.0.0.0/0  # HTTP
aws ec2 authorize-security-group-ingress \
  --group-name rag-app-sg \
  --protocol tcp --port 443 --cidr 0.0.0.0/0  # HTTPS

# Launch instance
aws ec2 run-instances \
  --image-id ami-xxxxx \  # Ubuntu 22.04 LTS
  --instance-type t3.xlarge \
  --key-name your-key-pair \
  --security-group-ids sg-xxxxx \
  --subnet-id subnet-xxxxx \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":100,"VolumeType":"gp3"}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=rag-knowledge-app}]'
```

## Step 2: Configure EC2 Instance

### 2.1 SSH into Instance

```bash
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>
```

### 2.2 Install Docker

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

### 2.3 Configure System Limits

```bash
# Increase file descriptor limits
sudo tee -a /etc/security/limits.conf << EOF
* soft nofile 65536
* hard nofile 65536
EOF

# Increase max connections
sudo tee -a /etc/sysctl.conf << EOF
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 2048
vm.overcommit_memory = 1
EOF

sudo sysctl -p
```

## Step 3: Deploy Application

### 3.1 Clone Repository

```bash
git clone https://github.com/yourorg/rag-knowledge-system.git
cd rag-knowledge-system
```

### 3.2 Create Environment Configuration

```bash
cp .env.example .env
```

Edit `.env`:
```bash
# Database
DATABASE_URL=postgresql+asyncpg://ragadmin:<PASSWORD>@rag-knowledge-db.xxxxx.us-east-1.rds.amazonaws.com:5432/ragdb
DATABASE_READ_REPLICA_URL=postgresql+asyncpg://ragadmin:<PASSWORD>@rag-knowledge-db-replica.xxxxx.us-east-1.rds.amazonaws.com:5432/ragdb

# Security
JWT_SECRET_KEY=<GENERATE_STRONG_KEY>  # openssl rand -hex 32
CREDENTIAL_ENCRYPTION_KEY=<GENERATE_32_CHAR_KEY>  # openssl rand -base64 32

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_ORG_ID=org-...

# AWS
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
S3_BUCKET=rag-knowledge-uploads

# Application
ALLOWED_ORIGINS=https://your-domain.com
NEXT_PUBLIC_API_URL=https://api.your-domain.com

# Monitoring (optional)
GRAFANA_ADMIN_PASSWORD=<SECURE_PASSWORD>
```

### 3.3 Initialize Database

```bash
# Run migrations
docker-compose -f docker-compose.yml run --rm management-api alembic upgrade head

# Create initial admin user
docker-compose -f docker-compose.yml run --rm management-api python -m app.scripts.create_admin \
  --email admin@your-domain.com \
  --password <SECURE_PASSWORD> \
  --name "Admin User"
```

### 3.4 Start Services

```bash
# Pull images
docker-compose pull

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 3.5 Verify Deployment

```bash
# Check health endpoints
curl http://localhost/health
curl http://localhost/api/management/health
curl http://localhost/api/query/health

# Check specific services
docker-compose logs management-api
docker-compose logs query-api
docker-compose logs ingestion-api
```

## Step 4: Configure Nginx

### 4.1 SSL Certificate

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx -y

# Obtain certificate
sudo certbot --nginx -d your-domain.com -d api.your-domain.com
```

### 4.2 Nginx Configuration

Create `nginx/nginx.conf`:
```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 2048;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    'rt=$request_time uct="$upstream_connect_time" '
                    'uht="$upstream_header_time" urt="$upstream_response_time"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 100M;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript 
               application/json application/javascript application/xml+rss;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/s;
    limit_req_zone $binary_remote_addr zone=query_limit:10m rate=200r/s;

    # Upstream definitions
    upstream management_api {
        least_conn;
        server management-api:8000 max_fails=3 fail_timeout=30s;
    }

    upstream query_api {
        least_conn;
        server query-api-1:8000 max_fails=3 fail_timeout=30s;
        server query-api-2:8000 max_fails=3 fail_timeout=30s;
    }

    upstream admin_ui {
        server admin-ui:3000 max_fails=3 fail_timeout=30s;
    }

    # Admin UI
    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        location / {
            proxy_pass http://admin_ui;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_cache_bypass $http_upgrade;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }

    # API Gateway
    server {
        listen 80;
        server_name api.your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name api.your-domain.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # Management API
        location /api/v1/management {
            limit_req zone=api_limit burst=20 nodelay;
            
            proxy_pass http://management_api;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            proxy_connect_timeout 5s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # Query API
        location /api/v1/search {
            limit_req zone=query_limit burst=50 nodelay;
            
            proxy_pass http://query_api;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            proxy_connect_timeout 2s;
            proxy_send_timeout 10s;
            proxy_read_timeout 10s;
            
            # Enable caching for GET requests
            proxy_cache_methods GET;
            proxy_cache_valid 200 5m;
        }

        # Health checks
        location /health {
            access_log off;
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }
    }
}
```

## Step 5: Monitoring & Logging

### 5.1 CloudWatch Logging

Install CloudWatch agent:
```bash
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i -E ./amazon-cloudwatch-agent.deb

# Configure agent
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard
```

Configure Docker logging driver:
```yaml
# In docker-compose.yml, add to each service:
logging:
  driver: awslogs
  options:
    awslogs-region: us-east-1
    awslogs-group: /rag-knowledge/app
    awslogs-stream: service-name
```

### 5.2 Enable Prometheus & Grafana (Optional)

```bash
# Start monitoring stack
docker-compose --profile monitoring up -d

# Access Grafana at http://<EC2_IP>:3001
# Default credentials: admin / <GRAFANA_ADMIN_PASSWORD>
```

## Step 6: Backup Strategy

### 6.1 Database Backups

RDS automated backups are enabled by default. For additional backups:

```bash
# Manual snapshot
aws rds create-db-snapshot \
  --db-instance-identifier rag-knowledge-db \
  --db-snapshot-identifier rag-manual-backup-$(date +%Y%m%d)
```

### 6.2 Application Data Backup

```bash
# Backup Redis data
docker-compose exec redis redis-cli BGSAVE

# Copy backup
docker cp rag-redis:/data/dump.rdb ./backups/redis-$(date +%Y%m%d).rdb

# Upload to S3
aws s3 cp ./backups/ s3://rag-knowledge-backups/ --recursive
```

## Step 7: Maintenance

### 7.1 Update Services

```bash
# Pull latest images
docker-compose pull

# Restart with zero downtime (rolling update)
docker-compose up -d --no-deps --scale query-api=1 query-api
sleep 30
docker-compose up -d --no-deps --scale query-api=2 query-api

# Check health
docker-compose ps
```

### 7.2 Database Maintenance

```bash
# Run VACUUM ANALYZE weekly
docker-compose exec management-api python -m app.scripts.db_maintenance

# Refresh materialized views daily
docker-compose exec management-api python -m app.scripts.refresh_views
```

### 7.3 Log Rotation

```bash
# Configure log rotation
sudo tee /etc/logrotate.d/rag-knowledge << EOF
/var/log/nginx/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 nginx nginx
    sharedscripts
    postrotate
        docker-compose exec nginx nginx -s reload
    endscript
}
EOF
```

## Step 8: Scaling

### 8.1 Vertical Scaling

Upgrade EC2 instance:
```bash
# Stop services
docker-compose down

# Change instance type in AWS Console or CLI
aws ec2 modify-instance-attribute \
  --instance-id i-xxxxx \
  --instance-type t3.2xlarge

# Restart services
docker-compose up -d
```

### 8.2 Horizontal Scaling

Add more Query API replicas:
```bash
# In docker-compose.yml, increase replicas
docker-compose up -d --scale query-api=4
```

Add more Ingestion Workers:
```bash
docker-compose up -d --scale ingestion-worker=4
```

## Step 9: Security Hardening

### 9.1 Firewall Configuration

```bash
# Install ufw
sudo apt-get install ufw -y

# Configure rules
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

### 9.2 Secrets Management

Use AWS Secrets Manager:
```bash
# Store secrets
aws secretsmanager create-secret \
  --name rag-knowledge/prod \
  --secret-string file://secrets.json

# Retrieve in application
aws secretsmanager get-secret-value \
  --secret-id rag-knowledge/prod \
  --query SecretString \
  --output text > .env
```

## Step 10: Disaster Recovery

### 10.1 Backup Checklist
- ✅ RDS automated backups (daily)
- ✅ RDS manual snapshots (weekly)
- ✅ Redis data backup (daily)
- ✅ Configuration files in Git
- ✅ S3 versioning enabled

### 10.2 Recovery Procedure

```bash
# 1. Restore RDS from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier rag-knowledge-db-restored \
  --db-snapshot-identifier rag-manual-backup-20240101

# 2. Update DATABASE_URL in .env
# 3. Restart services
docker-compose down
docker-compose up -d

# 4. Verify data integrity
docker-compose exec management-api python -m app.scripts.verify_data
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs <service-name>

# Check system resources
docker stats

# Check disk space
df -h

# Check network
docker network inspect rag-network
```

### Database Connection Issues

```bash
# Test connection from EC2
psql -h rag-knowledge-db.xxxxx.rds.amazonaws.com -U ragadmin -d ragdb

# Check security group rules
aws ec2 describe-security-groups --group-ids sg-xxxxx

# Verify RDS status
aws rds describe-db-instances --db-instance-identifier rag-knowledge-db
```

### High Memory Usage

```bash
# Check container memory
docker stats --no-stream

# Adjust memory limits in docker-compose.yml
# Restart affected services
docker-compose up -d --force-recreate <service-name>
```

## Performance Optimization

### Database Optimization

```sql
-- Check slow queries
SELECT query, mean_exec_time, calls 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;

-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan 
FROM pg_stat_user_indexes 
WHERE idx_scan = 0;
```

### Application Optimization

Monitor metrics:
```bash
# Query API latency
docker-compose logs query-api | grep "latency"

# Cache hit rate
docker-compose exec redis redis-cli INFO stats | grep hits

# Queue depth
docker-compose exec redis redis-cli LLEN celery
```

## Support & Maintenance Contacts

- **Application Issues**: dev-team@company.com
- **Infrastructure**: ops-team@company.com
- **Security**: security@company.com

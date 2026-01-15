#!/usr/bin/env python3
"""
Create an admin user for the RAG Knowledge Indexing System.

Usage:
    python create-admin.py --email admin@example.com --password secure123 --name "Admin User"
    
    Or with environment variables:
    ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=secure123 python create-admin.py
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add paths for imports (works both locally and in Docker)
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "services"))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select


async def create_admin_user(
    email: str,
    password: str,
    name: str,
    database_url: str
) -> None:
    """Create an admin user in the database."""
    
    # Import models after path is set - try different paths for Docker vs local
    try:
        from shared.database.models import AdminUser
        from shared.utils.security import hash_password
    except ImportError:
        from services.shared.database.models import AdminUser
        from services.shared.utils.security import hash_password
    
    engine = create_async_engine(database_url, echo=True)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        # Check if user already exists
        result = await session.execute(
            select(AdminUser).where(AdminUser.email == email)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            print(f"User with email {email} already exists!")
            if existing_user.role != "admin":
                existing_user.role = "admin"
                await session.commit()
                print(f"Updated user role to admin")
            return
        
        # Create new admin user
        admin_user = AdminUser(
            email=email,
            password_hash=hash_password(password),
            full_name=name,
            role="admin",
            is_active=True
        )
        
        session.add(admin_user)
        await session.commit()
        await session.refresh(admin_user)
        
        print(f"✅ Admin user created successfully!")
        print(f"   Email: {email}")
        print(f"   Name: {name}")
        print(f"   Role: admin")
        print(f"   Role: super_admin")
        print(f"   ID: {admin_user.id}")
    
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description="Create an admin user for the RAG Knowledge Indexing System"
    )
    parser.add_argument(
        "--email",
        default=os.environ.get("ADMIN_EMAIL"),
        help="Admin email address"
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("ADMIN_PASSWORD"),
        help="Admin password"
    )
    parser.add_argument(
        "--name",
        default=os.environ.get("ADMIN_NAME", "Admin User"),
        help="Admin display name"
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://raguser:ragpassword@localhost:5432/ragdb"
        ),
        help="Database connection URL"
    )
    
    args = parser.parse_args()
    
    if not args.email:
        print("Error: Email is required. Use --email or set ADMIN_EMAIL env var")
        sys.exit(1)
    
    if not args.password:
        print("Error: Password is required. Use --password or set ADMIN_PASSWORD env var")
        sys.exit(1)
    
    if len(args.password) < 8:
        print("Error: Password must be at least 8 characters long")
        sys.exit(1)
    
    asyncio.run(create_admin_user(
        email=args.email,
        password=args.password,
        name=args.name,
        database_url=args.database_url
    ))


if __name__ == "__main__":
    main()

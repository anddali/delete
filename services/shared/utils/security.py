"""
Security utilities for password hashing, token generation, and encryption.
"""

import base64
import hashlib
import os
import secrets
from typing import Optional

from cryptography.fernet import Fernet
from passlib.hash import argon2


def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return argon2.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a hash."""
    try:
        return argon2.verify(password, password_hash)
    except Exception:
        return False


def generate_token(length: int = 32) -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """Hash a token using SHA-256 for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def get_token_preview(token: str, length: int = 8) -> str:
    """Get a preview of the token for display."""
    return token[:length] + "..."


def get_encryption_key() -> bytes:
    """Get or generate the encryption key from environment."""
    key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
    if not key:
        raise ValueError("CREDENTIAL_ENCRYPTION_KEY environment variable is not set")
    
    # Ensure key is 32 bytes for Fernet
    key_bytes = key.encode()
    if len(key_bytes) < 32:
        key_bytes = key_bytes.ljust(32, b'\0')
    elif len(key_bytes) > 32:
        key_bytes = key_bytes[:32]
    
    # Base64 encode for Fernet
    return base64.urlsafe_b64encode(key_bytes)


def encrypt_credentials(data: str) -> str:
    """Encrypt sensitive credentials for storage."""
    key = get_encryption_key()
    fernet = Fernet(key)
    encrypted = fernet.encrypt(data.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_credentials(encrypted_data: str) -> str:
    """Decrypt stored credentials."""
    key = get_encryption_key()
    fernet = Fernet(key)
    encrypted = base64.urlsafe_b64decode(encrypted_data.encode())
    return fernet.decrypt(encrypted).decode()


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key.
    
    Returns:
        Tuple of (full_token, token_hash, token_preview)
    """
    token = generate_token(32)
    token_hash = hash_token(token)
    token_preview = get_token_preview(token)
    return token, token_hash, token_preview

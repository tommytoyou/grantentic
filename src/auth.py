import hashlib
import secrets
from typing import Optional
from src.database import get_user_by_username, create_user

def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()

def verify_password(password: str, salt: str, hashed: str) -> bool:
    return hash_password(password, salt) == hashed

def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = get_user_by_username(username)
    if not user:
        return None
    if verify_password(password, user["salt"], user["hashed_password"]):
        return user
    return None

def register_user(username: str, password: str, is_admin: bool = False) -> dict:
    existing = get_user_by_username(username)
    if existing:
        raise ValueError(f"Username '{username}' is already taken.")
    salt = secrets.token_hex(16)
    hashed = hash_password(password, salt)
    return create_user(username, hashed, salt, is_admin)

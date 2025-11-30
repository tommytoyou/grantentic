"""
Authentication module for Grantentic
Handles user authentication with secure password hashing
"""

import json
import hashlib
import secrets
from pathlib import Path
from typing import Optional, Dict, Any


# Path to users data file
USERS_FILE = Path(__file__).parent.parent / "data" / "users.json"


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    Hash a password using SHA-256 with a salt.
    Returns (hashed_password, salt)
    """
    if salt is None:
        salt = secrets.token_hex(32)

    # Combine password and salt, then hash
    salted = f"{password}{salt}"
    hashed = hashlib.sha256(salted.encode()).hexdigest()

    return hashed, salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify a password against a stored hash"""
    computed_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, stored_hash)


def load_users() -> Dict[str, Any]:
    """Load users from the JSON file"""
    if not USERS_FILE.exists():
        return {}

    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_users(users: Dict[str, Any]) -> bool:
    """Save users to the JSON file"""
    try:
        # Ensure data directory exists
        USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
        return True
    except IOError:
        return False


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate a user with username and password.
    Returns user data if successful, None otherwise.
    """
    users = load_users()

    if username not in users:
        return None

    user = users[username]

    if verify_password(password, user['password_hash'], user['salt']):
        return {
            'username': username,
            'role': user.get('role', 'user'),
            'created_at': user.get('created_at', '')
        }

    return None


def create_user(username: str, password: str, role: str = 'user') -> bool:
    """
    Create a new user account.
    Returns True if successful, False if user already exists.
    """
    users = load_users()

    if username in users:
        return False

    password_hash, salt = hash_password(password)

    from datetime import datetime

    users[username] = {
        'password_hash': password_hash,
        'salt': salt,
        'role': role,
        'created_at': datetime.now().isoformat()
    }

    return save_users(users)


def user_exists(username: str) -> bool:
    """Check if a user exists"""
    users = load_users()
    return username in users


def initialize_admin_account():
    """
    Initialize the default admin account if it doesn't exist.
    Call this on app startup.
    """
    users = load_users()

    # Check if admin exists and has valid hash (not placeholder)
    if 'admin' not in users or 'placeholder' in users.get('admin', {}).get('password_hash', ''):
        # Create admin account with default password
        password_hash, salt = hash_password('grantentic2024')

        from datetime import datetime

        users['admin'] = {
            'password_hash': password_hash,
            'salt': salt,
            'role': 'admin',
            'created_at': datetime.now().isoformat()
        }

        save_users(users)

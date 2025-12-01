"""
Authentication module for Grantentic
Handles user authentication with secure password hashing
"""

import json
import hashlib
import secrets
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta


# Path to users data file
USERS_FILE = Path(__file__).parent.parent / "data" / "users.json"
PAYMENTS_FILE = Path(__file__).parent.parent / "data" / "payments.json"


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

        users['admin'] = {
            'password_hash': password_hash,
            'salt': salt,
            'role': 'admin',
            'created_at': datetime.now().isoformat()
        }

        save_users(users)


# ============================================================================
# PAYMENT STATUS FUNCTIONS
# ============================================================================

def load_payments() -> Dict[str, Any]:
    """Load payments data from the JSON file"""
    if not PAYMENTS_FILE.exists():
        return {}

    try:
        with open(PAYMENTS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_payments(payments: Dict[str, Any]) -> bool:
    """Save payments data to the JSON file"""
    try:
        PAYMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PAYMENTS_FILE, 'w') as f:
            json.dump(payments, f, indent=2, default=str)
        return True
    except IOError:
        return False


def get_user_payment_status(username: str) -> Dict[str, Any]:
    """
    Get the payment status for a user.
    Returns a dict with payment info.
    """
    payments = load_payments()
    user_payment = payments.get(username, {})

    # Default status for unpaid users
    status = {
        'has_paid': False,
        'payment_type': None,
        'tier': None,
        'stripe_customer_id': user_payment.get('stripe_customer_id'),
        'proposals_generated': user_payment.get('proposals_generated', 0),
        'can_generate': False
    }

    # Check for one-time purchase
    one_time = user_payment.get('one_time_purchase')
    if one_time and one_time.get('status') == 'completed':
        expires_at = user_payment.get('one_time_expires_at')
        if expires_at:
            # Check if not expired (for revision access)
            try:
                expiry = datetime.fromisoformat(expires_at)
                if datetime.now() <= expiry:
                    status['has_paid'] = True
                    status['payment_type'] = 'one_time'
                    status['tier'] = one_time.get('tier', 'one_time')
                    status['can_generate'] = True
                    status['expires_at'] = expires_at
            except ValueError:
                pass
        else:
            # No expiry set, consider it valid
            status['has_paid'] = True
            status['payment_type'] = 'one_time'
            status['tier'] = one_time.get('tier', 'one_time')
            status['can_generate'] = True

    # Check for active subscription
    subscription = user_payment.get('subscription')
    if subscription and subscription.get('status') == 'active':
        status['has_paid'] = True
        status['payment_type'] = 'subscription'
        status['tier'] = subscription.get('tier')
        status['can_generate'] = True
        status['subscription_status'] = subscription.get('status')
        status['current_period_end'] = subscription.get('current_period_end')

    # Admin users can always generate
    users = load_users()
    if username in users and users[username].get('role') == 'admin':
        status['has_paid'] = True
        status['can_generate'] = True
        status['is_admin'] = True

    return status


def record_one_time_payment(
    username: str,
    payment_id: str,
    stripe_checkout_session_id: str,
    stripe_payment_intent_id: str,
    amount_cents: int,
    tier: str = 'one_time'
) -> bool:
    """Record a successful one-time payment for a user"""
    payments = load_payments()

    if username not in payments:
        payments[username] = {}

    payments[username]['one_time_purchase'] = {
        'payment_id': payment_id,
        'stripe_checkout_session_id': stripe_checkout_session_id,
        'stripe_payment_intent_id': stripe_payment_intent_id,
        'amount_cents': amount_cents,
        'currency': 'usd',
        'status': 'completed',
        'tier': tier,
        'created_at': datetime.now().isoformat(),
        'completed_at': datetime.now().isoformat()
    }

    # Set expiry for revision access (30 days from now)
    payments[username]['one_time_expires_at'] = (
        datetime.now() + timedelta(days=30)
    ).isoformat()

    return save_payments(payments)


def record_subscription(
    username: str,
    stripe_subscription_id: str,
    stripe_customer_id: str,
    tier: str,
    status: str,
    current_period_start: str,
    current_period_end: str
) -> bool:
    """Record or update a subscription for a user"""
    payments = load_payments()

    if username not in payments:
        payments[username] = {}

    payments[username]['stripe_customer_id'] = stripe_customer_id
    payments[username]['subscription'] = {
        'subscription_id': secrets.token_hex(16),
        'stripe_subscription_id': stripe_subscription_id,
        'stripe_customer_id': stripe_customer_id,
        'tier': tier,
        'status': status,
        'current_period_start': current_period_start,
        'current_period_end': current_period_end,
        'created_at': datetime.now().isoformat()
    }

    return save_payments(payments)


def update_subscription_status(
    username: str,
    status: str,
    canceled_at: Optional[str] = None
) -> bool:
    """Update subscription status (e.g., canceled, past_due)"""
    payments = load_payments()

    if username not in payments or 'subscription' not in payments[username]:
        return False

    payments[username]['subscription']['status'] = status
    if canceled_at:
        payments[username]['subscription']['canceled_at'] = canceled_at

    return save_payments(payments)


def set_stripe_customer_id(username: str, customer_id: str) -> bool:
    """Set the Stripe customer ID for a user"""
    payments = load_payments()

    if username not in payments:
        payments[username] = {}

    payments[username]['stripe_customer_id'] = customer_id
    return save_payments(payments)


def get_stripe_customer_id(username: str) -> Optional[str]:
    """Get the Stripe customer ID for a user"""
    payments = load_payments()
    return payments.get(username, {}).get('stripe_customer_id')


def increment_proposals_generated(username: str) -> bool:
    """Increment the count of proposals generated by a user"""
    payments = load_payments()

    if username not in payments:
        payments[username] = {}

    payments[username]['proposals_generated'] = (
        payments[username].get('proposals_generated', 0) + 1
    )

    return save_payments(payments)


def get_user_by_stripe_customer_id(customer_id: str) -> Optional[str]:
    """Find username by Stripe customer ID"""
    payments = load_payments()
    for username, data in payments.items():
        if data.get('stripe_customer_id') == customer_id:
            return username
    return None

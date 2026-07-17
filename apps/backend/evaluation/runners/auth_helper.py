import os
import sys
import logging
from dotenv import load_dotenv
from app.db.supabase_client import get_supabase_client

load_dotenv()

logger = logging.getLogger(__name__)

def get_evaluation_credentials():
    """Gets the evaluation user email and password strictly from environment variables."""
    email = os.environ.get("EVALUATION_USER_EMAIL")
    password = os.environ.get("EVALUATION_USER_PASSWORD")
    
    if not email or not password:
        print("[AUTH] ERROR: EVALUATION_USER_EMAIL or EVALUATION_USER_PASSWORD environment variables are missing.")
        print("[AUTH] ERROR: You must define these credentials in your environment or .env file.")
        sys.exit(1)
        
    return email, password

def authenticate_evaluation_user() -> tuple[str, str]:
    """
    Authenticates the evaluation user against Supabase.
    Strictly signs in an existing user. Does not perform auto-signup.
    Returns:
        (user_id, access_token)
    """
    email, password = get_evaluation_credentials()
    supabase = get_supabase_client()
    
    try:
        print(f"[AUTH] Attempting to sign in evaluation user: {email}...")
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        user_id = response.user.id
        access_token = response.session.access_token
        print(f"[AUTH] Sign-in successful. User ID: {user_id}")
        return str(user_id), str(access_token)
    except Exception as e:
        print(f"[AUTH] ERROR: Authentication failed for user {email}: {e}")
        print("[AUTH] ERROR: Please check your EVALUATION_USER_EMAIL and EVALUATION_USER_PASSWORD.")
        sys.exit(1)

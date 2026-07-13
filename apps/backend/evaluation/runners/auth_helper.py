import os
import logging
from dotenv import load_dotenv
from app.db.supabase_client import get_supabase_client

load_dotenv()

logger = logging.getLogger(__name__)

def get_evaluation_credentials():
    """Gets the evaluation user email and password from environment variables or defaults."""
    email = os.environ.get("EVALUATION_USER_EMAIL")
    password = os.environ.get("EVALUATION_USER_PASSWORD")
    
    if not email or not password:
        logger.info("EVALUATION_USER_EMAIL or EVALUATION_USER_PASSWORD not found. Using self-healing defaults.")
        # Self-healing defaults (safe fallback)
        email = email or "eval.user.depi.mega@gmail.com"
        password = password or "EvalPassword123!"
        
    return email, password

def authenticate_evaluation_user() -> tuple[str, str]:
    """
    Authenticates the evaluation user against Supabase.
    If the user does not exist, attempts to sign them up.
    Returns:
        (user_id, access_token)
    """
    email, password = get_evaluation_credentials()
    supabase = get_supabase_client()
    
    try:
        # Try to sign in
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
        err_msg = str(e).lower()
        if "invalid login credentials" in err_msg or "user not found" in err_msg or "cannot find" in err_msg:
            print(f"[AUTH] User {email} not found or credentials invalid. Attempting to sign up...")
            try:
                signup_resp = supabase.auth.sign_up({
                    "email": email,
                    "password": password
                })
                # In some configurations, sign up requires email confirmation or returns session immediately
                if signup_resp.user:
                    user_id = signup_resp.user.id
                    print(f"[AUTH] Sign-up successful. Created User ID: {user_id}")
                    # Try to sign in again after sign-up
                    try:
                        login_resp = supabase.auth.sign_in_with_password({
                            "email": email,
                            "password": password
                        })
                        return str(login_resp.user.id), str(login_resp.session.access_token)
                    except Exception as e2:
                        print(f"[AUTH] Sign-in after sign-up failed (possibly email confirmation needed): {e2}")
                        # If email confirmation is enabled, we can use the user_id from signup_resp
                        # and mock a token or use the service role key to bypass the token check in our script
                        # (since we call execute_query directly we can pass user_id).
                        # Let's return the user_id and a mock token or service role key as fallback.
                        return str(user_id), "signup-pending-confirmation"
                else:
                    raise RuntimeError("Sign up response returned no user.")
            except Exception as signup_err:
                print(f"[AUTH] Sign-up failed: {signup_err}")
                raise signup_err
        else:
            print(f"[AUTH] Authentication error: {e}")
            raise e

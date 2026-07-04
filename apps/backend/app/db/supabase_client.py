import httpx
from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
from app.core.config import settings

def sanitize_supabase_url(url: str) -> str:
    """
    Sanitizes the Supabase URL by removing extra spaces, trailing slashes,
    and any /rest/v1/ suffix if mistakenly appended.
    """
    clean_url = url.strip()
    if clean_url.endswith("/rest/v1/"):
        clean_url = clean_url[:-len("/rest/v1/")]
    elif clean_url.endswith("/rest/v1"):
        clean_url = clean_url[:-len("/rest/v1")]
    return clean_url.rstrip("/")

# Get sanitized URL and select the preferred key
sanitized_url = sanitize_supabase_url(settings.SUPABASE_URL)

# SUPABASE_SERVICE_ROLE_KEY is the preferred backend-only key.
# SUPABASE_KEY is only a fallback if SERVICE_ROLE_KEY is not provided.
resolved_key = (
    settings.SUPABASE_SERVICE_ROLE_KEY.strip()
    if settings.SUPABASE_SERVICE_ROLE_KEY.strip()
    else settings.SUPABASE_KEY.strip()
)

if not resolved_key:
    resolved_key = "placeholder-key"

# Create a custom HTTPX client with HTTP/2 disabled (forces HTTP/1.1) and a 120s timeout limit.
# This prevents the ConnectionTerminated errors and resolves upload write timeouts for larger documents.
custom_httpx_client = httpx.Client(http2=False, timeout=120.0)

# Configure SyncClientOptions with the custom HTTP client
client_options = SyncClientOptions(
    httpx_client=custom_httpx_client
)

# Initialize Supabase client
supabase_client: Client = create_client(
    supabase_url=sanitized_url,
    supabase_key=resolved_key,
    options=client_options
)

def get_supabase_client() -> Client:
    """
    Returns the global Supabase client instance.
    """
    return supabase_client

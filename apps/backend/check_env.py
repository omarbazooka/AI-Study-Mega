"""
Diagnostic script to check all environment variables and connections.
Run with: python check_env.py
"""
import os
import sys
import json
import base64

# Load .env manually
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")

print("=" * 60)
print("   ENV & CONNECTION DIAGNOSTIC REPORT")
print("=" * 60)

# ── 1. Supabase ──────────────────────────────────────────────
print("\n[1] SUPABASE CONFIG")
supabase_url = os.getenv("SUPABASE_URL", "")
service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

print(f"  SUPABASE_URL          : {supabase_url or '❌ MISSING'}")
print(f"  SERVICE_ROLE_KEY      : {'✅ Set (' + service_role_key[:20] + '...)' if service_role_key else '❌ MISSING'}")

# Decode JWT to check role
if service_role_key:
    try:
        parts = service_role_key.split(".")
        if len(parts) == 3:
            padding = 4 - len(parts[1]) % 4
            decoded = base64.urlsafe_b64decode(parts[1] + "=" * padding)
            payload = json.loads(decoded)
            role = payload.get("role", "unknown")
            if role == "service_role":
                print(f"  JWT Role              : ✅ service_role (correct!)")
            elif role == "anon":
                print(f"  JWT Role              : ❌ anon key detected! You need the SERVICE_ROLE key, not the anon key!")
                print(f"                          Go to Supabase → Project Settings → API → service_role → copy that key")
            else:
                print(f"  JWT Role              : ⚠️  Unknown role: {role}")
    except Exception as e:
        print(f"  JWT decode error      : {e}")

# ── 2. Test Supabase Connection ──────────────────────────────
print("\n[2] SUPABASE CONNECTION TEST")
try:
    from supabase import create_client
    client = create_client(supabase_url, service_role_key)
    # Try a simple query
    result = client.table("documents").select("id").limit(1).execute()
    print(f"  Database connection   : ✅ Connected! (documents table accessible)")
except Exception as e:
    err = str(e)
    if "10061" in err or "refused" in err.lower():
        print(f"  Database connection   : ❌ Connection refused - Supabase URL is wrong or local Supabase not running")
    elif "Invalid API key" in err or "401" in err:
        print(f"  Database connection   : ❌ Invalid API key")
    elif "relation" in err.lower() or "does not exist" in err.lower():
        print(f"  Database connection   : ✅ Connected (table may not exist yet - run migrations)")
    else:
        print(f"  Database connection   : ❌ Error: {err[:120]}")

# ── 3. Test Supabase Storage ─────────────────────────────────
print("\n[3] SUPABASE STORAGE TEST")
bucket_name = os.getenv("SUPABASE_STORAGE_BUCKET", "study-documents")
print(f"  Storage bucket        : {bucket_name}")
try:
    from supabase import create_client
    client = create_client(supabase_url, service_role_key)
    buckets = client.storage.list_buckets()
    bucket_names = [b.name for b in buckets]
    if bucket_name in bucket_names:
        print(f"  Bucket exists         : ✅ '{bucket_name}' found")
    else:
        print(f"  Bucket exists         : ❌ '{bucket_name}' NOT found. Available: {bucket_names}")
        print(f"                          Create it in Supabase → Storage → New bucket → '{bucket_name}' (private)")
except Exception as e:
    print(f"  Storage check         : ❌ {str(e)[:120]}")

# ── 4. Cloudflare (Embeddings) ───────────────────────────────
print("\n[4] CLOUDFLARE WORKERS AI (Embeddings)")
cf_account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
cf_token = os.getenv("CLOUDFLARE_API_TOKEN", "")
cf_model = os.getenv("EMBEDDING_MODEL_NAME", "@cf/baai/bge-m3")

print(f"  CLOUDFLARE_ACCOUNT_ID : {'✅ ' + cf_account[:8] + '...' if cf_account else '❌ MISSING'}")
print(f"  CLOUDFLARE_API_TOKEN  : {'✅ Set (' + cf_token[:12] + '...)' if cf_token else '❌ MISSING'}")
print(f"  EMBEDDING_MODEL       : {cf_model}")

if cf_account and cf_token:
    try:
        import httpx
        url = f"https://api.cloudflare.com/client/v4/accounts/{cf_account}/ai/run/{cf_model}"
        headers = {"Authorization": f"Bearer {cf_token}", "Content-Type": "application/json"}
        payload = {"text": ["test"]}
        resp = httpx.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                print(f"  Cloudflare AI call    : ✅ Working! Embedding dims: {len(data['result']['data'][0])}")
            else:
                print(f"  Cloudflare AI call    : ❌ API returned errors: {data.get('errors')}")
        elif resp.status_code == 401:
            print(f"  Cloudflare AI call    : ❌ Unauthorized - check your API token")
        elif resp.status_code == 403:
            print(f"  Cloudflare AI call    : ❌ Forbidden - token missing Workers AI permission")
        else:
            print(f"  Cloudflare AI call    : ❌ HTTP {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"  Cloudflare AI call    : ❌ {str(e)[:100]}")

# ── 5. GROQ API Keys (LLM) ───────────────────────────────────
print("\n[5] GROQ API KEYS (LLM)")
groq_fallback = os.getenv("GROQ_API_KEY", "").strip()
groq_keys = {
    "GROQ_FAST_API_KEYS":      os.getenv("GROQ_FAST_API_KEYS", ""),
    "GROQ_REASONING_API_KEYS": os.getenv("GROQ_REASONING_API_KEYS", ""),
    "GROQ_SUMMARY_API_KEYS":   os.getenv("GROQ_SUMMARY_API_KEYS", ""),
    "GROQ_VERIFIER_API_KEYS":  os.getenv("GROQ_VERIFIER_API_KEYS", ""),
}

if groq_fallback:
    print(f"  GROQ_API_KEY (fallback)       : OK Set ({groq_fallback[:12]}...) [used for all groups]")

all_groq_missing = True
for key_name, key_val in groq_keys.items():
    if key_val.strip():
        count = len([k for k in key_val.split(",") if k.strip()])
        print(f"  {key_name:<30}: OK {count} key(s) loaded")
        all_groq_missing = False
    elif groq_fallback:
        print(f"  {key_name:<30}: -> fallback to GROQ_API_KEY")
        all_groq_missing = False
    else:
        print(f"  {key_name:<30}: MISSING")

if all_groq_missing and not groq_fallback:
    print()
    print("  WARNING: NO GROQ KEYS FOUND! The LLM will not work.")
    print("  Get free keys from: https://console.groq.com/keys")
    print("  Add to .env:")
    print("       GROQ_API_KEY=gsk_xxxx   (single key for all groups)")


# ── 6. Gemini API Key ────────────────────────────────────────
print("\n[6] GEMINI API KEY")
gemini_key = os.getenv("GEMINI_API_KEY", "")
if gemini_key:
    print(f"  GEMINI_API_KEY        : ✅ Set ({gemini_key[:12]}...)")
else:
    print(f"  GEMINI_API_KEY        : ⚠️  Not set (optional if using Groq for LLM)")

# ── 7. Summary ───────────────────────────────────────────────
print("\n" + "=" * 60)
print("   SUMMARY & NEXT STEPS")
print("=" * 60)
print()
if all_groq_missing:
    print("🔴 CRITICAL: Add GROQ API keys to your .env file")
    print("   → https://console.groq.com/keys (free account)")
    print()
print("Done. Fix any ❌ items above, then restart uvicorn.")
print()

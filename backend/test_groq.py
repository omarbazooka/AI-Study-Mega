import os
import json
import urllib.request
import sys

# Try to load from the config we created
try:
    from app.core.config import settings
    api_key = settings.GROQ_API_KEY_VALIDATION
except Exception as e:
    api_key = ""

# If not found, read .env directly as fallback
if not api_key:
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("GROQ_API_KEY_VALIDATION="):
                    api_key = line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass

if not api_key:
    print("Error: Could not find GROQ_API_KEY_VALIDATION in .env")
    sys.exit(1)

print(f"Testing connection with API Key: {api_key[:8]}...{api_key[-4:]}")

url = "https://api.groq.com/openai/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
data = {
    "model": "llama3-8b-8192",
    "messages": [{"role": "user", "content": "مرحبا، هل تسمعني؟ أجب باختصار شديد باللغة العربية."}]
}

req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")

try:
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode("utf-8"))
        print("\nSuccess! Connected to Groq successfully.")
        print("Model Response (Llama 3):")
        print("-" * 40)
        print(result["choices"][0]["message"]["content"])
        print("-" * 40)
except Exception as e:
    print(f"\nConnection Failed: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode("utf-8"))

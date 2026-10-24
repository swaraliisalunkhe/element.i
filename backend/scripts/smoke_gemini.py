"""Manual Gemini API Smoke Test for element.i.

Run from the backend/ directory:
    python scripts/smoke_gemini.py

Owner: Member C.
Purpose:
    Validates Gemini API connectivity, credentials, and configured model access.
    Does NOT run during automated tests.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure backend root is on sys.path so app.* imports work
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings
from app.services.suite_generator import get_gemini_api_key, get_gemini_model


def sanitize(text: str, secret: str) -> str:
    """Strip secret values from error messages or logs."""
    if not secret:
        return text
    return text.replace(secret, "[REDACTED_API_KEY]")


def main() -> int:
    print("=" * 60)
    print("element.i - Gemini API Manual Smoke Test")
    print("=" * 60)

    # 1. Load configuration using the project's existing configuration approach
    settings = get_settings()
    api_key = get_gemini_api_key(settings)
    model_id = get_gemini_model()

    print(f"Configured Model ID: {model_id}")
    print(f"API Key Detected   : {'YES (loaded from .env / environment)' if api_key else 'NO'}")

    if not api_key:
        print("\n[ERROR] Missing GEMINI_API_KEY.")
        print("Please ensure your API key is defined in:")
        print(f"  {BACKEND_DIR / '.env'}")
        print("Format:")
        print("  GEMINI_API_KEY=your_gemini_api_key_here")
        return 1

    # 2. Initialize Gemini Client using official google-genai SDK
    try:
        from google import genai
        from google.genai import errors
    except ImportError:
        print("\n[ERROR] 'google-genai' package is not installed.")
        print("Run: pip install -r requirements.txt")
        return 1

    client = genai.Client(api_key=api_key)

    # 3. Send test request
    prompt = "Reply with exactly 'GEMINI_OK' and nothing else."
    print(f"\nSending test prompt to model '{model_id}'...")

    try:
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
        )
        reply = (response.text or "").strip()
        print("\n[SUCCESS] Response received from Gemini:")
        print(f"  {reply}")

        if "GEMINI_OK" in reply:
            print("\nVerification Passed: Model responded with expected confirmation.")
        else:
            print(f"\nNote: Expected 'GEMINI_OK', received '{reply}'. Check model alignment/instructions.")
        return 0

    except errors.APIError as err:
        msg = sanitize(str(err.message or err), api_key)
        code = getattr(err, "code", None) or getattr(err, "status", None)
        status_text = f" (code/status: {code})" if code else ""

        print(f"\n[FAILURE] Gemini API Error{status_text}:")
        print(f"  Details: {msg}")

        lower_msg = msg.lower()
        if any(w in lower_msg for w in ("api_key_invalid", "api key not valid", "permission_denied", "unauthenticated", "invalid api key")):
            print("\nDiagnosis: AUTHENTICATION FAILURE")
            print("  The GEMINI_API_KEY provided is invalid, expired, or lacks permission.")
            print("  Please verify the key in backend/.env against Google AI Studio / Google Cloud Console.")
        elif any(w in lower_msg for w in ("not_found", "model not found", "is not supported", "is not found", "unknown model")):
            print(f"\nDiagnosis: INVALID OR UNAVAILABLE MODEL ID ('{model_id}')")
            print(f"  The model ID '{model_id}' was not found or is not accessible with your API key / project tier.")
            print("  Check available models or override with: GEMINI_MODEL=<model_id> in backend/.env")
        elif any(w in lower_msg for w in ("resource_exhausted", "quota", "rate limit", "429")):
            print("\nDiagnosis: QUOTA / RATE LIMIT EXCEEDED")
            print("  You have hit a rate limit or exhausted the quota for this API key / project.")
        else:
            print("\nDiagnosis: GENERAL API FAILURE")
            print("  Review the error message details above.")
        return 2

    except Exception as exc:
        raw_msg = str(exc)
        msg = sanitize(raw_msg, api_key)
        exc_type = type(exc).__name__
        print(f"\n[FAILURE] Unexpected {exc_type}:")
        print(f"  Details: {msg}")

        lower_msg = msg.lower()
        if any(w in lower_msg for w in ("connect", "timeout", "network", "dns", "getaddrinfo")):
            print("\nDiagnosis: NETWORK / CONNECTIVITY ISSUE")
            print("  Could not reach Google GenAI endpoints (generativelanguage.googleapis.com).")
            print("  Check your internet connection, proxy settings, or firewall rules.")
        return 3


if __name__ == "__main__":
    sys.exit(main())

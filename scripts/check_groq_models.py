"""
Live check: confirm each configured Groq key works and can use the
configured model. Keys are reported by position, never printed. Run by hand:

    python scripts/check_groq_models.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(ROOT / ".env")

from llm.llm_client import DEFAULT_MODEL, configured_api_keys

model = (os.getenv("MODEL_NAME") or DEFAULT_MODEL).strip()
keys = configured_api_keys()
if not keys:
    sys.exit("No GROQ_API_KEY found in .env")

for position, key in enumerate(keys, 1):
    label = f"key {position} of {len(keys)}"
    try:
        available = {m.id for m in OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1").models.list().data}
        status = "can use" if model in available else "CANNOT use"
        print(f"{label}: OK, {len(available)} models, {status} {model}")
    except Exception as e:
        print(f"{label}: FAILED ({type(e).__name__}: {str(e)[:120]})")

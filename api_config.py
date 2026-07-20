"""
API Configuration for FRIDAY
Simple Groq-based setup.
"""

import os
import json

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "friday_config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


config = load_config()
GROQ_API_KEY = config.get("groq_api_key") or os.environ.get("GROQ_API_KEY") or ""
GROQ_MODEL = config.get("groq_model", "llama-3.3-70b-versatile")

try:
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    print(f"[API] Groq ready | model: {GROQ_MODEL}")
except Exception as e:
    print(f"[API] Groq init failed: {e}")
    client = None

def chat_completion(messages, **kwargs):
    if client is None:
        return None
    try:
        return client.chat.completions.create(
            model=GROQ_MODEL, messages=messages,
            timeout=20, **kwargs
        )
    except Exception as e:
        print(f"[API] Error: {e}")
        return None

def get_client_info():
    return {"client": client, "provider": "groq", "model": GROQ_MODEL}

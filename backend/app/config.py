import os


def _load_env():
    path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_BASE = os.getenv("PAYPAL_BASE", "https://api-m.sandbox.paypal.com")
PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "poolside/laguna-s-2.1:free")
MOCK_MODE = not (PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET)
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "paidpilot.db")

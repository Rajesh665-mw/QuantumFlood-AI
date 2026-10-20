"""
Vercel Serverless Function entrypoint for QuantumFlood AI.
Exposes the existing FastAPI application instance without duplicating logic.
"""
import sys
from pathlib import Path

# Add the backend directory to sys.path so 'app' and its subpackages resolve cleanly
_ROOT_DIR = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _ROOT_DIR / "backend"

if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Import the existing production FastAPI app from backend/app/main.py
from app.main import app

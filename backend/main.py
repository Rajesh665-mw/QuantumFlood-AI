import sys
import logging
from pathlib import Path

# Ensure backend root directory is in sys.path regardless of execution context
_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

try:
    from app.main import app
except Exception as e:
    logging.exception(f"CRITICAL: Failed to load app from app.main: {e}")
    import traceback
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI(title="QuantumFlood AI Fallback")
    _tb = traceback.format_exc()
    _err_msg = str(e)

    @app.api_route("/{path:path}", methods=["GET", "POST", "OPTIONS"])
    def catch_all(path: str):
        return JSONResponse(
            status_code=500,
            content={
                "error": "FastAPI startup exception",
                "detail": _err_msg,
                "traceback": _tb,
            },
        )

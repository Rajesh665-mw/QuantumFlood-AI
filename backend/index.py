import sys
import traceback
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Ensure backend root directory is in sys.path
_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Top-level application assignments for Vercel static AST parser
app = FastAPI()
application = app
handler = app

_import_error = None
try:
    from app.main import app as _real_app
    app = _real_app
    application = app
    handler = app
except Exception as e:
    _import_error = traceback.format_exc()

if _import_error is not None:
    _err_app = FastAPI(title="QuantumFlood Error Diagnostic")

    @_err_app.api_route("/{path:path}", methods=["GET", "POST", "OPTIONS"])
    def error_handler(path: str):
        return JSONResponse(
            status_code=500,
            content={
                "error": "Backend import failure",
                "detail": _import_error.splitlines(),
            },
        )

    app = _err_app
    application = app
    handler = app

import sys
from pathlib import Path

# Ensure backend root directory is in sys.path
_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.main import app as _app

# Explicit top-level exports for Vercel Python runtime static AST detection
app = _app
application = app
handler = app

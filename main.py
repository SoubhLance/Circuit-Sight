"""
CircuitSight - Root ASGI Entry Point
Forwards ASGI application requests to backend.main:app, allowing
`uvicorn main:app` to be invoked directly from the project root directory.
"""

import sys
from pathlib import Path

# Add backend directory to sys.path so backend internal modules resolve cleanly
root_dir = Path(__file__).resolve().parent
backend_dir = root_dir / "backend"

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Expose app for uvicorn main:app
from backend.main import app  # noqa: E402, F401

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI()

# Resolve UI directory relative to this Python file
BASE_DIR = Path(__file__).resolve().parent
UI_DIR = BASE_DIR / "ui"

# Check that the UI directory exists
if not UI_DIR.exists():
    raise RuntimeError(f"UI directory not found: {UI_DIR}")

# Mount static files
app.mount(
    "/ui",
    StaticFiles(directory=str(UI_DIR)),
    name="ui"
)

# Serve frontend at root
@app.get("/")
async def read_root():
    index_file = UI_DIR / "index.html"

    if not index_file.exists():
        raise RuntimeError(f"index.html not found: {index_file}")

    return FileResponse(index_file)
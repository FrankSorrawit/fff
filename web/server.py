from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from core.validation import validate_and_repair
from core.node_catalog import NODE_CATALOG
from core.nodes import NODE_HANDLERS
from core.runtime.engine import run_flow

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
INDEX_PATH = BASE_DIR / "index.html"
STATIC_DIR = BASE_DIR / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(INDEX_PATH.read_text())


@app.post("/api/validate")
async def api_validate(flow: dict):
    try:
        repaired = validate_and_repair(flow, NODE_CATALOG)
    except Exception as exc:  # pragma: no cover - simple error path
        return {"valid": False, "error": str(exc)}
    return {"valid": True, "flow": repaired}


@app.post("/api/run")
async def api_run(payload: dict):
    flow = payload["flow"]
    inputs = payload.get("inputs")
    result = await run_flow(flow, inputs, NODE_HANDLERS)
    return {"result": result}

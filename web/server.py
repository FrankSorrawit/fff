from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from core.validation import validate_and_repair
from core.node_catalog import NODE_CATALOG
from core.nodes import NODE_HANDLERS
from core.runtime.engine import run_flow

app = FastAPI()

INDEX_PATH = Path(__file__).resolve().parent / "index.html"


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

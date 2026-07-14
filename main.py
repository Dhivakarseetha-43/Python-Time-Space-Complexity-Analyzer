"""
main.py
-------
FastAPI application entry point.

Exposes a single endpoint:

    POST /analyze   { "code": "..." }  ->  AnalyzeResponse

Also serves the static frontend (frontend/index.html) so the whole
MVP can be run with a single command.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from models import AnalyzeRequest, AnalyzeResponse
from parser import parse_code, CodeParseError
from analyzer import analyze

app = FastAPI(
    title="Python Time & Space Complexity Analyzer",
    description="Paste Python code and get an estimated Big-O time/space complexity.",
    version="0.1.0",
)

# Permissive CORS since this is a local/demo MVP with no auth.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent 


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_code(payload: AnalyzeRequest):
    """
    Parse the submitted Python code and return an estimated time/space
    complexity, along with the lines responsible and a few structural
    details (loop nesting depth, whether recursion was detected).
    """
    try:
        tree = parse_code(payload.code)
    except CodeParseError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    result = analyze(tree)
    return AnalyzeResponse(**result)


@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    """Serve the single-page frontend."""
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found.")
    return index_path.read_text(encoding="utf-8")


# Serve any other static assets (css/js) if added later.
if (FRONTEND_DIR).exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")



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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent 


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_code(payload: AnalyzeRequest):
    
    try:
        tree = parse_code(payload.code)
    except CodeParseError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    result = analyze(tree)
    return AnalyzeResponse(**result)


@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found.")
    return index_path.read_text(encoding="utf-8")


# Serve any other static assets (css/js) if added later.
if (FRONTEND_DIR).exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

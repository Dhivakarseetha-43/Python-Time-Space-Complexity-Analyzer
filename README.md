# Python Time & Space Complexity Analyzer (MVP)

Paste Python code, click **Analyze**, and get an estimated Big-O time
and space complexity, the line numbers responsible, loop nesting
depth, and whether recursion was detected.

This is an educational MVP aimed at common interview-style snippets
(loops, nested loops, sorting, binary-search-style halving loops,
linear/branching recursion, list/dict/set creation) — not a
production-grade static analyzer. All detection is done with Python's
built-in `ast` module; no regex is used.

## Project structure

```
complexity_analyzer/
├── backend/
│   ├── main.py         # FastAPI app, /analyze endpoint, serves the frontend
│   ├── parser.py        # Wraps ast.parse(), turns SyntaxError into a clean error
│   ├── analyzer.py       # Core AST-walking complexity detection logic
│   ├── models.py        # Pydantic request/response models
│   └── requirements.txt
└── frontend/
    └── index.html       # Single-page UI (plain HTML/CSS/JS, no build step)
```

## Run it

```bash
cd complexity_analyzer/backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Then open **http://127.0.0.1:8000/** in your browser — the FastAPI
app serves the frontend directly, so there's nothing else to start.

## API

`POST /analyze`

Request:
```json
{ "code": "def f(arr):\n    for x in arr:\n        print(x)" }
```

Response:
```json
{
  "timeComplexity": "O(n)",
  "spaceComplexity": "O(1)",
  "detectedLines": [3],
  "loopDepth": 1,
  "recursionDetected": false,
  "explanation": ["Detected a single loop (or sequential loops) -> O(n) time.", "..."]
}
```

## Rules implemented

| Pattern | Time | Space |
|---|---|---|
| Single loop | O(n) | — |
| Sequential loops | O(n) | — |
| Two nested loops | O(n²) | — |
| Three+ nested loops | O(n³) | — |
| `sorted()` / `.sort()` (no surrounding loop) | O(n log n) | — |
| `while n > 1: n //= 2` (halving/doubling loop) | O(log n) | — |
| List / dict / set literal or comprehension | — | O(n) |
| Recursion, 1 self-call (e.g. factorial) | O(n) | O(n) (call stack) |
| Recursion, 2+ self-calls (e.g. naive Fibonacci) | O(2ⁿ) | O(n) (call stack) |
| Nothing detected | O(1) | O(1) |

When multiple signals are present, the analyzer reports the dominant
one (highest complexity first) and lists the reasoning in
`explanation`.

"""
Versight AI Pre-Editor — FastAPI service.

This is the prototype of the AI pre-editor module: one of Versight's two core
differentiators (alongside the template intelligence system). It takes raw
document text (eventually pulled from Enovia/SVN via the middleware) and runs
three layers of review:

  1. Readability      — Flesch-Kincaid grade, sentence length, passive voice
  2. Terminology       — controlled-vocabulary compliance against a glossary
  3. Structure         — required-section / template compliance
  4. AI review         — Claude call for procedural ambiguity & safety gaps

and returns a single scored report. Run it with:

    uvicorn main:app --reload

then open http://localhost:8000/ for the demo UI.
"""
import os
from pathlib import Path
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from models import AnalyzeRequest, AnalyzeResponse
from readability import analyze_readability
from terminology import load_glossary, check_terminology
from structure import load_template, check_structure
from ai_review import run_ai_review
import rate_limit

load_dotenv()

app = FastAPI(title="Versight AI Pre-Editor", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GLOSSARY = load_glossary()

# Documents come from Word/SVN exports and can be long, but a public endpoint
# needs a hard ceiling so one request can't blow up token spend or memory.
MAX_TEXT_LENGTH = int(os.environ.get("MAX_TEXT_LENGTH", "20000"))


def client_key(request: Request) -> str:
    # Render/Railway sit behind a proxy; prefer the forwarded client IP.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def compute_overall_score(
    readability: Dict[str, Any],
    terminology_issues: List[Dict[str, Any]],
    structure: Dict[str, Any],
    ai_suggestions: List[Dict[str, Any]],
) -> float:
    score = 100.0

    fk = readability["flesch_kincaid_grade"]
    if fk > 10:
        # SOPs read by technicians on a factory floor should land well below
        # a college reading level; penalize past grade 10.
        score -= min((fk - 10) * 2.5, 20)

    score -= min(len(readability["passive_voice_sentences"]) * 1.5, 15)
    score -= min(len(readability["long_sentences"]) * 1.5, 10)
    score -= min(len(terminology_issues) * 2, 20)
    score -= min(len(structure["missing_sections"]) * 5, 20)
    if structure["out_of_order"]:
        score -= 5

    high_sev = sum(1 for s in ai_suggestions if s.get("severity") == "high")
    med_sev = sum(1 for s in ai_suggestions if s.get("severity") == "medium")
    score -= min(high_sev * 6 + med_sev * 3, 25)

    return round(max(score, 0.0), 1)


def build_summary(
    score: float,
    readability: Dict[str, Any],
    terminology_issues: List[Dict[str, Any]],
    structure: Dict[str, Any],
    ai_suggestions: List[Dict[str, Any]],
) -> str:
    parts = [f"Overall score: {score}/100.", f"Reading grade level: {readability['flesch_kincaid_grade']}."]
    if terminology_issues:
        parts.append(f"{len(terminology_issues)} terminology issue(s) found.")
    if structure["missing_sections"]:
        parts.append(f"Missing sections: {', '.join(structure['missing_sections'])}.")
    high_sev = [s for s in ai_suggestions if s.get("severity") == "high"]
    if high_sev:
        parts.append(f"{len(high_sev)} high-severity clarity/safety issue(s) flagged for review.")
    return " ".join(parts)


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest, request: Request):
    if len(req.text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=413,
            detail=f"Document too long ({len(req.text)} chars). Limit is {MAX_TEXT_LENGTH} chars per request.",
        )

    if not req.skip_ai_review:
        key = client_key(request)
        if not rate_limit.allow(key):
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded ({rate_limit.RATE_LIMIT_MAX_REQUESTS} AI-reviewed "
                    f"analyses per {rate_limit.RATE_LIMIT_WINDOW_SECONDS // 60} min per user). "
                    "Retry later, or set skip_ai_review=true for unlimited rule-based-only checks."
                ),
            )

    readability = analyze_readability(req.text)
    terminology_issues = check_terminology(req.text, GLOSSARY, req.glossary_overrides)

    required_sections = req.required_sections or load_template(req.document_type)
    structure = check_structure(req.text, required_sections)

    ai_suggestions: List[Dict[str, Any]] = []
    if not req.skip_ai_review:
        ai_suggestions = run_ai_review(
            req.text,
            req.document_type,
            {
                "readability": readability,
                "terminology_issues": terminology_issues,
                "structure": structure,
            },
        )

    score = compute_overall_score(readability, terminology_issues, structure, ai_suggestions)
    summary = build_summary(score, readability, terminology_issues, structure, ai_suggestions)

    return {
        "document_type": req.document_type,
        "readability": readability,
        "terminology_issues": terminology_issues,
        "structure": structure,
        "ai_suggestions": ai_suggestions,
        "overall_score": score,
        "summary": summary,
    }


@app.get("/health")
def health():
    return {"status": "ok", "ai_review_enabled": bool(__import__("os").environ.get("ANTHROPIC_API_KEY"))}


# Serve the demo frontend as static files at "/", so `uvicorn main:app` alone
# is enough to try the whole thing end to end.
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


if __name__ == "__main__":
    # Render/Railway both set $PORT and expect the process to bind to it.
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))

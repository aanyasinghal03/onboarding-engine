"""
main.py  (v2 + UI)
------------------
AI-Adaptive Onboarding Engine — FastAPI entry point.

Endpoints
---------
GET  /         — serves index.html (SkillBridge UI)
GET  /health   — detailed health check
POST /analyze  — full analysis pipeline
GET  /api      — JSON liveness probe
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from parser import load_skills_db, parse_and_extract, _SPACY_AVAILABLE
from skill_gap import compute_skill_gap, build_reasoning, gap_summary
from roadmap import generate_roadmap

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SkillBridge — AI Onboarding Engine",
    description="Skill-gap analysis and personalised learning roadmap generation.",
    version="2.0.0",
)

# Allow the HTML frontend to call the API without CORS errors.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Startup: load skills DB once
# ---------------------------------------------------------------------------

SKILLS_DB: Dict[str, Any] = {}

@app.on_event("startup")
async def _startup():
    global SKILLS_DB
    try:
        SKILLS_DB = load_skills_db("skills.json")
        print(f"[OK] Skills DB loaded — {len(SKILLS_DB)} skills.")
    except FileNotFoundError as exc:
        print(f"[WARN] {exc}")

    if _SPACY_AVAILABLE:
        print("[OK] spaCy + en_core_web_md — full NLP pipeline active.")
    else:
        print("[INFO] spaCy not available — pure-Python NLP fallback active.")


# ---------------------------------------------------------------------------
# GET /  — serve the SkillBridge UI
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def serve_ui():
    html_path = Path(__file__).parent / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found.")
    return FileResponse(html_path, media_type="text/html")


# ---------------------------------------------------------------------------
# GET /api  — JSON liveness probe
# ---------------------------------------------------------------------------

@app.get("/api", tags=["Health"])
async def api_status():
    return {
        "status":        "ok",
        "version":       "2.0.0",
        "skills_loaded": len(SKILLS_DB),
        "nlp_engine":    "spaCy (en_core_web_md)" if _SPACY_AVAILABLE else "pure-Python NLP",
        "ui":            "http://127.0.0.1:8000/",
    }


# ---------------------------------------------------------------------------
# GET /health  — detailed health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health():
    category_counts: Dict[str, int] = {}
    for meta in SKILLS_DB.values():
        cat = meta.get("category", "unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    pdf_engines = []
    try:
        import pdfplumber; pdf_engines.append("pdfplumber (primary)")
    except ImportError: pass
    try:
        import pypdf; pdf_engines.append("pypdf (fallback)")
    except ImportError: pass

    return {
        "status": "ok" if SKILLS_DB else "degraded",
        "skills_db": {
            "loaded": bool(SKILLS_DB),
            "total_skills": len(SKILLS_DB),
            "by_category": category_counts,
        },
        "nlp": {
            "spacy_available": _SPACY_AVAILABLE,
            "model": "en_core_web_md" if _SPACY_AVAILABLE else None,
            "capabilities": (
                ["exact", "fuzzy", "alias", "n-gram", "TF-IDF", "section-boost",
                 "vector-similarity", "noun-chunk"]
                if _SPACY_AVAILABLE else
                ["exact", "fuzzy", "alias", "n-gram", "TF-IDF", "section-boost"]
            ),
        },
        "pdf_extractors": pdf_engines,
    }


# ---------------------------------------------------------------------------
# POST /analyze  — main analysis endpoint
# ---------------------------------------------------------------------------

@app.post("/analyze", tags=["Analysis"])
async def analyze(
    resume_file: UploadFile = File(..., description="Candidate resume (.pdf or .txt)"),
    jd_file:     UploadFile = File(..., description="Job description (.pdf or .txt)"),
):
    """Full pipeline: parse → NLP extraction → gap analysis → roadmap → reasoning."""
    t0 = time.perf_counter()

    if not SKILLS_DB:
        raise HTTPException(status_code=503, detail="Skills DB unavailable.")

    resume_bytes = await resume_file.read()
    jd_bytes     = await jd_file.read()

    try:
        resume_text, resume_skills = parse_and_extract(
            resume_file.filename or "resume", resume_bytes, SKILLS_DB)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Resume error: {exc}")

    try:
        jd_text, jd_skills = parse_and_extract(
            jd_file.filename or "job_description", jd_bytes, SKILLS_DB)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Job description error: {exc}")

    skill_gap = compute_skill_gap(resume_skills, jd_skills, SKILLS_DB)
    reasoning = build_reasoning(resume_skills, jd_skills, skill_gap, SKILLS_DB)
    summary   = gap_summary(resume_skills, jd_skills, skill_gap)
    roadmap   = generate_roadmap(skill_gap, resume_skills)

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    return JSONResponse(content={
        "summary":       summary,
        "resume_skills": resume_skills,
        "jd_skills":     jd_skills,
        "skill_gap":     skill_gap,
        "roadmap":       roadmap,
        "reasoning":     reasoning,
        "meta": {
            "processing_ms":   elapsed_ms,
            "nlp_engine":      "spaCy" if _SPACY_AVAILABLE else "pure-Python NLP",
            "resume_filename": resume_file.filename,
            "jd_filename":     jd_file.filename,
            "resume_chars":    len(resume_text),
            "jd_chars":        len(jd_text),
        },
    })

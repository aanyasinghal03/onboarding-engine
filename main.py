"""
main.py  (v2)
-------------
AI-Adaptive Onboarding Engine – FastAPI entry point.

Endpoints
---------
GET  /         – liveness probe
GET  /health   – detailed health check (NLP model status, skills DB stats)
POST /analyze  – full analysis pipeline
"""

from __future__ import annotations

import time
from typing import Any, Dict

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from parser import load_skills_db, parse_and_extract, _SPACY_AVAILABLE
from skill_gap import compute_skill_gap, build_reasoning, gap_summary
from roadmap import generate_roadmap

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI-Adaptive Onboarding Engine",
    description=(
        "Upload a resume and a job description to receive a skill-gap analysis "
        "and a personalised, prerequisite-aware learning roadmap.\n\n"
        "**v2 improvements:** pdfplumber PDF parsing, NLP skill extraction "
        "(spaCy when available, pure-Python fallback), semantic synonym matching, "
        "level-upgrade gap detection, and topologically-sequenced roadmaps."
    ),
    version="2.0.0",
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
        print(f"[OK] Skills DB loaded — {len(SKILLS_DB)} skills across categories.")
    except FileNotFoundError as exc:
        print(f"[WARN] {exc}")

    if _SPACY_AVAILABLE:
        print("[OK] spaCy + en_core_web_md loaded — full NLP pipeline active.")
    else:
        print("[INFO] spaCy not available — using pure-Python NLP fallback.")
        print("       Run: pip install spacy && python -m spacy download en_core_web_md")
        print("       to enable vector similarity and noun-chunk extraction.")


# ---------------------------------------------------------------------------
# GET /  – liveness probe
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
async def root():
    return {
        "status":        "ok",
        "version":       "2.0.0",
        "skills_loaded": len(SKILLS_DB),
        "nlp_engine":    "spaCy (en_core_web_md)" if _SPACY_AVAILABLE else "pure-Python NLP",
        "hint":          "POST to /analyze with resume_file and jd_file to get started.",
    }


# ---------------------------------------------------------------------------
# GET /health  – detailed health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health():
    """
    Returns detailed system health including:
    - Skills DB statistics per category
    - NLP pipeline status and capabilities
    - PDF extractor availability
    """
    # Category breakdown
    category_counts: Dict[str, int] = {}
    for meta in SKILLS_DB.values():
        cat = meta.get("category", "unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # PDF extractor status
    pdf_engines = []
    try:
        import pdfplumber  # noqa
        pdf_engines.append("pdfplumber (primary)")
    except ImportError:
        pass
    try:
        import pypdf  # noqa
        pdf_engines.append("pypdf (fallback)")
    except ImportError:
        pass

    return {
        "status": "ok" if SKILLS_DB else "degraded",
        "skills_db": {
            "loaded":           bool(SKILLS_DB),
            "total_skills":     len(SKILLS_DB),
            "by_category":      category_counts,
        },
        "nlp": {
            "spacy_available":  _SPACY_AVAILABLE,
            "model":            "en_core_web_md" if _SPACY_AVAILABLE else None,
            "capabilities": (
                ["exact match", "fuzzy match", "alias match", "n-gram extraction",
                 "TF-IDF weighting", "section detection", "vector similarity",
                 "noun-chunk extraction"]
                if _SPACY_AVAILABLE
                else ["exact match", "fuzzy match", "alias match", "n-gram extraction",
                      "TF-IDF weighting", "section detection"]
            ),
        },
        "pdf_extractors": pdf_engines,
    }


# ---------------------------------------------------------------------------
# POST /analyze  – main endpoint
# ---------------------------------------------------------------------------

@app.post("/analyze", tags=["Analysis"])
async def analyze(
    resume_file: UploadFile = File(..., description="Candidate resume (.pdf or .txt)"),
    jd_file:     UploadFile = File(..., description="Job description (.pdf or .txt)"),
):
    """
    Full analysis pipeline:

    1. Parse uploaded files (pdfplumber → pypdf fallback for PDFs)
    2. Extract skills using multi-stage NLP pipeline
    3. Perform gap analysis with synonym resolution + level-upgrade detection
    4. Generate a topologically-sorted, phase-aware learning roadmap
    5. Build a transparent reasoning trace

    **Response fields:**
    - `summary`        — coverage stats, readiness label, NLP engine used
    - `resume_skills`  — skills found in the resume with confidence scores
    - `jd_skills`      — skills found in the JD with confidence scores
    - `skill_gap`      — enriched gap entries (MISSING or LEVEL_UPGRADE)
    - `roadmap`        — ordered learning plan with steps, effort, phase
    - `reasoning`      — per-skill explanation of every gap decision
    - `meta`           — processing time, file info
    """
    t0 = time.perf_counter()

    # ── Guard ────────────────────────────────────────────────────────────
    if not SKILLS_DB:
        raise HTTPException(
            status_code=503,
            detail="Skills DB unavailable — ensure skills.json is present and the server has restarted.",
        )

    # ── Read file bytes ───────────────────────────────────────────────────
    resume_bytes = await resume_file.read()
    jd_bytes     = await jd_file.read()

    # ── Parse + extract skills ────────────────────────────────────────────
    try:
        resume_text, resume_skills = parse_and_extract(
            resume_file.filename or "resume", resume_bytes, SKILLS_DB
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Resume parsing failed: {exc}")

    try:
        jd_text, jd_skills = parse_and_extract(
            jd_file.filename or "job_description", jd_bytes, SKILLS_DB
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Job description parsing failed: {exc}")

    # ── Gap analysis ──────────────────────────────────────────────────────
    skill_gap = compute_skill_gap(resume_skills, jd_skills, SKILLS_DB)
    reasoning = build_reasoning(resume_skills, jd_skills, skill_gap, SKILLS_DB)
    summary   = gap_summary(resume_skills, jd_skills, skill_gap)

    # ── Roadmap ───────────────────────────────────────────────────────────
    roadmap = generate_roadmap(skill_gap, resume_skills)

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    # ── Compose response ──────────────────────────────────────────────────
    return JSONResponse(content={
        "summary":       summary,
        "resume_skills": resume_skills,
        "jd_skills":     jd_skills,
        "skill_gap":     skill_gap,
        "roadmap":       roadmap,
        "reasoning":     reasoning,
        "meta": {
            "processing_ms":    elapsed_ms,
            "nlp_engine":       "spaCy (en_core_web_md)" if _SPACY_AVAILABLE else "pure-Python NLP",
            "resume_filename":  resume_file.filename,
            "jd_filename":      jd_file.filename,
            "resume_chars":     len(resume_text),
            "jd_chars":         len(jd_text),
        },
    })

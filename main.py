"""
main.py  (v3 — Competition Edition)
-------------------------------------
GET  /           — SkillBridge UI
GET  /api        — JSON liveness probe
GET  /health     — detailed health check
POST /analyze    — full analysis pipeline
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
from roadmap import generate_roadmap, compute_training_time_saved

app = FastAPI(
    title="SkillBridge — AI Adaptive Onboarding Engine",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SKILLS_DB: Dict[str, Any] = {}

@app.on_event("startup")
async def _startup():
    global SKILLS_DB
    try:
        SKILLS_DB = load_skills_db("skills.json")
        print(f"[OK] Skills DB loaded — {len(SKILLS_DB)} skills across {_count_domains()} domains.")
    except FileNotFoundError as exc:
        print(f"[WARN] {exc}")
    if _SPACY_AVAILABLE:
        print("[OK] spaCy NLP pipeline active.")
    else:
        print("[INFO] Pure-Python NLP fallback active.")

def _count_domains():
    cats = {m.get("category") for m in SKILLS_DB.values()}
    return len(cats)

@app.get("/", include_in_schema=False)
async def serve_ui():
    html = Path(__file__).parent / "index.html"
    if not html.exists():
        raise HTTPException(404, "index.html not found")
    return FileResponse(html, media_type="text/html")

@app.get("/api", tags=["Health"])
async def api_status():
    return {"status": "ok", "version": "3.0.0",
            "skills_loaded": len(SKILLS_DB),
            "nlp": "spaCy" if _SPACY_AVAILABLE else "pure-Python"}

@app.get("/health", tags=["Health"])
async def health():
    cats: Dict[str, int] = {}
    for m in SKILLS_DB.values():
        c = m.get("category","?"); cats[c] = cats.get(c,0)+1
    pdf = []
    try: import pdfplumber; pdf.append("pdfplumber")
    except ImportError: pass
    try: import pypdf; pdf.append("pypdf")
    except ImportError: pass
    from pathlib import Path as P
    catalog_ok = (P(__file__).parent / "course_catalog.json").exists()
    return {
        "status": "ok" if SKILLS_DB else "degraded",
        "skills_db": {"total": len(SKILLS_DB), "by_domain": cats},
        "course_catalog": {"loaded": catalog_ok, "grounded": catalog_ok},
        "nlp": {"engine": "spaCy" if _SPACY_AVAILABLE else "pure-Python"},
        "pdf_extractors": pdf,
    }

@app.post("/analyze", tags=["Analysis"])
async def analyze(
    resume_file: UploadFile = File(...),
    jd_file:     UploadFile = File(...),
):
    t0 = time.perf_counter()
    if not SKILLS_DB:
        raise HTTPException(503, "Skills DB unavailable.")

    rb = await resume_file.read()
    jb = await jd_file.read()

    try:
        rt, resume_skills = parse_and_extract(resume_file.filename or "resume", rb, SKILLS_DB)
    except ValueError as e:
        raise HTTPException(422, f"Resume error: {e}")

    try:
        jt, jd_skills = parse_and_extract(jd_file.filename or "jd", jb, SKILLS_DB)
    except ValueError as e:
        raise HTTPException(422, f"JD error: {e}")

    skill_gap = compute_skill_gap(resume_skills, jd_skills, SKILLS_DB)
    reasoning = build_reasoning(resume_skills, jd_skills, skill_gap, SKILLS_DB)
    summary   = gap_summary(resume_skills, jd_skills, skill_gap)
    roadmap   = generate_roadmap(skill_gap, resume_skills)
    impact    = compute_training_time_saved(resume_skills, skill_gap)

    return JSONResponse(content={
        "summary":       summary,
        "resume_skills": resume_skills,
        "jd_skills":     jd_skills,
        "skill_gap":     skill_gap,
        "roadmap":       roadmap,
        "reasoning":     reasoning,
        "product_impact": impact,
        "meta": {
            "processing_ms":   round((time.perf_counter()-t0)*1000,1),
            "nlp_engine":      "spaCy" if _SPACY_AVAILABLE else "pure-Python NLP",
            "catalog_grounded": True,
            "resume_filename": resume_file.filename,
            "jd_filename":     jd_file.filename,
        },
    })

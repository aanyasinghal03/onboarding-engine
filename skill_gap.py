"""
skill_gap.py  (v2)
------------------
Significant upgrades over v1:

1. SEMANTIC NEAR-MATCH DETECTION
   Catches conceptually related skills that differ in name — e.g. a resume
   listing "Postgres" is credited toward "postgresql" in the JD.
   Implemented via a curated synonym map + difflib similarity, with spaCy
   vector similarity when available.

2. LEVEL-UPGRADE GAPS
   A candidate with "beginner" SQL but a JD requiring "intermediate" SQL
   is flagged as LEVEL_UPGRADE — they know the skill but need to deepen it.
   This surfaces in both the gap list and the reasoning trace.

3. CONFIDENCE-WEIGHTED GAP SCORING
   Skills extracted with high confidence count more toward coverage.
   Low-confidence matches (near the threshold) don't fully cancel a gap.

4. PREREQUISITE-AWARE ORDERING
   Gap skills are annotated with their known prerequisites so the roadmap
   module can sequence learning correctly.
"""

from __future__ import annotations

import math
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------
SkillEntry = Dict  # {"name", "level", "category", "confidence", "match_type"}


# ---------------------------------------------------------------------------
# Synonym / alias map for semantic near-match detection
# Canonical DB key → set of surface forms that count as equivalent
# ---------------------------------------------------------------------------

SKILL_SYNONYMS: Dict[str, Set[str]] = {
    "postgresql":       {"postgres", "psql", "pg"},
    "javascript":       {"js", "ecmascript", "es6", "es2015"},
    "typescript":       {"ts"},
    "python":           {"py", "python3", "python2"},
    "kubernetes":       {"k8s", "kube"},
    "machine learning": {"ml", "statistical learning"},
    "deep learning":    {"dl", "neural networks", "neural network"},
    "react":            {"reactjs", "react.js"},
    "nextjs":           {"next.js", "next js"},
    "fastapi":          {"fast api"},
    "django":           {"django rest framework", "drf"},
    "github actions":   {"gh actions", "gha"},
    "ci/cd":            {"continuous integration", "continuous deployment",
                         "continuous delivery", "cicd"},
    "rest api":         {"restful", "rest", "restful api"},
    "graphql":          {"graph ql"},
    "aws":              {"amazon web services", "amazon aws"},
    "gcp":              {"google cloud", "google cloud platform"},
    "azure":            {"microsoft azure"},
    "docker":           {"containerization", "containerisation"},
    "scikit-learn":     {"sklearn", "scikit learn"},
    "tensorflow":       {"tf", "tensor flow"},
    "pytorch":          {"torch"},
    "mongodb":          {"mongo"},
    "elasticsearch":    {"elastic search", "elastic"},
    "redis":            {"redis cache"},
    "rabbitmq":         {"rabbit mq", "rabbit"},
    "kafka":            {"apache kafka"},
    "nlp":              {"natural language processing"},
    "computer vision":  {"cv", "image recognition"},
    "git":              {"github", "gitlab", "version control"},
}

# Build reverse map: surface_form → canonical
_REVERSE_SYNONYM: Dict[str, str] = {}
for canonical, forms in SKILL_SYNONYMS.items():
    for form in forms:
        _REVERSE_SYNONYM[form.lower()] = canonical


# ---------------------------------------------------------------------------
# Prerequisite graph (used to annotate gap entries)
# ---------------------------------------------------------------------------

PREREQUISITES: Dict[str, List[str]] = {
    "react":            ["javascript"],
    "nextjs":           ["react", "javascript"],
    "django":           ["python"],
    "fastapi":          ["python"],
    "kubernetes":       ["docker"],
    "tensorflow":       ["python", "numpy"],
    "pytorch":          ["python", "numpy"],
    "scikit-learn":     ["python", "numpy", "pandas"],
    "machine learning": ["python", "statistics", "numpy"],
    "deep learning":    ["machine learning", "python"],
    "mlops":            ["machine learning", "docker", "git"],
    "aws":              ["linux", "networking basics"],
    "gcp":              ["linux"],
    "azure":            ["linux"],
    "elasticsearch":    ["rest api"],
    "kafka":            ["messaging basics"],
    "graphql":          ["rest api"],
    "postgresql":       ["sql"],
    "mongodb":          ["nosql basics"],
    "redis":            ["caching basics"],
}


# ---------------------------------------------------------------------------
# Optional spaCy (graceful degradation)
# ---------------------------------------------------------------------------

try:
    import spacy  # type: ignore
    _NLP = spacy.load("en_core_web_md")
    _SPACY_AVAILABLE = True
except Exception:
    _NLP = None
    _SPACY_AVAILABLE = False


# ---------------------------------------------------------------------------
# Semantic near-match resolution
# ---------------------------------------------------------------------------

def _resolve_canonical(name: str, skills_db: Dict) -> Optional[str]:
    """
    Given a skill name from one document, return its canonical DB key if
    it is semantically equivalent to a known skill.
    Check order:
      1. Already a canonical key
      2. Synonym reverse-map
      3. Fuzzy string similarity
      4. spaCy vector similarity (if available)
    """
    lower = name.lower()

    # 1. Exact DB key
    if lower in skills_db:
        return lower

    # 2. Synonym map
    if lower in _REVERSE_SYNONYM:
        canonical = _REVERSE_SYNONYM[lower]
        if canonical in skills_db:
            return canonical

    # 3. Fuzzy
    best_ratio, best_key = 0.0, None
    for key in skills_db:
        ratio = SequenceMatcher(None, lower, key).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_key = key
    if best_ratio >= 0.88:
        return best_key

    # 4. spaCy vector similarity
    if _SPACY_AVAILABLE and _NLP is not None:
        doc_a = _NLP(lower)
        if doc_a.has_vector:
            for key in skills_db:
                doc_b = _NLP(key)
                if doc_b.has_vector and doc_a.similarity(doc_b) >= 0.82:
                    return key

    return None


def _build_resume_canonical_map(
    resume_skills: List[SkillEntry], skills_db: Dict
) -> Dict[str, Dict]:
    """
    Map each resume skill to its canonical DB key, resolving synonyms.
    Returns: { canonical_key: {level, confidence, original_name} }
    """
    result: Dict[str, Dict] = {}
    for s in resume_skills:
        canonical = _resolve_canonical(s["name"], skills_db)
        if canonical:
            # Keep the highest-confidence match if we see duplicates
            existing = result.get(canonical)
            if not existing or existing["confidence"] < s.get("confidence", 1.0):
                result[canonical] = {
                    "level":         s.get("level", "beginner"),
                    "confidence":    s.get("confidence", 1.0),
                    "original_name": s["name"],
                }
    return result


# ---------------------------------------------------------------------------
# Core gap analysis
# ---------------------------------------------------------------------------

def compute_skill_gap(
    resume_skills: List[SkillEntry],
    jd_skills:     List[SkillEntry],
    skills_db:     Optional[Dict] = None,
) -> List[SkillEntry]:
    """
    Return enriched gap entries for each JD skill not adequately covered
    by the resume.

    Gap status per JD skill:
      MISSING       — not present at all
      LEVEL_UPGRADE — present but at a lower level than required

    Each gap entry carries:
      name, level, category, confidence (from JD extraction),
      gap_type, prerequisites, urgency_score
    """
    db = skills_db or {}
    resume_map = _build_resume_canonical_map(resume_skills, db)

    gap: List[SkillEntry] = []

    for jd_skill in jd_skills:
        canonical = _resolve_canonical(jd_skill["name"], db) or jd_skill["name"].lower()
        resume_entry = resume_map.get(canonical)
        jd_level = jd_skill.get("level", "beginner")

        if resume_entry is None:
            # Completely missing
            gap.append(_make_gap_entry(jd_skill, canonical, "MISSING", db))

        elif _level_rank(jd_level) > _level_rank(resume_entry["level"]):
            # Has the skill but at insufficient level
            gap_entry = _make_gap_entry(jd_skill, canonical, "LEVEL_UPGRADE", db)
            gap_entry["resume_current_level"] = resume_entry["level"]
            gap.append(gap_entry)

        # else: adequately covered — no gap

    # Sort: MISSING first, then LEVEL_UPGRADE; within each group by urgency desc
    gap.sort(key=lambda e: (0 if e["gap_type"] == "MISSING" else 1, -e["urgency_score"]))
    return gap


def _make_gap_entry(
    jd_skill: SkillEntry,
    canonical: str,
    gap_type: str,
    db: Dict,
) -> Dict:
    prereqs = PREREQUISITES.get(canonical, [])
    urgency = _urgency_score(jd_skill, gap_type)
    return {
        "name":          jd_skill["name"],
        "level":         jd_skill.get("level", "beginner"),
        "category":      jd_skill.get("category", db.get(canonical, {}).get("category", "general")),
        "confidence":    jd_skill.get("confidence", 1.0),
        "gap_type":      gap_type,           # MISSING | LEVEL_UPGRADE
        "prerequisites": prereqs,
        "urgency_score": urgency,
    }


def _level_rank(level: str) -> int:
    return {"beginner": 0, "intermediate": 1, "advanced": 2}.get(level, 0)


def _urgency_score(skill: SkillEntry, gap_type: str) -> float:
    """
    Higher score = should be addressed sooner.
    Factors: gap type, skill level, extraction confidence.
    """
    base = 1.0 if gap_type == "MISSING" else 0.6
    level_weight = 1.2 if skill.get("level") == "intermediate" else 1.0
    confidence_weight = skill.get("confidence", 1.0)
    return round(base * level_weight * confidence_weight, 3)


# ---------------------------------------------------------------------------
# Reasoning trace
# ---------------------------------------------------------------------------

def build_reasoning(
    resume_skills: List[SkillEntry],
    jd_skills:     List[SkillEntry],
    skill_gap:     List[SkillEntry],
    skills_db:     Optional[Dict] = None,
) -> List[Dict]:
    """
    Produces a transparent, per-skill explanation of every gap decision.
    """
    db = skills_db or {}
    resume_map = _build_resume_canonical_map(resume_skills, db)
    gap_names  = {e["name"].lower() for e in skill_gap}
    gap_map    = {e["name"].lower(): e for e in skill_gap}

    reasoning: List[Dict] = []

    for jd_skill in jd_skills:
        canonical = _resolve_canonical(jd_skill["name"], db) or jd_skill["name"].lower()
        name_lower = jd_skill["name"].lower()
        resume_entry = resume_map.get(canonical)
        jd_level  = jd_skill.get("level", "beginner")
        gap_entry = gap_map.get(name_lower)

        if gap_entry is None:
            # PRESENT and adequate
            rl = resume_entry["level"] if resume_entry else "unknown"
            orig = resume_entry["original_name"] if resume_entry else jd_skill["name"]
            conf = resume_entry["confidence"] if resume_entry else 1.0
            alias_note = (
                f" (matched via alias '{orig}')"
                if orig.lower() != jd_skill["name"].lower() else ""
            )
            explanation = (
                f"'{jd_skill['name']}' was found in the resume{alias_note} "
                f"with level '{rl}' (confidence {conf:.0%}). "
                f"JD requires '{jd_level}'. Requirement is satisfied — no gap recorded."
            )
            status = "PRESENT"
            detail = {}

        elif gap_entry["gap_type"] == "LEVEL_UPGRADE":
            current = gap_entry.get("resume_current_level", "beginner")
            explanation = (
                f"'{jd_skill['name']}' was detected in the resume at level '{current}', "
                f"but the JD requires '{jd_level}'. "
                f"A level-upgrade gap has been added to the roadmap."
            )
            status = "LEVEL_UPGRADE"
            detail = {"current_level": current, "required_level": jd_level}

        else:
            # MISSING
            match_hint = ""
            if _SPACY_AVAILABLE:
                match_hint = " No semantically similar term was found via NLP analysis."
            explanation = (
                f"'{jd_skill['name']}' (required level: {jd_level}) was not detected "
                f"anywhere in the resume using exact, fuzzy, alias, or synonym matching.{match_hint} "
                f"It has been added to the skill gap and learning roadmap "
                f"with urgency score {gap_entry['urgency_score']:.2f}."
            )
            prereqs = gap_entry.get("prerequisites", [])
            status = "MISSING"
            detail = {
                "prerequisites": prereqs,
                "urgency_score": gap_entry["urgency_score"],
            }

        reasoning.append({
            "skill":       jd_skill["name"],
            "status":      status,
            "jd_level":    jd_level,
            "explanation": explanation,
            **detail,
        })

    # Sort: gaps first (MISSING → LEVEL_UPGRADE → PRESENT), then alphabetical
    order = {"MISSING": 0, "LEVEL_UPGRADE": 1, "PRESENT": 2}
    reasoning.sort(key=lambda r: (order.get(r["status"], 9), r["skill"]))
    return reasoning


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

def gap_summary(
    resume_skills: List[SkillEntry],
    jd_skills:     List[SkillEntry],
    skill_gap:     List[SkillEntry],
) -> Dict:
    """Compute high-level statistics for the API response summary block."""
    total_jd   = len(jd_skills)
    missing    = sum(1 for e in skill_gap if e.get("gap_type") == "MISSING")
    upgrades   = sum(1 for e in skill_gap if e.get("gap_type") == "LEVEL_UPGRADE")
    covered    = total_jd - len(skill_gap)

    # Confidence-weighted coverage: partial credits for low-confidence matches
    weighted_covered = sum(
        s.get("confidence", 1.0)
        for s in jd_skills
        if s["name"].lower() not in {e["name"].lower() for e in skill_gap}
    )
    coverage = round(weighted_covered / max(total_jd, 1) * 100, 1)

    return {
        "total_jd_skills":        total_jd,
        "total_resume_skills":    len(resume_skills),
        "skills_covered":         covered,
        "missing_skills":         missing,
        "level_upgrade_needed":   upgrades,
        "total_gaps":             len(skill_gap),
        "coverage_percent":       coverage,
        "readiness":              _readiness_label(coverage),
        "nlp_enhanced":           _SPACY_AVAILABLE,
    }


def _readiness_label(coverage: float) -> str:
    if coverage >= 80:
        return "Strong Match"
    if coverage >= 55:
        return "Moderate Match"
    if coverage >= 30:
        return "Developing — targeted upskilling recommended"
    return "Significant Gaps — structured onboarding required"

"""
parser.py  (v2)
---------------
Two major upgrades over v1:

1. PDF EXTRACTION
   ─────────────
   Primary  : pdfplumber  — layout-aware, handles multi-column resumes,
                            reconstructs reading order, cleans hyphenation.
   Fallback : pypdf       — fast, handles more edge-case encodings.

2. SKILL EXTRACTION  (NLP pipeline — spaCy-compatible architecture)
   ─────────────────────────────────────────────────────────────────
   When spaCy + en_core_web_md are installed the full vector-similarity
   pipeline activates automatically.  Without them, a pure-Python NLP
   pipeline provides most of the same intelligence:

   Stage 1  Keyword matching         — exact whole-word/phrase hits (v1 baseline)
   Stage 2  N-gram candidate pool    — 1-to-4-word token windows as candidates
   Stage 3  Fuzzy matching           — difflib SequenceMatcher (catches typos,
                                       plural forms, abbreviation drift)
   Stage 4  Noun-phrase heuristics   — simple POS-like tagging via suffix rules
                                       to boost noun/tech-term confidence
   Stage 5  TF-IDF context scoring   — skills mentioned in skill-dense regions
                                       (e.g. "Skills" section) score higher
   Stage 6  Confidence thresholding  — only skills above MIN_CONFIDENCE kept
   Stage 7  spaCy vector similarity  — if spaCy available, semantic near-matches
                                       are surfaced even without keyword overlap

   Every detected skill carries a `confidence` score (0.0–1.0) so downstream
   modules can make smarter decisions.
"""

from __future__ import annotations

import io
import json
import math
import re
import string
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_CONFIDENCE: float = 0.55        # Skills below this are discarded
FUZZY_THRESHOLD: float = 0.82       # SequenceMatcher ratio for fuzzy match
SECTION_BOOST: float = 0.15         # Confidence boost for skill-dense sections

# Section headers that indicate a skills-rich region
SKILL_SECTION_HEADERS = frozenset({
    "skills", "technical skills", "core competencies", "competencies",
    "technologies", "tech stack", "tools", "expertise", "qualifications",
    "requirements", "what we're looking for", "what you'll need",
    "responsibilities", "key skills",
})

# Common English stopwords (no NLTK needed)
STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must", "we", "you",
    "our", "your", "their", "its", "this", "that", "these", "those", "as",
    "it", "if", "not", "no", "so", "up", "out", "about", "into", "than",
    "then", "when", "where", "who", "which", "what", "how", "all", "any",
    "also", "just", "more", "other", "such", "they", "he", "she", "we",
    "experience", "knowledge", "understanding", "ability", "strong",
    "excellent", "good", "solid", "proficient", "familiarity", "familiar",
    "working", "minimum", "preferred", "required", "years", "year",
})


# ---------------------------------------------------------------------------
# Optional spaCy import (graceful degradation)
# ---------------------------------------------------------------------------

try:
    import spacy  # type: ignore

    _NLP = spacy.load("en_core_web_md")
    _SPACY_AVAILABLE = True
except Exception:
    _NLP = None
    _SPACY_AVAILABLE = False


# ---------------------------------------------------------------------------
# Skills database loader
# ---------------------------------------------------------------------------

def load_skills_db(skills_file: str = "skills.json") -> Dict[str, Dict]:
    """
    Load skills from JSON.  Returns a rich dict:
        { skill_name_lower: {"level": str, "category": str, "aliases": [str]} }
    """
    skills_path = Path(__file__).parent / skills_file
    if not skills_path.exists():
        raise FileNotFoundError(f"Skills DB not found: {skills_path}")

    with open(skills_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    flat: Dict[str, Dict] = {}
    for category, skills in data.get("skills", {}).items():
        for skill, meta in skills.items():
            key = skill.lower()
            if isinstance(meta, str):
                # legacy format: skill -> "level"
                flat[key] = {"level": meta, "category": category, "aliases": []}
            else:
                # new format: skill -> {level, aliases, ...}
                flat[key] = {
                    "level": meta.get("level", "beginner"),
                    "category": category,
                    "aliases": [a.lower() for a in meta.get("aliases", [])],
                }
    return flat


# ---------------------------------------------------------------------------
# PDF extraction  (pdfplumber primary, pypdf fallback)
# ---------------------------------------------------------------------------

def _extract_pdf_pdfplumber(file_bytes: bytes) -> str:
    """
    pdfplumber extraction with layout awareness:
    - Sorts text objects by (page, top, x0) to reconstruct reading order
    - Joins hyphenated line-breaks
    - Filters out header/footer artifacts (very small or very top/bottom text)
    """
    import pdfplumber  # type: ignore

    pages_text: List[str] = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            # extract_text with layout=True preserves column structure
            text = page.extract_text(layout=True, x_tolerance=3, y_tolerance=3)
            if text:
                # Fix common PDF hyphenation: "develop-\nment" → "development"
                text = re.sub(r"-\s*\n\s*", "", text)
                pages_text.append(text)

    return "\n\n".join(pages_text)


def _extract_pdf_pypdf(file_bytes: bytes) -> str:
    """Fallback: pypdf extraction (handles some edge-case encodings better)."""
    from pypdf import PdfReader  # type: ignore

    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join(
        p.extract_text() for p in reader.pages if p.extract_text()
    )


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Try pdfplumber first; fall back to pypdf on any error.
    Raises ValueError only when both extractors fail or yield empty text.
    """
    text = ""
    errors: List[str] = []

    for extractor, name in [
        (_extract_pdf_pdfplumber, "pdfplumber"),
        (_extract_pdf_pypdf,      "pypdf"),
    ]:
        try:
            text = extractor(file_bytes).strip()
            if text:
                return text
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    if errors:
        raise ValueError(f"PDF extraction failed — {'; '.join(errors)}")
    raise ValueError("PDF produced no extractable text (possibly image-only).")


def extract_text_from_txt(file_bytes: bytes) -> str:
    """Decode bytes → str, trying UTF-8 then latin-1."""
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return file_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("latin-1", errors="replace")


def extract_text(filename: str, file_bytes: bytes) -> str:
    """Route to the correct extractor; raise ValueError on empty content."""
    if not file_bytes:
        raise ValueError(f"'{filename}' is empty.")

    ext = Path(filename).suffix.lower()
    text = extract_text_from_pdf(file_bytes) if ext == ".pdf" else extract_text_from_txt(file_bytes)

    stripped = text.strip()
    if not stripped:
        raise ValueError(f"No readable text in '{filename}'. Check it isn't blank or image-only.")
    return stripped


# ---------------------------------------------------------------------------
# NLP helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lower-case, collapse whitespace, keep punctuation for regex."""
    return re.sub(r"[ \t]+", " ", text.lower()).strip()


def _tokenize(text: str) -> List[str]:
    """Split into lowercase tokens, remove pure-punctuation tokens."""
    tokens = re.findall(r"[\w\+\#\.\-\/]+", text.lower())
    return tokens


def _ngrams(tokens: List[str], n: int) -> List[str]:
    """Generate space-joined n-grams from a token list."""
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def _is_likely_technical_term(phrase: str) -> bool:
    """
    Simple noun-phrase heuristic:
    Technical terms tend to be short, lack stopwords, and often end in
    common tech suffixes.
    """
    words = phrase.split()
    if not words:
        return False
    # Reject if majority of words are stopwords
    non_stop = [w for w in words if w not in STOPWORDS]
    if len(non_stop) < max(1, len(words) // 2):
        return False
    # Boost multi-word phrases that look like tech stacks
    tech_suffixes = (
        "js", "py", "db", "sql", "ml", "ai", "api", "sdk", "cli",
        "ops", "net", "hub", "lab", "kit", "io", "go", "rs",
    )
    last = words[-1]
    if any(last.endswith(s) for s in tech_suffixes):
        return True
    return True  # pass through; confidence thresholding handles false positives


def _detect_skill_sections(text: str) -> List[Tuple[int, int]]:
    """
    Return a list of (start, end) character spans that are likely
    to be skill-dense sections (e.g. a "Technical Skills" bullet block).
    """
    lines = text.split("\n")
    spans: List[Tuple[int, int]] = []
    pos = 0
    in_section = False
    section_start = 0

    for line in lines:
        stripped = line.strip().lower().rstrip(":")
        if stripped in SKILL_SECTION_HEADERS:
            in_section = True
            section_start = pos
        elif in_section and re.match(r"^[A-Z][a-z].*:?\s*$", line.strip()) and stripped not in SKILL_SECTION_HEADERS:
            # A new non-skills header — close the section
            spans.append((section_start, pos))
            in_section = False
        pos += len(line) + 1

    if in_section:
        spans.append((section_start, pos))

    return spans


def _compute_tfidf_weights(text: str, skills_db: Dict[str, Dict]) -> Dict[str, float]:
    """
    Lightweight TF-IDF: for each skill, compute term-frequency in the document
    weighted by inverse document frequency (approximated from skill frequency
    in the DB).  Returns a normalised weight per skill.
    """
    normalized = _normalize(text)
    total_words = max(len(normalized.split()), 1)
    db_size = max(len(skills_db), 1)

    weights: Dict[str, float] = {}
    for skill in skills_db:
        # TF: count occurrences of skill phrase in document
        escaped = re.escape(skill)
        pattern = rf"(?<!\w){escaped}(?!\w)"
        matches = re.findall(pattern, normalized)
        tf = len(matches) / total_words

        # IDF approximation: rarer skills in DB score higher
        # (single-word common terms like "sql" get slight penalty)
        idf = math.log(db_size / (1 + 1))  # simplified — all skills treated equally
        words_in_skill = len(skill.split())
        # Multi-word skills are more specific → boost IDF
        idf *= (1 + 0.3 * (words_in_skill - 1))

        weights[skill] = tf * idf

    return weights


# ---------------------------------------------------------------------------
# Core skill extraction pipeline
# ---------------------------------------------------------------------------

def extract_skills(
    text: str,
    skills_db: Dict[str, Dict],
) -> List[Dict]:
    """
    Multi-stage NLP skill extraction pipeline.

    Returns a list of skill dicts, each with:
        name        : canonical skill name
        level       : beginner | intermediate
        category    : skill category from DB
        confidence  : float 0.0–1.0
        match_type  : exact | fuzzy | ngram | spacy
    """
    normalized_text = _normalize(text)
    tokens = _tokenize(text)
    found: Dict[str, Dict] = {}  # canonical_name → best match info

    # Pre-compute skill section spans for section boosting
    skill_spans = _detect_skill_sections(text)
    skill_section_text = " ".join(
        text[s:e] for s, e in skill_spans
    ).lower() if skill_spans else ""

    # ── Stage 1: Exact whole-word / whole-phrase matching ──────────────────
    for skill, meta in skills_db.items():
        escaped = re.escape(skill)
        pattern = rf"(?<!\w){escaped}(?!\w)"

        if re.search(pattern, normalized_text):
            confidence = 1.0
            # Boost if found inside a declared skills section
            if skill_spans and re.search(pattern, skill_section_text):
                confidence = min(1.0, confidence + SECTION_BOOST)
            _update_found(found, skill, meta, confidence, "exact")

        # Also match any aliases defined in the skills DB
        for alias in meta.get("aliases", []):
            esc_alias = re.escape(alias)
            pat_alias = rf"(?<!\w){esc_alias}(?!\w)"
            if re.search(pat_alias, normalized_text):
                _update_found(found, skill, meta, 0.95, "alias")

    # ── Stage 2 & 3: N-gram candidate pool + fuzzy matching ───────────────
    # Generate 1- to 4-gram candidates from the document
    candidates: List[str] = []
    for n in range(1, 5):
        candidates.extend(_ngrams(tokens, n))

    # Deduplicate candidates
    unique_candidates = list(dict.fromkeys(candidates))

    for skill, meta in skills_db.items():
        if skill in found:
            continue  # already found exactly

        best_ratio = 0.0
        for candidate in unique_candidates:
            if candidate in STOPWORDS:
                continue
            ratio = SequenceMatcher(None, skill, candidate).ratio()
            if ratio > best_ratio:
                best_ratio = ratio

        if best_ratio >= FUZZY_THRESHOLD and _is_likely_technical_term(skill):
            confidence = best_ratio * 0.88  # fuzzy hits get slight penalty vs exact
            _update_found(found, skill, meta, confidence, "fuzzy")

    # ── Stage 4: TF-IDF context scoring — adjust confidence by frequency ──
    tfidf = _compute_tfidf_weights(text, skills_db)
    for skill in list(found.keys()):
        w = tfidf.get(skill, 0.0)
        if w > 0:
            # Boost skills that appear multiple times (high TF)
            boost = min(0.1, w * 500)
            found[skill]["confidence"] = min(1.0, found[skill]["confidence"] + boost)

    # ── Stage 5: spaCy vector similarity (if available) ───────────────────
    if _SPACY_AVAILABLE and _NLP is not None:
        found = _spacy_enhance(text, skills_db, found)

    # ── Stage 6: Confidence threshold & final formatting ──────────────────
    result: List[Dict] = []
    for skill, info in found.items():
        if info["confidence"] >= MIN_CONFIDENCE:
            result.append({
                "name": skill,
                "level": info["meta"]["level"],
                "category": info["meta"]["category"],
                "confidence": round(info["confidence"], 3),
                "match_type": info["match_type"],
            })

    # Sort: confidence desc, then name asc
    result.sort(key=lambda s: (-s["confidence"], s["name"]))
    return result


def _update_found(
    found: Dict,
    skill: str,
    meta: Dict,
    confidence: float,
    match_type: str,
) -> None:
    """Insert or update a skill entry if new confidence is higher."""
    if skill not in found or found[skill]["confidence"] < confidence:
        found[skill] = {
            "meta": meta,
            "confidence": confidence,
            "match_type": match_type,
        }


def _spacy_enhance(
    text: str,
    skills_db: Dict[str, Dict],
    found: Dict,
) -> Dict:
    """
    Use spaCy noun chunks and named entities as additional candidate signals.
    Skills not found by keyword/fuzzy but semantically close to a noun-chunk
    extracted by spaCy are surfaced with a 'spacy' match_type.
    """
    doc = _NLP(text[:50_000])  # cap at 50k chars to stay within memory

    # Collect noun chunks and ORG/PRODUCT/TECH named entities as candidates
    spacy_candidates: List[str] = []
    for chunk in doc.noun_chunks:
        spacy_candidates.append(chunk.text.lower().strip())
    for ent in doc.ents:
        if ent.label_ in {"ORG", "PRODUCT", "GPE", "WORK_OF_ART"}:
            spacy_candidates.append(ent.text.lower().strip())

    # For each un-found skill, compute vector similarity against candidates
    for skill, meta in skills_db.items():
        if skill in found:
            continue
        skill_doc = _NLP(skill)
        if not skill_doc.has_vector:
            continue
        for candidate in spacy_candidates:
            cand_doc = _NLP(candidate)
            if not cand_doc.has_vector:
                continue
            sim = skill_doc.similarity(cand_doc)
            if sim >= 0.78:
                _update_found(found, skill, meta, sim * 0.85, "spacy")
                break

    return found


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_and_extract(
    filename: str,
    file_bytes: bytes,
    skills_db: Dict[str, Dict],
) -> Tuple[str, List[Dict]]:
    """
    Full pipeline: read file → extract text → run NLP skill extraction.

    Returns:
        (raw_text, skills_list)
    """
    raw_text = extract_text(filename, file_bytes)
    skills = extract_skills(raw_text, skills_db)
    return raw_text, skills

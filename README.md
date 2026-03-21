# SkillBridge — AI Adaptive Onboarding Engine

> **Zero hallucinations. Catalog-grounded. Cross-domain. Reasoning-transparent.**

SkillBridge analyses a candidate's résumé against a job description, identifies skill gaps using a multi-stage NLP pipeline, and generates a personalised, prerequisite-ordered learning roadmap — all grounded strictly in a locked course catalog with no AI-generated course names.

---

## Live Demo

```
https://skillbridge.onrender.com
```

---

## Key Features

| Feature | Detail |
|---|---|
| **Multi-Stage NLP** | Exact match → Fuzzy (difflib) → Alias resolution → N-gram → TF-IDF section boosting → spaCy vectors (optional) |
| **Zero Hallucinations** | Every course recommendation read from `course_catalog.json` — no free-text generation |
| **Gap Types** | `MISSING` (skill absent) and `LEVEL_UPGRADE` (skill present but below required level) |
| **Reasoning Trace** | Per-skill explanation of every gap decision with match type and confidence |
| **Prerequisite Ordering** | Topological sort (Kahn's algorithm) ensures Docker before Kubernetes, Python before Django |
| **Product Impact** | Calculates redundant training hours avoided vs targeted learning hours required |
| **Cross-Domain** | 12 domains: Tech, Healthcare, Operations/Labor, Education, Business, Security, and more |
| **84+ Skills** | Covering 12 job categories from software engineers to nurses to warehouse operators |

---

## Project Structure

```
onboarding_engine/
├── main.py              # FastAPI app — serves UI + /analyze endpoint
├── parser.py            # PDF parsing (pdfplumber → pypdf) + NLP extraction
├── skill_gap.py         # Gap analysis with synonym resolution + level detection
├── roadmap.py           # Catalog-grounded roadmap with topological ordering
├── skills.json          # 84+ skills across 12 domains with aliases
├── course_catalog.json  # Locked course catalog — only source for recommendations
├── index.html           # SkillBridge UI — golden dots, animated, tabbed results
└── requirements.txt
```

---

## How It Works

### 1. Skill Extraction Pipeline

```
Document Text
      ↓
[Stage 1] Exact whole-word / whole-phrase regex match
      ↓
[Stage 2] Alias matching (postgres → postgresql, k8s → kubernetes)
      ↓
[Stage 3] N-gram candidate pool (1–4 word windows)
      ↓
[Stage 4] Fuzzy matching via difflib SequenceMatcher (threshold: 0.82)
      ↓
[Stage 5] TF-IDF weighting + skill-section header detection boost
      ↓
[Stage 6] spaCy vector similarity (if installed)
      ↓
Confidence-scored skill list
```

### 2. Gap Analysis

- **Synonym resolution** — `postgres` on résumé correctly matches `postgresql` in JD
- **MISSING** — skill not found anywhere in résumé
- **LEVEL_UPGRADE** — skill found but at lower level than JD requires
- **Confidence-weighted coverage** — low-confidence matches contribute partial credit

### 3. Roadmap Generation (Zero Hallucination)

```python
# roadmap.py — all courses come from course_catalog.json
catalog_courses = _get_courses(skill_name, level)
# Returns locked catalog entries only.
# If skill not in catalog → uses 'default' fallback entry.
# NEVER generates course names via LLM.
```

Each roadmap entry includes:
- Phase assignment (Foundation / Core Mastery / Applied)
- Prerequisite warning if dependencies are missing
- Catalog-verified courses with direct URLs
- Hands-on project suggestion
- Effort estimate in weeks and hours

### 4. Reasoning Trace

Every JD skill gets one of three verdicts:
- `PRESENT` — found with explanation of match type and confidence
- `MISSING` — not found after exhausting all matching stages
- `LEVEL_UPGRADE` — found but below required level

---

## Cross-Domain Coverage

| Domain | Example Skills |
|---|---|
| Software Engineering | Python, React, Docker, Kubernetes, AWS, PostgreSQL |
| Data / ML | Machine Learning, TensorFlow, PyTorch, NLP, MLOps |
| Healthcare | Patient Care, EHR, HIPAA, Triage, Medication Administration |
| Operations / Labor | Inventory Management, Six Sigma, Forklift Operation, OSHA |
| Education | Curriculum Development, IEP, Differentiated Instruction |
| Business | Excel, Salesforce, SAP, Power BI, Project Management |
| Security | Cybersecurity, OAuth, Penetration Testing, SIEM |

---

## Product Impact Metric

SkillBridge calculates the **training efficiency gain** for every analysis:

```
Redundant Training Avoided = Σ(hours for skills candidate already has)
Focused Learning Required  = Σ(hours for gap skills × 2)
Efficiency Gain %          = Avoided / (Avoided + Required) × 100
```

This directly addresses the cost of blanket onboarding programmes that retrain employees on skills they already possess.

---

## Setup

### 1. Clone
```bash
git clone https://github.com/aanyasinghal03/onboarding-engine.git
cd onboarding-engine
```

### 2. Virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Optional — spaCy for full NLP pipeline
```bash
pip install spacy
python -m spacy download en_core_web_md
```

### 5. Run
```bash
uvicorn main:app --reload
```

### 6. Open
```
http://127.0.0.1:8000
```

---

## API

### `POST /analyze`

**Input:** `multipart/form-data`
- `resume_file` — PDF or .txt
- `jd_file` — PDF or .txt

**Output:**
```json
{
  "summary":        { "coverage_percent": 54.1, "readiness": "Moderate Match", ... },
  "resume_skills":  [{ "name": "python", "level": "intermediate", "confidence": 0.98 }],
  "jd_skills":      [...],
  "skill_gap":      [{ "name": "kubernetes", "gap_type": "MISSING", "urgency_score": 1.2 }],
  "roadmap":        [{ "skill": "kubernetes", "catalog_courses": [...], "steps": [...] }],
  "reasoning":      [{ "skill": "kubernetes", "status": "MISSING", "explanation": "..." }],
  "product_impact": { "redundant_training_hours_avoided": 84, "efficiency_gain_percent": 62.3 }
}
```

### `GET /health`
Returns NLP engine status, skill DB stats, catalog grounding status, and PDF extractors.

---

## Tech Stack

- **FastAPI** — async Python web framework
- **pdfplumber** — layout-aware PDF text extraction (primary)
- **pypdf** — PDF fallback extractor
- **difflib** — fuzzy skill matching
- **spaCy** — optional vector similarity (en_core_web_md)
- **Vanilla JS + Canvas** — animated frontend, zero framework dependencies

---

## Rubric Alignment

| Criterion | Implementation |
|---|---|
| Technical Sophistication | 6-stage NLP pipeline, synonym resolution, confidence scoring, topological sort |
| Grounding & Reliability | `course_catalog.json` — all courses locked, catalog_id on every entry, `grounded: true` flag |
| Reasoning Trace | Per-skill PRESENT/MISSING/LEVEL_UPGRADE with match type + confidence |
| Product Impact | `compute_training_time_saved()` — hours avoided vs hours required |
| User Experience | Tabbed UI, animated pipeline viz, collapsible roadmap cards, course cards with direct URLs |
| Cross-Domain Scalability | 12 domains, 84+ skills: tech + healthcare + operations + education + business |
| Documentation | This README + inline code comments throughout all modules |

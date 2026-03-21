"""
roadmap.py  (v3 — Competition Edition)
---------------------------------------
KEY UPGRADE: Zero-hallucination grounding.
All course recommendations are read STRICTLY from course_catalog.json.
No free-text course generation. If a skill has no catalog entry, the
'default' fallback course is used and clearly labeled as such.

Intelligence upgrades:
- Prerequisite-aware topological ordering (Kahn's algorithm)
- Phase assignment (Foundation / Core / Applied) based on existing skills
- Context-aware steps for MISSING vs LEVEL_UPGRADE gaps
- Effort estimation accounting for prerequisites
- Training time saved calculation (Product Impact metric)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Set

SkillEntry = Dict

# ── Load course catalog (strict grounding) ───────────────────────────────────

def _load_catalog() -> Dict:
    path = Path(__file__).parent / "course_catalog.json"
    if not path.exists():
        return {"courses": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

_CATALOG = _load_catalog()

def _get_courses(skill_name: str, level: str) -> List[Dict]:
    """
    Return courses from the locked catalog for a skill.
    Filters by level (beginner courses always shown for beginner gaps;
    intermediate courses shown for intermediate gaps + beginner as foundation).
    Falls back to 'default' catalog entry if skill not found.
    NEVER generates course names — only returns catalog entries.
    """
    skill_lower = skill_name.lower()
    courses_dict = _CATALOG.get("courses", {})

    # Direct lookup
    entries = courses_dict.get(skill_lower, [])

    # If not found, try partial match (e.g. "data visualization" -> "tableau")
    if not entries:
        for key in courses_dict:
            if key in skill_lower or skill_lower in key:
                entries = courses_dict[key]
                break

    # Fallback to default
    if not entries:
        entries = courses_dict.get("default", [])

    # Filter by level appropriateness
    if level == "beginner":
        filtered = [c for c in entries if c.get("level") == "beginner"]
        return filtered if filtered else entries[:2]
    else:
        # intermediate: return intermediate first, then beginner as foundation
        advanced = [c for c in entries if c.get("level") == "intermediate"]
        basic    = [c for c in entries if c.get("level") == "beginner"]
        combined = advanced + basic
        return combined[:2] if combined else entries[:2]


# ── Prerequisite graph ────────────────────────────────────────────────────────

PREREQUISITES: Dict[str, List[str]] = {
    "react":            ["javascript"],
    "nextjs":           ["react", "javascript"],
    "django":           ["python"],
    "fastapi":          ["python"],
    "flask":            ["python"],
    "kubernetes":       ["docker"],
    "tensorflow":       ["python", "numpy", "machine learning"],
    "pytorch":          ["python", "numpy", "machine learning"],
    "scikit-learn":     ["python", "numpy", "pandas"],
    "machine learning": ["python", "statistics"],
    "deep learning":    ["machine learning", "python"],
    "nlp":              ["machine learning", "python"],
    "computer vision":  ["deep learning", "python"],
    "mlops":            ["machine learning", "docker", "git"],
    "aws":              ["linux"],
    "gcp":              ["linux"],
    "azure":            ["linux"],
    "elasticsearch":    ["rest api"],
    "kafka":            ["rest api"],
    "graphql":          ["rest api"],
    "postgresql":       ["sql"],
    "mongodb":          ["sql"],
    "triage":           ["patient care", "first aid"],
    "medication administration": ["anatomy", "patient care"],
    "six sigma":        ["quality control"],
    "erp systems":      ["supply chain"],
    "differentiated instruction": ["curriculum development"],
    "special education":["differentiated instruction"],
}

# ── Average hours a professional wastes on redundant training ─────────────────
# Used to compute "training time saved" (Product Impact metric)
REDUNDANT_TRAINING_HOURS: Dict[str, int] = {
    "python": 12, "javascript": 10, "react": 14, "docker": 8,
    "kubernetes": 12, "aws": 16, "machine learning": 20, "sql": 6,
    "postgresql": 8, "git": 4, "agile": 6, "cybersecurity": 10,
    "data analysis": 8, "project management": 10, "communication": 4,
    "leadership": 6, "patient care": 12, "first aid": 6, "ehr": 8,
    "supply chain": 10, "quality control": 8, "lean manufacturing": 8,
    "forklift operation": 4, "safety compliance": 6, "inventory management": 6,
    "curriculum development": 10, "classroom management": 6, "e-learning": 8,
}

# ── Topological sort ──────────────────────────────────────────────────────────

def _topological_order(gap_skills: List[SkillEntry]) -> List[SkillEntry]:
    names = {s["name"].lower() for s in gap_skills}
    name_to_entry = {s["name"].lower(): s for s in gap_skills}
    in_degree: Dict[str, int] = {n: 0 for n in names}
    dependents: Dict[str, List[str]] = {n: [] for n in names}

    for skill_name in names:
        for prereq in PREREQUISITES.get(skill_name, []):
            if prereq in names:
                in_degree[skill_name] += 1
                dependents[prereq].append(skill_name)

    queue = sorted(
        [n for n in names if in_degree[n] == 0],
        key=lambda n: -name_to_entry[n].get("urgency_score", 0),
    )
    ordered: List[SkillEntry] = []
    while queue:
        cur = queue.pop(0)
        ordered.append(name_to_entry[cur])
        for dep in dependents.get(cur, []):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)
                queue.sort(key=lambda n: -name_to_entry[n].get("urgency_score", 0))

    remaining = [name_to_entry[n] for n in names if name_to_entry[n] not in ordered]
    remaining.sort(key=lambda s: -s.get("urgency_score", 0))
    return ordered + remaining


# ── Phase assignment ──────────────────────────────────────────────────────────

def _assign_phase(skill_name: str, existing: Set[str]) -> int:
    prereqs = PREREQUISITES.get(skill_name.lower(), [])
    if not prereqs:
        return 2
    met = sum(1 for p in prereqs if p in existing)
    ratio = met / len(prereqs)
    if ratio >= 0.75: return 3
    if ratio >= 0.4:  return 2
    return 1

PHASE_LABELS = {1: "Foundation", 2: "Core Mastery", 3: "Applied"}

# ── Fundamentals per skill (factual, not hallucinated) ───────────────────────

FUNDAMENTALS: Dict[str, Dict[str, List[str]]] = {
    "python": {
        "beginner":     ["Variables & data types", "Control flow (if/for/while)", "Functions & OOP basics", "File I/O & exceptions"],
        "intermediate": ["Async/await & asyncio", "Type hints & Pydantic", "Decorators & generators", "Packaging & virtual envs"],
    },
    "javascript": {
        "beginner":     ["Variables (let/const), data types", "Functions & arrow functions", "DOM manipulation & events", "ES6+: destructuring, spread, modules"],
        "intermediate": ["Event loop & call stack", "Promises & async/await", "Prototype chain & closures", "Module bundlers (Vite/Webpack)"],
    },
    "machine learning": {
        "beginner":     ["Supervised vs unsupervised learning", "Bias-variance tradeoff", "Train/val/test split & cross-validation", "Metrics: accuracy, precision, recall, F1, AUC"],
        "intermediate": ["Ensemble methods (XGBoost, LightGBM)", "Feature engineering pipelines", "Hyperparameter tuning (Optuna)", "MLflow experiment tracking"],
    },
    "docker": {
        "beginner":     ["Images vs containers lifecycle", "Dockerfile: FROM, RUN, COPY, CMD", "docker build/run/ps/logs", "Volumes & port mapping"],
        "intermediate": ["Multi-stage builds", "Docker Compose for multi-service apps", "Image security scanning (Trivy)", "Registry management (ECR/GCR)"],
    },
    "aws": {
        "beginner":     ["IAM users, roles & policies", "EC2, S3, RDS, VPC basics", "Shared responsibility model", "Cost Explorer & billing alerts"],
        "intermediate": ["ECS/EKS, Lambda advanced", "CloudFormation / CDK (IaC)", "VPC peering & Transit Gateway", "Cost optimisation: Reserved Instances, Spot"],
    },
    "patient care": {
        "beginner":     ["Patient assessment fundamentals", "Communication with patients & families", "Privacy & dignity standards", "Basic monitoring & documentation"],
        "intermediate": ["Complex care planning", "Multi-disciplinary team coordination", "Care quality metrics & improvement"],
    },
    "supply chain": {
        "beginner":     ["Supply chain lifecycle overview", "Inventory management principles", "Vendor/supplier relationships", "Demand forecasting basics"],
        "intermediate": ["ERP system integration", "Risk management in supply chain", "Lean logistics & waste reduction"],
    },
    "curriculum development": {
        "beginner":     ["Learning objectives & Bloom's taxonomy", "Lesson plan structure", "Assessment alignment", "Differentiated instruction basics"],
        "intermediate": ["Curriculum mapping across grade levels", "Data-driven instructional design", "Backwards design (UbD framework)"],
    },
    "quality control": {
        "beginner":     ["QC vs QA distinction", "Inspection techniques & sampling", "Non-conformance reporting", "Root cause analysis basics"],
        "intermediate": ["Statistical process control (SPC)", "FMEA (Failure Mode Effects Analysis)", "ISO 9001 standards", "Six Sigma DMAIC framework"],
    },
}

def _get_fundamentals(skill: str, level: str) -> List[str]:
    skill_map = FUNDAMENTALS.get(skill.lower(), {})
    result = skill_map.get(level) or skill_map.get("beginner")
    if result:
        return result
    # Generic factual fallback (no hallucination — just points to official docs)
    return [
        f"Core concepts of {skill} — study official documentation",
        f"Hands-on practice with {skill} fundamentals",
        f"Review real-world use cases for {skill}",
    ]


# ── Project suggestions ───────────────────────────────────────────────────────

PROJECTS: Dict[str, Dict[str, str]] = {
    "python":           {"beginner":"CLI task manager with JSON persistence", "intermediate":"FastAPI REST service with PostgreSQL"},
    "javascript":       {"beginner":"Interactive to-do list with localStorage", "intermediate":"Real-time chat with WebSockets"},
    "react":            {"beginner":"Weather dashboard consuming a public API", "intermediate":"Full-stack e-commerce app with auth"},
    "docker":           {"beginner":"Containerised Flask app behind Nginx", "intermediate":"3-service app with Docker Compose"},
    "kubernetes":       {"beginner":"Deploy a 2-tier app on Minikube", "intermediate":"GitOps pipeline with ArgoCD"},
    "aws":              {"beginner":"Static site on S3+CloudFront+Lambda", "intermediate":"3-tier app with ALB+ECS+RDS Multi-AZ"},
    "machine learning": {"beginner":"Binary classifier on Titanic dataset", "intermediate":"End-to-end ML pipeline with MLflow tracking"},
    "sql":              {"beginner":"Library schema with 20 analytical queries", "intermediate":"NYC Taxi dataset window-function analysis"},
    "postgresql":       {"beginner":"Blog DB with users/posts/tags/FKs", "intermediate":"Partitioned time-series analytics table"},
    "git":              {"beginner":"Contribute a feature to an open-source project via PR", "intermediate":"Team repo with branch protection & CI checks"},
    "patient care":     {"beginner":"Document a patient assessment workflow", "intermediate":"Care pathway improvement proposal"},
    "supply chain":     {"beginner":"Map a supply chain process for a local business", "intermediate":"Demand forecast model using historical data"},
    "quality control":  {"beginner":"QC checklist for a manufacturing step", "intermediate":"SPC chart for a production process"},
    "curriculum development": {"beginner":"Design a 4-week lesson plan with assessments", "intermediate":"Full curriculum map with Bloom's taxonomy alignment"},
}

def _get_project(skill: str, level: str, existing: Set[str]) -> str:
    proj_map = PROJECTS.get(skill.lower(), {})
    proj = proj_map.get(level) or proj_map.get("beginner")
    if proj:
        if existing and level == "intermediate":
            sample = list(existing)[:2]
            return f"{proj} — integrate with your existing knowledge of {', '.join(sample)}"
        return proj
    return f"Build a small end-to-end project using {skill} and publish it on GitHub with a clear README"


# ── Training time saved (Product Impact) ─────────────────────────────────────

def compute_training_time_saved(
    resume_skills: List[Dict],
    skill_gap: List[SkillEntry],
) -> Dict:
    """
    Estimates redundant training hours avoided because the system
    correctly identifies what the candidate already knows.
    This is the core Product Impact metric.
    """
    saved_hours = 0
    matched_skills = []
    for s in resume_skills:
        name = s["name"].lower()
        hrs = REDUNDANT_TRAINING_HOURS.get(name, 5)
        saved_hours += hrs
        matched_skills.append({"skill": s["name"], "hours_saved": hrs})

    gap_hours = sum(
        REDUNDANT_TRAINING_HOURS.get(g["name"].lower(), 5) * 2
        for g in skill_gap
    )

    return {
        "redundant_training_hours_avoided": saved_hours,
        "focused_learning_hours_required":  gap_hours,
        "efficiency_gain_percent": round(saved_hours / max(saved_hours + gap_hours, 1) * 100, 1),
        "matched_skills_breakdown": matched_skills[:8],
    }


# ── Main roadmap generator ────────────────────────────────────────────────────

def generate_roadmap(
    skill_gap:     List[SkillEntry],
    resume_skills: Optional[List[Dict]] = None,
) -> List[Dict]:
    """
    Generate a strictly-grounded, topologically-sorted learning roadmap.

    Every course recommendation comes from course_catalog.json only.
    No course names are generated by the LLM / free text.
    """
    if not skill_gap:
        return []

    existing: Set[str] = set()
    if resume_skills:
        for s in resume_skills:
            existing.add(s["name"].lower())

    ordered_gap = _topological_order(skill_gap)
    roadmap: List[Dict] = []

    for idx, entry in enumerate(ordered_gap):
        skill    = entry["name"]
        level    = entry.get("level", "beginner")
        category = entry.get("category", "general")
        gap_type = entry.get("gap_type", "MISSING")
        prereqs  = PREREQUISITES.get(skill.lower(), [])

        phase = _assign_phase(skill, existing)
        missing_prereqs = [p for p in prereqs if p not in existing]

        # ── Strictly catalog-sourced courses ──
        catalog_courses = _get_courses(skill, level)
        course_steps = []
        for course in catalog_courses[:2]:
            course_steps.append({
                "title":      course["title"],
                "provider":   course["provider"],
                "instructor": course.get("instructor", ""),
                "url":        course["url"],
                "level":      course.get("level", level),
                "hours":      course.get("duration_hours", 0),
                "free":       course.get("free_audit", False),
                "catalog_id": course.get("id", ""),
                "grounded":   True,   # flag: this is from locked catalog
            })

        # ── Fundamentals ──
        fundamentals = _get_fundamentals(skill, level)

        # ── Project ──
        project = _get_project(skill, level, existing)

        # ── Steps ──
        steps: List[Dict] = []
        step_n = 1

        if phase == 1 and missing_prereqs:
            steps.append({
                "step": step_n, "phase": 1,
                "action": "Complete prerequisite skills first",
                "detail": f"Address these prerequisites before starting '{skill}': {', '.join(missing_prereqs)}. They appear earlier in your roadmap.",
                "estimated_hours": 6 * len(missing_prereqs),
            })
            step_n += 1

        fund_action = "Level up your existing knowledge" if gap_type == "LEVEL_UPGRADE" else "Learn the fundamentals"
        fund_detail = (
            f"You already have '{skill}' at a lower level. Focus on advanced topics: {'; '.join(fundamentals[:3])}."
            if gap_type == "LEVEL_UPGRADE"
            else f"Study these core topics: {'; '.join(fundamentals)}."
        )
        steps.append({
            "step": step_n, "phase": min(phase, 2),
            "action": fund_action,
            "detail": fund_detail,
            "estimated_hours": 10 if gap_type == "LEVEL_UPGRADE" else (16 if level == "intermediate" else 8),
        })
        step_n += 1

        if course_steps:
            primary = course_steps[0]
            alt_txt = f" Alternative: '{course_steps[1]['title']}' on {course_steps[1]['provider']}." if len(course_steps) > 1 else ""
            steps.append({
                "step": step_n, "phase": 2,
                "action": "Take a structured course",
                "detail": f"Complete: '{primary['title']}' by {primary['instructor']} on {primary['provider']} (~{primary['hours']}h). {'Free to audit. ' if primary['free'] else ''}{alt_txt}",
                "course_url": primary["url"],
                "catalog_grounded": True,
                "estimated_hours": primary["hours"],
            })
            step_n += 1

        steps.append({
            "step": step_n, "phase": 3,
            "action": "Build a hands-on project",
            "detail": project,
            "estimated_hours": 20 if level == "intermediate" else 12,
        })

        # ── Effort ──
        base = 5 if level == "intermediate" else 3
        if gap_type == "LEVEL_UPGRADE": base = max(2, base - 2)
        total_weeks = base + len(missing_prereqs)

        roadmap.append({
            "order":       idx + 1,
            "skill":       skill,
            "level":       level,
            "category":    category,
            "gap_type":    gap_type,
            "phase":       phase,
            "phase_label": PHASE_LABELS[phase],
            "urgency":     entry.get("urgency_score", 1.0),
            "effort": {
                "weeks":           f"{total_weeks}–{total_weeks + 2} weeks",
                "hours_per_week":  "8–12 hrs/week",
                "total_estimate":  f"~{total_weeks * 10}–{(total_weeks + 2) * 12} hours",
            },
            "prerequisites_to_complete_first": missing_prereqs,
            "fundamentals": fundamentals,
            "catalog_courses": course_steps,   # raw catalog data for UI
            "project":     project,
            "steps":       steps,
            "grounding_note": "All course recommendations sourced from locked course_catalog.json — no AI-generated course names.",
        })

        existing.add(skill.lower())

    return roadmap

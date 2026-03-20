"""
roadmap.py  (v2)
-----------------
Intelligent roadmap generation with four major improvements over v1:

1. PHASE-BASED LEARNING PATH
   Instead of a flat 3-step list, each skill gets assigned to one of three
   learning phases based on its prerequisites and the candidate's existing
   skills:
     Phase 1 — Foundation    (learn concepts + prerequisites first)
     Phase 2 — Core Mastery  (take a structured course, build solo project)
     Phase 3 — Applied       (integrate with other skills, production project)

2. PREREQUISITE SEQUENCING
   The full roadmap is topologically sorted so skills that are prerequisites
   for others appear earlier.  Learning Kubernetes before Docker would be
   wrong — this prevents that.

3. CONTEXT-AWARE STEP GENERATION
   Steps are personalised based on:
     - gap_type  (MISSING vs LEVEL_UPGRADE → different advice)
     - existing skills the candidate already has
     - skill category (data/ML vs DevOps vs web vs soft-skills)

4. EFFORT & SCHEDULE ESTIMATION
   Each skill gets a realistic week estimate that accounts for:
     - Skill level (beginner / intermediate)
     - Number of missing prerequisites
     - Whether it's a LEVEL_UPGRADE (shorter) or MISSING (longer)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------
SkillEntry = Dict  # enriched gap entry from skill_gap.py


# ---------------------------------------------------------------------------
# Rich content catalogue
# Keyed by canonical skill name.  Each entry has beginner + intermediate
# sub-keys with: fundamentals, courses (list), projects (list by level),
# docs_url, and practice_platform.
# ---------------------------------------------------------------------------

SKILL_CATALOGUE: Dict[str, Dict] = {
    "python": {
        "beginner": {
            "fundamentals": [
                "Variables, data types (int/float/str/list/dict/set)",
                "Control flow: if/elif/else, for/while loops",
                "Functions, default args, *args/**kwargs",
                "OOP: classes, inheritance, dunder methods",
                "File I/O, exception handling, context managers",
            ],
            "courses": [
                "Python for Everybody – Coursera / University of Michigan (free audit)",
                "Automate the Boring Stuff with Python – Al Sweigart (free online)",
            ],
            "projects": [
                "CLI task manager persisting tasks to JSON",
                "Web scraper using requests + BeautifulSoup",
            ],
            "docs": "https://docs.python.org/3/",
            "practice": "https://exercism.org/tracks/python",
        },
        "intermediate": {
            "fundamentals": [
                "Async/await, asyncio event loop",
                "Type hints, mypy, Pydantic models",
                "Decorators, generators, context managers (deep)",
                "Concurrency: threading vs multiprocessing vs asyncio",
                "Packaging: pyproject.toml, virtual envs, pip",
            ],
            "courses": [
                "Complete Python Bootcamp – Udemy (Jose Portilla)",
                "Python Concurrency with asyncio – Manning",
            ],
            "projects": [
                "FastAPI microservice with async DB calls and JWT auth",
                "CLI dev tool published as a PyPI package",
            ],
            "docs": "https://realpython.com/",
            "practice": "https://leetcode.com/",
        },
    },
    "javascript": {
        "beginner": {
            "fundamentals": [
                "Variables (var/let/const), data types, type coercion",
                "Functions, arrow functions, closures",
                "DOM manipulation, events, fetch API",
                "ES6+: destructuring, spread, template literals, modules",
                "Promises and async/await",
            ],
            "courses": [
                "The Complete JavaScript Course 2024 – Udemy (Jonas Schmedtmann)",
                "JavaScript.info – free comprehensive reference",
            ],
            "projects": [
                "Interactive to-do list with localStorage persistence",
                "Weather app using fetch + a public REST API",
            ],
            "docs": "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
            "practice": "https://exercism.org/tracks/javascript",
        },
        "intermediate": {
            "fundamentals": [
                "Event loop, call stack, microtasks vs macrotasks",
                "Prototype chain, class inheritance",
                "Module bundlers: Webpack/Vite",
                "Testing: Jest, Testing Library",
                "TypeScript integration",
            ],
            "courses": [
                "JavaScript: The Hard Parts v2 – Frontend Masters",
                "You Don't Know JS – Kyle Simpson (free on GitHub)",
            ],
            "projects": [
                "Real-time chat app using WebSockets (Socket.io)",
                "Drag-and-drop kanban board with undo/redo history",
            ],
            "docs": "https://javascript.info/",
            "practice": "https://www.codewars.com/",
        },
    },
    "react": {
        "beginner": {
            "fundamentals": [
                "JSX syntax and how Babel transforms it",
                "Components: functional vs class, props vs state",
                "Hooks: useState, useEffect, useRef, useContext",
                "Conditional rendering, lists, keys",
                "React DevTools and component debugging",
            ],
            "courses": [
                "React – The Complete Guide 2024 – Udemy (Maximilian Schwarzmüller)",
                "The official React docs (react.dev) – Start Here section",
            ],
            "projects": [
                "Weather dashboard consuming a public API",
                "Hacker News reader with search and pagination",
            ],
            "docs": "https://react.dev/",
            "practice": "https://codesandbox.io/",
        },
        "intermediate": {
            "fundamentals": [
                "State management: Redux Toolkit, Zustand, Jotai",
                "Performance: memo, useMemo, useCallback, code splitting",
                "Server components vs client components (Next.js)",
                "Testing with Vitest + React Testing Library",
                "Accessibility (ARIA, keyboard navigation)",
            ],
            "courses": [
                "Epic React – Kent C. Dodds (epicreact.dev)",
                "React Query (TanStack Query) docs – official",
            ],
            "projects": [
                "Full-stack e-commerce app with cart, auth, and Stripe checkout",
                "Collaborative real-time whiteboard using CRDT",
            ],
            "docs": "https://react.dev/reference/react",
            "practice": "https://www.frontendmentor.io/",
        },
    },
    "docker": {
        "beginner": {
            "fundamentals": [
                "Images vs containers: lifecycle and layering",
                "Dockerfile instructions: FROM, RUN, COPY, CMD, ENTRYPOINT",
                "docker build, run, ps, stop, rm, logs",
                "Volumes and bind mounts",
                "Port mapping and basic networking (bridge network)",
            ],
            "courses": [
                "Docker & Kubernetes: The Complete Guide – Udemy (Stephen Grider)",
                "Play with Docker – free browser-based labs (labs.play-with-docker.com)",
            ],
            "projects": [
                "Containerise a Python Flask app with Nginx reverse proxy",
                "Multi-container dev environment with Docker Compose",
            ],
            "docs": "https://docs.docker.com/",
            "practice": "https://labs.play-with-docker.com/",
        },
        "intermediate": {
            "fundamentals": [
                "Multi-stage builds for lean production images",
                "Docker Compose override files for dev/staging/prod",
                "Image security: non-root users, image scanning (Trivy)",
                "Docker networking deep dive: overlay, macvlan",
                "Registry management: ECR, GCR, Harbor",
            ],
            "courses": [
                "Docker Deep Dive – Pluralsight (Nigel Poulton)",
                "Docker official reference docs",
            ],
            "projects": [
                "Microservices system (3+ services) with Compose + health checks",
                "CI pipeline that builds, tests, and pushes a multi-arch image",
            ],
            "docs": "https://docs.docker.com/reference/",
            "practice": "https://killercoda.com/",
        },
    },
    "kubernetes": {
        "beginner": {
            "fundamentals": [
                "Architecture: control plane, nodes, etcd, kubelet",
                "Core objects: Pod, Deployment, Service (ClusterIP/NodePort/LB)",
                "ConfigMaps and Secrets",
                "kubectl: get, describe, apply, logs, exec",
                "Namespaces, resource quotas, limit ranges",
            ],
            "courses": [
                "Kubernetes for the Absolute Beginners – Udemy (Mumshad Mannambeth)",
                "Kubernetes: Up & Running – O'Reilly book",
            ],
            "projects": [
                "Deploy a 2-tier app on local Minikube with LoadBalancer",
                "Rollout, rollback, and HPA demo on a sample microservice",
            ],
            "docs": "https://kubernetes.io/docs/home/",
            "practice": "https://killercoda.com/playgrounds/scenario/kubernetes",
        },
        "intermediate": {
            "fundamentals": [
                "Helm v3: charts, values, templating, chart repos",
                "RBAC: Roles, ClusterRoles, service accounts",
                "Ingress controllers (Nginx, Traefik) and TLS termination",
                "Persistent volumes, storage classes, StatefulSets",
                "Operators and Custom Resource Definitions (CRDs)",
            ],
            "courses": [
                "CKA Exam Prep – Linux Foundation (official)",
                "Kubernetes Mastery – Udemy (Bret Fisher)",
            ],
            "projects": [
                "GitOps pipeline with ArgoCD deploying to a multi-env cluster",
                "Stateful database cluster (PostgreSQL + Patroni) on K8s",
            ],
            "docs": "https://kubernetes.io/docs/concepts/",
            "practice": "https://killer.sh/",
        },
    },
    "aws": {
        "beginner": {
            "fundamentals": [
                "Global infrastructure: regions, AZs, edge locations",
                "IAM: users, roles, policies, least-privilege principle",
                "Core services: EC2, S3, RDS, VPC, Route 53",
                "Billing dashboard, Cost Explorer, Free Tier limits",
                "Shared responsibility model",
            ],
            "courses": [
                "AWS Certified Cloud Practitioner – Stephane Maarek (Udemy)",
                "AWS Skill Builder – free official learning platform",
            ],
            "projects": [
                "Static website: S3 + CloudFront + Route 53",
                "Serverless contact form: API Gateway + Lambda + SES",
            ],
            "docs": "https://docs.aws.amazon.com/",
            "practice": "https://aws.amazon.com/free/",
        },
        "intermediate": {
            "fundamentals": [
                "Compute: ECS (Fargate), EKS, Lambda edge cases",
                "Networking deep dive: VPC peering, PrivateLink, Transit Gateway",
                "Infrastructure as Code: CloudFormation / CDK",
                "Observability: CloudWatch, X-Ray, AWS Config",
                "Cost optimisation: Reserved Instances, Savings Plans, Spot",
            ],
            "courses": [
                "AWS Certified Solutions Architect Associate – Stephane Maarek (Udemy)",
                "AWS Advanced Networking Specialty – Adrian Cantrill",
            ],
            "projects": [
                "3-tier app with ALB + ECS Fargate + RDS Multi-AZ + CDK",
                "Event-driven pipeline: S3 → Lambda → DynamoDB → SNS",
            ],
            "docs": "https://aws.amazon.com/architecture/",
            "practice": "https://wellarchitectedlabs.com/",
        },
    },
    "machine learning": {
        "beginner": {
            "fundamentals": [
                "Supervised vs unsupervised vs reinforcement learning",
                "Bias-variance tradeoff, overfitting, regularisation",
                "Core algorithms: linear/logistic regression, decision trees, k-NN",
                "Train/validation/test split, cross-validation",
                "Metrics: accuracy, precision, recall, F1, AUC-ROC",
            ],
            "courses": [
                "Machine Learning Specialisation – Andrew Ng (Coursera)",
                "Fast.ai Practical Deep Learning (for coders) – free",
            ],
            "projects": [
                "Binary classifier on Titanic dataset; evaluate all metrics",
                "House price regression with feature engineering",
            ],
            "docs": "https://scikit-learn.org/stable/user_guide.html",
            "practice": "https://www.kaggle.com/",
        },
        "intermediate": {
            "fundamentals": [
                "Ensemble methods: Random Forest, Gradient Boosting (XGBoost, LightGBM)",
                "Hyperparameter optimisation: Optuna, grid search",
                "Feature engineering: encoding, scaling, imputation pipelines",
                "Model explainability: SHAP, LIME",
                "Experiment tracking: MLflow, Weights & Biases",
            ],
            "courses": [
                "Hands-On ML with Scikit-Learn, Keras & TensorFlow – O'Reilly (Aurélien Géron)",
                "Full Stack Deep Learning – free (fullstackdeeplearning.com)",
            ],
            "projects": [
                "End-to-end pipeline: feature store → training → MLflow → FastAPI",
                "Kaggle competition top-25% submission with full write-up",
            ],
            "docs": "https://mlflow.org/docs/latest/index.html",
            "practice": "https://www.kaggle.com/competitions",
        },
    },
    "sql": {
        "beginner": {
            "fundamentals": [
                "SELECT, FROM, WHERE, ORDER BY, LIMIT",
                "INNER / LEFT / RIGHT / FULL JOINs",
                "GROUP BY, HAVING, aggregate functions",
                "Subqueries, EXISTS, IN",
                "Indexes, primary keys, foreign keys, ACID",
            ],
            "courses": [
                "The Complete SQL Bootcamp – Udemy (Jose Portilla)",
                "SQLZoo – free interactive browser exercises",
            ],
            "projects": [
                "Normalised library schema with 20 analytical queries",
                "Sales dashboard queries against a sample Northwind DB",
            ],
            "docs": "https://www.postgresql.org/docs/current/",
            "practice": "https://sqlzoo.net/",
        },
        "intermediate": {
            "fundamentals": [
                "Window functions: ROW_NUMBER, RANK, LAG, LEAD, running totals",
                "CTEs (WITH clause) and recursive CTEs",
                "Query optimisation: EXPLAIN ANALYZE, index strategies",
                "Stored procedures, triggers, views, materialised views",
                "Transactions, isolation levels, deadlock handling",
            ],
            "courses": [
                "Advanced SQL for Data Scientists – Mode Analytics (free)",
                "PostgreSQL: Up and Running – O'Reilly",
            ],
            "projects": [
                "Analytical dashboard on NYC Taxi dataset using window functions",
                "Performance optimisation: reduce query time by 10× using indexes + CTEs",
            ],
            "docs": "https://use-the-index-luke.com/",
            "practice": "https://pgexercises.com/",
        },
    },
    "git": {
        "beginner": {
            "fundamentals": [
                "init, clone, add, commit, push, pull",
                "Branches: create, switch, merge, delete",
                "Resolving merge conflicts",
                ".gitignore, commit messages best practices",
                "Pull requests / code review workflow on GitHub/GitLab",
            ],
            "courses": [
                "Git & GitHub for Beginners – freeCodeCamp (YouTube, free)",
                "Learn Git Branching – interactive browser game (learngitbranching.js.org)",
            ],
            "projects": [
                "Contribute a real feature to an open-source project via PR",
            ],
            "docs": "https://git-scm.com/doc",
            "practice": "https://learngitbranching.js.org/",
        },
        "intermediate": {
            "fundamentals": [
                "Rebasing, interactive rebase (squash, fixup, reorder)",
                "Cherry-pick, reflog, bisect for debugging",
                "Git hooks (pre-commit, commit-msg)",
                "Gitflow vs trunk-based development",
                "Monorepo strategies",
            ],
            "courses": [
                "Pro Git – Scott Chacon (free at git-scm.com/book)",
                "Git for Professionals – freeCodeCamp (YouTube)",
            ],
            "projects": [
                "Set up a team repo: branch protection, CODEOWNERS, required reviews, CI",
            ],
            "docs": "https://git-scm.com/book/en/v2",
            "practice": "https://ohshitgit.com/",
        },
    },
    "postgresql": {
        "beginner": {
            "fundamentals": [
                "Install, psql CLI, pgAdmin basics",
                "Data types: text, numeric, boolean, JSONB, arrays, UUID",
                "DDL: CREATE TABLE, ALTER, DROP, constraints",
                "User management, roles, schema isolation",
            ],
            "courses": [
                "Learn PostgreSQL – freeCodeCamp (YouTube, free)",
                "PostgreSQL Tutorial – postgresqltutorial.com (free)",
            ],
            "projects": [
                "Blog database: users, posts, comments, tags with FKs",
            ],
            "docs": "https://www.postgresql.org/docs/",
            "practice": "https://pgexercises.com/",
        },
        "intermediate": {
            "fundamentals": [
                "JSONB operators, full-text search, pg_trgm",
                "Partitioning: range, list, hash",
                "Replication: streaming, logical, pg_basebackup",
                "Connection pooling: PgBouncer",
                "VACUUM, ANALYZE, autovacuum tuning",
            ],
            "courses": [
                "PostgreSQL: Up and Running – Regina Obe & Leo Hsu (O'Reilly)",
            ],
            "projects": [
                "Analytics platform: partitioned time-series table, materialised views, JSONB events",
            ],
            "docs": "https://www.postgresql.org/docs/current/performance-tips.html",
            "practice": "https://explain.dalibo.com/",
        },
    },
}

# ---------------------------------------------------------------------------
# Generic fallback template builder
# ---------------------------------------------------------------------------

_CATEGORY_TIPS = {
    "data_ml":      "Focus on hands-on experimentation with real datasets from Kaggle or UCI.",
    "cloud_devops": "Spin up a free-tier cloud account and build everything — theory alone won't stick.",
    "web_frameworks": "Build something real. Tutorial projects are fine to start, but ship a personal project ASAP.",
    "programming_languages": "Daily practice beats binge sessions. Aim for 30-45 focused minutes every day.",
    "databases":    "Use a realistic dataset (at least 100k rows) so you experience real performance considerations.",
    "security":     "Set up a local lab (VirtualBox / Docker) for safe hands-on practice.",
    "soft_skills":  "Apply the skill in your current role while learning. Real-world reps accelerate growth.",
    "tools":        "Integrate the tool into your daily workflow immediately — passive reading won't build muscle memory.",
}


def _generic_content(skill: str, level: str, category: str) -> Dict:
    tip = _CATEGORY_TIPS.get(category, "Build something tangible as early as possible.")
    return {
        "fundamentals": [
            f"Study the official documentation or the most highly-rated book for '{skill}'.",
            f"Focus on {level}-level concepts: understand the core primitives before advanced topics.",
            f"Category tip: {tip}",
        ],
        "courses": [
            f"Search Udemy / Coursera / Pluralsight for '{skill}' — filter by ★4.5+ and updated within 12 months.",
            "Check the official docs for a Getting Started guide; these are often the best first resource.",
        ],
        "projects": [
            f"Build a minimal but complete project that uses '{skill}' as its primary technology.",
            "Document it on GitHub with a clear README describing what you learned and what you'd do differently.",
        ],
        "docs": f"https://www.google.com/search?q={skill.replace(' ', '+')}+official+documentation",
        "practice": f"https://www.google.com/search?q={skill.replace(' ', '+')}+interactive+exercises",
    }


# ---------------------------------------------------------------------------
# Topological sort (prerequisite ordering)
# ---------------------------------------------------------------------------

from skill_gap import PREREQUISITES  # reuse the same graph


def _topological_order(gap_skills: List[SkillEntry]) -> List[SkillEntry]:
    """
    Sort gap skills so prerequisites come before dependents.
    Uses Kahn's algorithm (BFS-based topological sort).
    Cycles (unusual but possible) are broken by urgency score.
    """
    names = {s["name"].lower() for s in gap_skills}
    name_to_entry = {s["name"].lower(): s for s in gap_skills}

    # Build in-degree count within the gap (ignore prereqs outside the gap)
    in_degree: Dict[str, int] = {n: 0 for n in names}
    dependents: Dict[str, List[str]] = {n: [] for n in names}

    for skill_name in names:
        for prereq in PREREQUISITES.get(skill_name, []):
            if prereq in names:
                in_degree[skill_name] += 1
                dependents[prereq].append(skill_name)

    # Start with skills that have no in-gap prerequisites
    queue = sorted(
        [n for n in names if in_degree[n] == 0],
        key=lambda n: -name_to_entry[n].get("urgency_score", 0),
    )

    ordered: List[SkillEntry] = []
    while queue:
        current = queue.pop(0)
        ordered.append(name_to_entry[current])
        for dependent in dependents.get(current, []):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)
                queue.sort(key=lambda n: -name_to_entry[n].get("urgency_score", 0))

    # Append any remaining (cycle) nodes sorted by urgency
    remaining = [name_to_entry[n] for n in names if name_to_entry[n] not in ordered]
    remaining.sort(key=lambda s: -s.get("urgency_score", 0))
    return ordered + remaining


# ---------------------------------------------------------------------------
# Phase assignment
# ---------------------------------------------------------------------------

def _assign_phase(skill_name: str, resume_skill_names: Set[str]) -> int:
    """
    Assign a learning phase (1/2/3) based on how many prerequisites the
    candidate already possesses.
      Phase 1 – Few/no prereqs met  → lay foundation first
      Phase 2 – Some prereqs met    → direct skill building
      Phase 3 – Most prereqs met    → applied / integration work
    """
    prereqs = PREREQUISITES.get(skill_name.lower(), [])
    if not prereqs:
        return 2  # No prerequisites needed → jump straight to core work

    met = sum(1 for p in prereqs if p in resume_skill_names)
    ratio = met / len(prereqs)

    if ratio >= 0.75:
        return 3  # Most prereqs already known → focus on applied work
    if ratio >= 0.4:
        return 2
    return 1


# ---------------------------------------------------------------------------
# Step generation
# ---------------------------------------------------------------------------

def _build_steps(
    skill: str,
    level: str,
    category: str,
    gap_type: str,
    phase: int,
    content: Dict,
    existing_skills: Set[str],
) -> List[Dict]:
    """
    Build a tailored step list for one skill.
    Steps vary by gap_type and phase.
    """
    steps: List[Dict] = []
    step_num = 1

    # ── Step A: Prerequisites (Phase 1 only) ──────────────────────────────
    if phase == 1:
        missing_prereqs = [
            p for p in PREREQUISITES.get(skill.lower(), [])
            if p not in existing_skills
        ]
        if missing_prereqs:
            steps.append({
                "step":   step_num,
                "phase":  1,
                "action": "Address prerequisite gaps first",
                "detail": (
                    f"Before diving into '{skill}', build a foundation in: "
                    f"{', '.join(missing_prereqs)}. These prerequisites appear "
                    f"earlier in your roadmap."
                ),
                "estimated_hours": 8 * len(missing_prereqs),
            })
            step_num += 1

    # ── Step B: Fundamentals ───────────────────────────────────────────────
    fundamentals = content.get("fundamentals", [])
    if gap_type == "LEVEL_UPGRADE":
        fund_detail = (
            f"You already have '{skill}' at a lower level. Deepen your knowledge by focusing on "
            f"advanced/intermediate topics: {'; '.join(fundamentals[:3])}."
        )
        estimated_hours = 10
    else:
        fund_detail = (
            f"Study these core topics in order: {'; '.join(fundamentals)}. "
            f"Use the official docs as your primary reference: {content.get('docs', 'N/A')}."
        )
        estimated_hours = 15 if level == "intermediate" else 8

    steps.append({
        "step":            step_num,
        "phase":           1 if phase == 1 else 2,
        "action":          "Learn the fundamentals" if gap_type == "MISSING" else "Level up your knowledge",
        "detail":          fund_detail,
        "estimated_hours": estimated_hours,
    })
    step_num += 1

    # ── Step C: Structured course ──────────────────────────────────────────
    courses = content.get("courses", [])
    course_detail = (
        f"Complete at least one structured course. Recommended: {courses[0]}. "
        + (f"Alternative: {courses[1]}." if len(courses) > 1 else "")
        + f" Practice interactively at: {content.get('practice', 'see docs')}."
    )
    steps.append({
        "step":            step_num,
        "phase":           2,
        "action":          "Take a structured course",
        "detail":          course_detail,
        "estimated_hours": 20 if level == "intermediate" else 12,
    })
    step_num += 1

    # ── Step D: Project ────────────────────────────────────────────────────
    projects = content.get("projects", [])
    if phase == 3:
        project_instruction = (
            f"Build an integration project that combines '{skill}' with skills you already have "
            f"({', '.join(list(existing_skills)[:3])}). Suggested: {projects[-1] if projects else 'a real-world project'}."
        )
    elif gap_type == "LEVEL_UPGRADE":
        project_instruction = (
            f"Rebuild a previous project using '{skill}' at the '{level}' level, applying the "
            f"advanced techniques you've just learned. Suggested: {projects[-1] if projects else 'a challenging project'}."
        )
    else:
        project_instruction = (
            f"Build a solo project from scratch. Suggested: {projects[0] if projects else 'a demo project'}. "
            f"Share it publicly on GitHub — this also demonstrates the skill to employers."
        )

    steps.append({
        "step":            step_num,
        "phase":           3,
        "action":          "Build a hands-on project",
        "detail":          project_instruction,
        "estimated_hours": 25 if level == "intermediate" else 15,
    })

    return steps


# ---------------------------------------------------------------------------
# Effort estimation
# ---------------------------------------------------------------------------

def _estimate_effort(
    level: str,
    gap_type: str,
    missing_prereq_count: int,
) -> Dict[str, str]:
    base_weeks = 5 if level == "intermediate" else 3
    if gap_type == "LEVEL_UPGRADE":
        base_weeks = max(1, base_weeks - 2)
    prereq_penalty = missing_prereq_count * 1  # 1 extra week per missing prereq
    total = base_weeks + prereq_penalty
    return {
        "weeks":          f"{total}–{total + 2} weeks",
        "hours_per_week": "8–12 hrs/week recommended",
        "total_estimate": f"~{total * 10}–{(total + 2) * 12} hours",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_roadmap(
    skill_gap:     List[SkillEntry],
    resume_skills: Optional[List[Dict]] = None,
) -> List[Dict]:
    """
    Generate an intelligent, sequenced learning roadmap.

    Args:
        skill_gap:     enriched gap entries from skill_gap.compute_skill_gap()
        resume_skills: candidate's existing skills (for context-aware steps)

    Returns:
        Ordered list of roadmap entries, topologically sorted by prerequisites.
    """
    if not skill_gap:
        return []

    # Build set of skills the candidate already has (lowercase canonical names)
    existing: Set[str] = set()
    if resume_skills:
        for s in resume_skills:
            existing.add(s["name"].lower())

    # Topological ordering
    ordered_gap = _topological_order(skill_gap)

    roadmap: List[Dict] = []

    for idx, entry in enumerate(ordered_gap):
        skill      = entry["name"]
        level      = entry.get("level", "beginner")
        category   = entry.get("category", "general")
        gap_type   = entry.get("gap_type", "MISSING")
        prereqs    = entry.get("prerequisites", [])

        # Look up content; fallback to generic
        content_map = SKILL_CATALOGUE.get(skill.lower(), {})
        content = (
            content_map.get(level)
            or content_map.get("beginner")
            or _generic_content(skill, level, category)
        )

        # Phase assignment
        phase = _assign_phase(skill, existing)

        # Missing prereqs within the gap
        missing_prereq_count = sum(
            1 for p in prereqs if p not in existing
        )

        # Build steps
        steps = _build_steps(
            skill, level, category, gap_type,
            phase, content, existing
        )

        # Effort estimate
        effort = _estimate_effort(level, gap_type, missing_prereq_count)

        roadmap.append({
            "order":       idx + 1,
            "skill":       skill,
            "level":       level,
            "category":    category,
            "gap_type":    gap_type,
            "phase":       phase,
            "urgency":     entry.get("urgency_score", 1.0),
            "effort":      effort,
            "prerequisites_to_complete_first": [
                p for p in prereqs if p not in existing
            ],
            "docs_url":   content.get("docs", ""),
            "practice_url": content.get("practice", ""),
            "steps":      steps,
        })

        # After processing, treat this skill as "in progress" so downstream
        # skills can reference it as being addressed
        existing.add(skill.lower())

    return roadmap

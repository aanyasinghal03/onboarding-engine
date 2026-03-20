# AI-Adaptive Onboarding Engine

A FastAPI backend that compares a candidate's resume against a job description,
identifies skill gaps, and generates a personalized step-by-step learning roadmap.

## Features
- PDF and text file parsing (pdfplumber + pypdf)
- Multi-stage NLP skill extraction with fuzzy matching and alias resolution
- Skill gap analysis with MISSING and LEVEL_UPGRADE detection
- Topologically-sorted, phase-aware learning roadmap
- spaCy integration (optional) for vector similarity matching

## Project Structure
```
onboarding_engine/
├── main.py          # FastAPI app + endpoints
├── parser.py        # PDF parsing + NLP extraction
├── skill_gap.py     # Gap analysis + reasoning trace
├── roadmap.py       # Learning roadmap generator
├── skills.json      # Skills database (84 skills)
└── requirements.txt
```

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/onboarding-engine.git
cd onboarding-engine
```

### 2. Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Optional — install spaCy for full NLP pipeline
```bash
pip install spacy
python -m spacy download en_core_web_md
```

### 5. Run the server
```bash
uvicorn main:app --reload
```

### 6. Open the API docs
Visit http://127.0.0.1:8000/docs

## API Usage

### POST /analyze
Upload a resume and job description to get:
- Extracted skills from both documents
- Skill gap analysis
- Personalized learning roadmap
- Reasoning trace
```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -F "resume_file=@resume.pdf" \
  -F "jd_file=@job_description.txt"
```

## Tech Stack
- FastAPI
- pdfplumber / pypdf
- spaCy (optional)
- Python 3.9+

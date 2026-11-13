<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Flask-2.3+-000000?logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/MongoDB-Atlas-47A248?logo=mongodb&logoColor=white" alt="MongoDB" />
  <img src="https://img.shields.io/badge/scikit--learn-1.2+-F7931E?logo=scikitlearn&logoColor=white" alt="scikit-learn" />
  <img src="https://img.shields.io/badge/License-MIT-blue" alt="License" />
</p>

# 🧠 Résumé Intelligence — AI-Powered Smart Recruitment Platform

> A full-stack, multimodal AI recruitment platform that automates resume parsing, skill extraction, job-description matching, candidate ranking, document authentication, aptitude profiling, personality insights, learning roadmap generation, and interview preparation — all powered by machine learning and NLP.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Usage Guide](#-usage-guide)
- [API Reference](#-api-reference)
- [Machine Learning Pipeline](#-machine-learning-pipeline)
- [Database Design](#-database-design)
- [Frontend Pages](#-frontend-pages)
- [Scoring Formula](#-scoring-formula)
- [Upgrade Path](#-upgrade-path)
- [Screenshots](#-screenshots)
- [Known Limitations](#-known-limitations)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🔍 Overview

**Résumé Intelligence** is an end-to-end AI-powered recruitment platform designed to streamline and automate the hiring pipeline. It serves two user roles:

- **Recruiters / HR**: Post jobs, manage candidates, rank applicants against job descriptions, authenticate documents, generate interview questions, and view analytics dashboards.
- **Candidates**: Build profiles, upload resumes for AI analysis, search and apply for jobs, get personalized skill-gap learning roadmaps, and track application status.

The platform uses machine learning (TF-IDF vectorization, classification models, cosine similarity, and optional Sentence Transformers) to intelligently score, classify, and rank resumes against job descriptions — providing data-driven hiring decisions.

---

## ✨ Key Features

### 🤖 AI & ML Core

| Feature | Description |
|---|---|
| **Resume Parsing** | Extracts text from PDF, DOCX, and TXT files with OCR fallback for scanned documents |
| **Category Classification** | Auto-classifies resumes into career categories (Data Science, Web Dev, Finance, HR, etc.) using trained ML models |
| **JD-Resume Matching** | Computes semantic similarity between resumes and job descriptions using TF-IDF cosine similarity (or Sentence Transformers) |
| **Skill Extraction** | Identifies 100+ technical and soft skills using NLP dictionary matching (upgradeable to spaCy NER) |
| **Candidate Ranking** | Ranks multiple candidates against a single JD with composite weighted scoring |
| **Education Extraction** | Parses degrees, institutions, GPAs, and academic credentials from resume text |
| **Experience Extraction** | Detects years of experience, job roles, and employment history via pattern matching |
| **Certification Detection** | Identifies AWS, GCP, Azure, Cisco, PMP, and other professional certifications |
| **Project Extraction** | Pulls key projects and achievements from resume content |

### 📊 Candidate Intelligence

| Feature | Description |
|---|---|
| **Aptitude Analysis** | AI-based cognitive profiling across Quantitative, Logical, Verbal, and Technical domains |
| **Personality Insights** | Big Five personality trait assessment (Conscientiousness, Openness, Collaboration, Resilience, Leadership) |
| **Multimodal Interview Assessment** | Combines speech analysis, video cues, and resume profile for composite hiring recommendations |
| **Interview Question Generation** | Auto-generates Technical, Behavioral, and Role-Specific interview questions based on JD and candidate profile |

### 📄 Document Authentication

| Feature | Description |
|---|---|
| **Neural Credential Classification** | Classifies documents using Sentence Transformers (all-MiniLM-L6-v2) across 6 credential categories |
| **Authenticity Verification** | Detects REAL vs FORGED documents with structural marker analysis |
| **Authority Registry** | Validates 15+ issuing authorities (AWS, Google, Stanford, MIT, Coursera, etc.) |
| **PII Redaction** | Auto-masks phone numbers, emails, SSNs, addresses, and serial codes for recruiter privacy |
| **Gemini LLM Verification** | Optional deep verification using Google Gemini Flash API for multimodal document inspection |
| **Live Web Corroboration** | Validates issuing institutions via Wikipedia and live web search |

### 🗺️ Skill Gap Roadmap Generator

| Feature | Description |
|---|---|
| **Personalized Learning Paths** | Generates Beginner → Intermediate → Advanced learning roadmaps for 50+ technologies |
| **Practice Activities** | Hands-on coding exercises and real-world scenarios for each missing skill |
| **Capstone Projects** | Portfolio-ready project ideas with deliverables for each skill |
| **Assessment Questions** | Self-evaluation questions with key answer points |
| **Timeline Estimation** | Estimated weeks and hours for each skill gap |
| **Curated Resources** | Official docs, courses, books, and interactive platforms for learning |

### 👥 Full Recruitment Workflow

| Feature | Description |
|---|---|
| **Role-Based Authentication** | Separate login flows for Admin, Recruiter, and Candidate with session isolation |
| **Job Management** | Create, edit, close, and manage job postings with salary ranges, requirements, and skills |
| **Candidate Management** | Full CRUD operations with search, filter, pagination, and status tracking |
| **Application Tracking** | Candidates apply to jobs; recruiters review, shortlist, interview, and offer/reject |
| **Analytics Dashboard** | Visual analytics for recruiters on hiring pipeline metrics |
| **Recruiter Dashboard** | Centralized overview of jobs, candidates, and applications |
| **Candidate Dashboard** | Personal hub for profile, applications, resume analysis, and roadmaps |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser)                            │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌────────────────┐   │
│  │  Login /  │  │ Candidate │  │ Recruiter │  │  Resume Check  │   │
│  │  Signup   │  │ Dashboard │  │ Dashboard │  │  / Job Search  │   │
│  └─────┬────┘  └─────┬─────┘  └─────┬─────┘  └───────┬────────┘   │
│        └──────────────┴──────────────┴────────────────┘            │
│                            REST API calls                          │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────────────┐
│                     FLASK BACKEND (app.py)                         │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │   Auth &   │  │  Candidate │  │   Job Mgmt   │  │ Application│ │
│  │  Session   │  │    CRUD    │  │     CRUD     │  │   Tracker  │ │
│  └────────────┘  └────────────┘  └──────────────┘  └───────────┘ │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  Resume    │  │  Document  │  │   Roadmap    │  │ Interview  │ │
│  │  Analysis  │  │  Verifier  │  │  Generator   │  │ Questions  │ │
│  └─────┬──────┘  └─────┬──────┘  └──────┬───────┘  └───────────┘ │
└────────┼───────────────┼────────────────┼─────────────────────────┘
         │               │                │
┌────────▼───────┐ ┌─────▼──────┐  ┌──────▼───────┐
│ intelligence.py│ │ document_  │  │  roadmap_    │
│ (ML Pipeline)  │ │ verifier.py│  │ generator.py │
│ TF-IDF, Cosine │ │ Neural NLP │  │ 50+ Skills   │
│ Classification │ │ Sentence   │  │ Knowledge    │
│ Skill Extract  │ │ Transformer│  │ Base         │
└────────┬───────┘ └────────────┘  └──────────────┘
         │
┌────────▼───────────────────────────────────────┐
│              DATABASE LAYER                     │
│  ┌──────────────┐    ┌───────────────────────┐ │
│  │ MongoDB Atlas │    │  Local MockDB / JSON  │ │
│  │  (Primary)   │◄──►│    (Fallback)         │ │
│  └──────────────┘    └───────────────────────┘ │
└────────────────────────────────────────────────┘
```

---

## 🛠 Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| **Python 3.10+** | Core language |
| **Flask 2.3+** | Web framework & REST API server |
| **scikit-learn 1.2+** | ML models (LogisticRegression, LinearSVC, RandomForest) |
| **Pandas / NumPy** | Data processing & numerical computation |
| **TF-IDF Vectorizer** | Text feature extraction (5000 features, bigrams) |
| **Sentence Transformers** | Semantic similarity (all-MiniLM-L6-v2) — optional |
| **XGBoost** | Gradient boosting classifier — optional |
| **spaCy** | NER-based skill extraction — optional |
| **pdfplumber** | PDF text extraction |
| **python-docx** | DOCX text extraction |
| **pytesseract / EasyOCR** | OCR for scanned documents — optional |
| **MongoDB (PyMongo)** | Primary database |
| **Joblib** | Model serialization & persistence |

### Frontend
| Technology | Purpose |
|---|---|
| **HTML5** | Semantic page structure (20+ pages) |
| **CSS3** | Custom design system with CSS variables |
| **Vanilla JavaScript** | Client-side logic, REST API integration, session management |
| **Google Fonts** | Playfair Display, Source Sans Pro, Source Code Pro |

### Database
| Technology | Purpose |
|---|---|
| **MongoDB Atlas** | Cloud-hosted primary database |
| **SQLite** | Legacy local database (migration supported) |
| **JSON MockDB** | Automatic fallback when Atlas is unreachable |

### External APIs (Optional)
| API | Purpose |
|---|---|
| **Google Gemini Flash** | Deep multimodal document verification |
| **Wikipedia OpenSearch** | Credential issuer corroboration |
| **DuckDuckGo Lite** | Live web institution verification |

---

## 📁 Project Structure

```
Resume-minor/
├── backend/
│   ├── app.py                    # Flask API server (3000+ lines)
│   │                             #   - Authentication (register/login/logout)
│   │                             #   - Candidate CRUD with pagination & search
│   │                             #   - Job CRUD with applicant tracking
│   │                             #   - Application management
│   │                             #   - Resume parsing, analysis & ranking
│   │                             #   - Document verification endpoints
│   │                             #   - Roadmap & interview question generation
│   │                             #   - MongoDB Atlas + local MockDB fallback
│   │
│   ├── intelligence.py           # ML/NLP engine (850+ lines)
│   │                             #   - Text cleaning & preprocessing
│   │                             #   - TF-IDF vectorization & model training
│   │                             #   - Resume scoring & JD matching
│   │                             #   - Skill, education, experience extraction
│   │                             #   - Aptitude & personality analysis
│   │                             #   - Multimodal interview assessment
│   │                             #   - Interview question generation
│   │
│   ├── document_verifier.py      # Document authentication engine (1200+ lines)
│   │                             #   - Neural credential classification
│   │                             #   - Authority registry & verification
│   │                             #   - PII redaction & privacy masking
│   │                             #   - OCR text extraction
│   │                             #   - Gemini LLM deep verification
│   │
│   ├── roadmap_generator.py      # Skill gap roadmap engine (700+ lines)
│   │                             #   - 50+ technology knowledge base
│   │                             #   - Dynamic learning path generation
│   │                             #   - Practice activities & projects
│   │                             #   - Assessment & resource curation
│   │
│   ├── models.py                 # SQLAlchemy ORM models (legacy)
│   ├── push_to_atlas.py          # MongoDB Atlas sync utility
│   ├── requirements.txt          # Python dependencies
│   ├── seed_resumes.csv          # Bundled demo dataset (168 resumes, 6 categories)
│   ├── mock_db_data.json         # Persistent local database
│   ├── models/
│   │   ├── category_model.pkl    # Trained classification model
│   │   ├── tfidf_vectorizer.pkl  # Fitted TF-IDF vectorizer
│   │   └── label_encoder.pkl     # Category label encoder
│   └── instance/
│       ├── mock_db_store.json    # Legacy local data store
│       └── recruitment.db        # SQLite database (legacy)
│
├── frontend/
│   ├── index.html                # Landing page
│   ├── login.html                # User login
│   ├── signup.html               # User registration
│   ├── candidate-dashboard.html  # Candidate home dashboard
│   ├── recruiter-dashboard.html  # Recruiter home dashboard
│   ├── resume-checker.html       # AI resume analysis tool
│   ├── job-search.html           # Job listing & search (candidates)
│   ├── my-applications.html      # Application tracking (candidates)
│   ├── my-profile.html           # Candidate profile editor
│   ├── roadmap.html              # Personalized learning roadmap
│   ├── manage-jobs.html          # Job CRUD (recruiters)
│   ├── manage-candidates.html    # Candidate management (recruiters)
│   ├── interview-questions.html  # AI interview question bank
│   ├── document-authenticator.html # Document verification tool
│   ├── analytics.html            # Recruitment analytics dashboard
│   ├── settings.html             # Account settings
│   ├── landing.html              # Marketing landing page
│   ├── explore.html              # Platform exploration page
│   ├── tour.html                 # Interactive platform tour
│   ├── learn-more.html           # Feature details page
│   ├── get-started.html          # Onboarding guide
│   ├── style.css                 # Design system (4500+ lines)
│   └── script.js                 # Client-side logic (680+ lines)
│
├── resume_data.csv               # Full Kaggle resume dataset (217K+ rows)
├── resume_data_exploration.ipynb # Data exploration Jupyter notebook
├── resume_data_modeling.ipynb    # ML modeling Jupyter notebook
└── README.md                     # This file
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **pip** (Python package manager)
- Internet connection (for MongoDB Atlas; local fallback works offline)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-username/Resume-minor.git
cd Resume-minor

# 2. (Optional) Create a virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# 3. Install dependencies
cd backend
pip install -r requirements.txt

# 4. (Optional) Install enhanced NLP packages
pip install sentence-transformers    # Semantic similarity
pip install spacy                    # NER-based extraction
pip install xgboost                  # Gradient boosting
pip install easyocr                  # OCR for scanned docs
```

### Running the Application

```bash
cd backend
python app.py
```

Open **http://127.0.0.1:5000** in your browser — Flask serves the frontend directly, no separate dev server needed.

> **First run**: If no trained model exists, the backend auto-trains on the bundled `seed_resumes.csv` (168 synthetic resumes across 6 categories) so you get a working demo immediately.

### Default Accounts

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `admin123` |
| Recruiter | `recruiter` | `recruiter123` |
| Candidate | `candidate` | `candidate123` |

---

## 📖 Usage Guide

### For Candidates

1. **Sign Up** → Create an account with the "Candidate" role
2. **Complete Profile** → Fill in skills, experience, education, and upload your resume
3. **Resume Checker** → Upload your resume to get AI-powered analysis with skill breakdown, category prediction, and score
4. **Job Search** → Browse open positions and apply with one click
5. **My Applications** → Track the status of all your applications
6. **Learning Roadmap** → Get personalized skill-gap learning paths after analyzing your resume against a JD

### For Recruiters

1. **Sign Up / Login** → Create an account with the "Recruiter" role
2. **Post Jobs** → Create job listings with descriptions, required skills, and salary ranges
3. **Manage Candidates** → View, search, filter, and manage all candidates
4. **Rank & Match** → Paste a JD and upload multiple resumes to rank candidates by AI score
5. **Interview Prep** → Generate tailored interview questions based on JD and candidate profile
6. **Document Verification** → Upload certificates/credentials for AI authenticity verification
7. **Analytics** → View recruitment pipeline metrics and insights

---

## 📡 API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/register` | Register a new user |
| `POST` | `/api/login` | Login with username/email and password |
| `POST` | `/api/logout` | End the current session |

### Resume Intelligence

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/status` | Model health check + available categories |
| `POST` | `/api/parse-file` | Upload PDF/DOCX/TXT → extracted text |
| `POST` | `/api/analyze` | Score a single resume (optionally vs. a JD) |
| `POST` | `/api/rank` | Score + rank multiple resumes against one JD |
| `POST` | `/api/match` | Enhanced candidate-job matching |

### Candidate Management

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/candidates` | List candidates (paginated, searchable) |
| `POST` | `/api/candidates` | Create a new candidate |
| `GET` | `/api/candidates/<id>` | Get candidate details with AI enrichment |
| `PUT` | `/api/candidates/<id>` | Update candidate profile |
| `DELETE` | `/api/candidates/<id>` | Delete a candidate |

### Job Management

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/jobs` | List all jobs (filterable by status) |
| `POST` | `/api/jobs` | Create a new job posting |
| `GET` | `/api/jobs/<id>` | Get job details |
| `PUT` | `/api/jobs/<id>` | Update a job posting |
| `DELETE` | `/api/jobs/<id>` | Delete a job posting |
| `GET` | `/api/jobs/<id>/applicants` | List applicants for a job |

### Applications

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/applications` | List applications (filterable) |
| `POST` | `/api/applications` | Submit an application |
| `PUT` | `/api/applications/<id>` | Update application status |

### Document Verification

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/verify-document` | Verify document authenticity |

### AI Tools

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/roadmap` | Generate skill-gap learning roadmap |
| `POST` | `/api/interview-questions` | Generate interview questions |
| `POST` | `/api/aptitude` | Run aptitude analysis |
| `POST` | `/api/personality` | Run personality insights |

### Example: Analyze a Resume

```bash
curl -X POST http://127.0.0.1:5000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "resume_text": "Experienced Python developer with 5 years in machine learning, Django, and AWS...",
    "jd_text": "Looking for a senior Python developer with ML experience and cloud deployment skills."
  }'
```

**Response:**
```json
{
  "predicted_category": "Data Science",
  "category_confidence": 0.847,
  "final_score": 78.3,
  "jd_similarity": 0.652,
  "skill_overlap": 0.75,
  "resume_skills": ["python", "machine learning", "django", "aws"],
  "matched_skills": ["python", "machine learning", "aws"],
  "missing_skills": ["docker", "kubernetes"],
  "keywords": [{"term": "python", "weight": 0.412}, ...],
  "education": {"degree": "B.Tech", "institution": "..."},
  "experience": {"years": 5, "experience_level": "Senior (5+ yrs)"},
  "certifications": ["AWS Certified Solutions Architect"],
  "aptitude": {"overall_aptitude_score": 82.5, "rating": "Proficient"},
  "personality": {"primary_work_style": "Collaborative Technical Innovator"}
}
```

---

## 🤖 Machine Learning Pipeline

### Model Training Process

```
Raw Resume CSV ──► Text Cleaning ──► TF-IDF Vectorization ──► Model Training ──► Best Model Selection
                     │                    │                        │
                     ▼                    ▼                        ▼
               - Lowercase          - 5000 features          - LogisticRegression
               - Remove URLs        - Unigrams + Bigrams     - LinearSVC
               - Remove emails      - Sublinear TF           - RandomForest
               - Remove specials    - Stopword removal       - XGBoost (optional)
               - Tokenize                                         │
                                                                  ▼
                                                            Auto-selects best
                                                            by weighted F1 score
```

### Scoring Pipeline (per resume)

```
Resume Text ──► Clean ──► TF-IDF Transform ──► Category Prediction (+ confidence)
     │                         │                         │
     ├──► Skill Extraction     ├──► JD Cosine Similarity │
     ├──► Education Parsing    │                         │
     ├──► Experience Parsing   │                         │
     ├──► Cert Detection       │                         │
     ├──► Aptitude Analysis    │                         │
     └──► Personality Profile  │                         │
                               ▼                         ▼
                    Composite Score = 0.5 × JD_Similarity
                                   + 0.3 × Skill_Overlap
                                   + 0.2 × Category_Confidence
```

### Training on Custom Dataset

```python
# From the backend/ directory
import intelligence as intel

# Auto-detects text and category columns
df = intel.load_dataset("/path/to/Resume.csv")

# Trains, compares models, saves the best one
intel.train_category_model(df)
# Output:
# LogisticRegression   accuracy=0.912 f1_weighted=0.908
# LinearSVC            accuracy=0.925 f1_weighted=0.921
# RandomForest         accuracy=0.897 f1_weighted=0.890
# [best] LinearSVC (f1=0.921)
```

Restart `app.py` afterward to load the newly trained model.

---

## 🗄 Database Design

### Collections (MongoDB)

```
users                    candidates               jobs
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ _id              │     │ _id              │     │ _id              │
│ username (unique)│     │ user_id (FK)     │     │ title            │
│ email (unique)   │     │ first_name       │     │ description      │
│ password_hash    │     │ last_name        │     │ required_skills  │
│ full_name        │     │ email            │     │ experience_req   │
│ role             │     │ phone            │     │ education_req    │
│ organization     │     │ skills[]         │     │ location         │
│ designation      │     │ resume_text      │     │ employment_type  │
│ created_at       │     │ education        │     │ salary_min/max   │
│ is_active        │     │ experience_years │     │ status           │
└──────────────────┘     │ current_status   │     │ created_by (FK)  │
                         │ created_at       │     │ created_at       │
                         └──────────────────┘     └──────────────────┘

applications             document_verifications
┌──────────────────┐     ┌──────────────────────┐
│ _id              │     │ _id                  │
│ candidate_id(FK) │     │ candidate_id (FK)    │
│ job_id (FK)      │     │ filename             │
│ applied_at       │     │ verdict (REAL/FORGED)│
│ status           │     │ confidence           │
│ match_score      │     │ predicted_category   │
│ resume_score     │     │ issuer               │
│ jd_similarity    │     │ credential_id        │
│ skill_overlap    │     │ verified_at          │
│ notes            │     └──────────────────────┘
└──────────────────┘
```

### Dual Database Strategy

The platform uses a **resilient dual-database** architecture:

1. **MongoDB Atlas (Primary)** — Cloud-hosted, auto-synced on startup
2. **Local JSON MockDB (Fallback)** — Automatically activates when Atlas is unreachable, providing full CRUD functionality with persistent JSON storage
3. **SQLite (Legacy)** — Records from the legacy SQLite database are auto-migrated to MongoDB on sync

---

## 🖥 Frontend Pages

| Page | File | Role | Description |
|---|---|---|---|
| Home | `index.html` | Public | Landing page with hero section |
| Login | `login.html` | Public | User authentication |
| Sign Up | `signup.html` | Public | User registration with role selection |
| Candidate Dashboard | `candidate-dashboard.html` | Candidate | Personal overview hub |
| My Profile | `my-profile.html` | Candidate | Edit profile, skills, and resume |
| Resume Checker | `resume-checker.html` | Candidate | AI resume analysis tool |
| Job Search | `job-search.html` | Candidate | Browse and apply to jobs |
| My Applications | `my-applications.html` | Candidate | Track application status |
| Learning Roadmap | `roadmap.html` | Candidate | Skill-gap learning paths |
| Recruiter Dashboard | `recruiter-dashboard.html` | Recruiter | Recruitment overview |
| Manage Jobs | `manage-jobs.html` | Recruiter | Create and manage job postings |
| Manage Candidates | `manage-candidates.html` | Recruiter | Candidate search and management |
| Interview Questions | `interview-questions.html` | Recruiter | AI-generated question bank |
| Document Authenticator | `document-authenticator.html` | Recruiter | Credential verification tool |
| Analytics | `analytics.html` | Recruiter | Hiring pipeline analytics |
| Settings | `settings.html` | All | Account settings |

---

## 📊 Scoring Formula

### With Job Description
```
final_score = (0.5 × jd_similarity + 0.3 × skill_overlap + 0.2 × category_confidence) × 100
```

| Component | Weight | Range | Description |
|---|---|---|---|
| `jd_similarity` | 50% | 0.0 – 1.0 | TF-IDF cosine similarity between resume and JD |
| `skill_overlap` | 30% | 0.0 – 1.0 | Fraction of JD skills found in resume |
| `category_confidence` | 20% | 0.0 – 1.0 | ML model's confidence in category prediction |

### Without Job Description
```
final_score = (0.6 × skill_richness + 0.4 × category_confidence) × 100
```

Weights are configurable in `intelligence.py → score_resume()`.

---

## 🔄 Upgrade Path

The codebase is modular so each component can be upgraded independently:

| # | Upgrade | Effort | Impact |
|---|---|---|---|
| 1 | **spaCy NER** → Replace regex skill dictionary | Medium | Better skill extraction for non-standard phrasing |
| 2 | **Sentence Transformers** → Replace TF-IDF similarity | Low | Already supported; captures semantic meaning |
| 3 | **XGBoost** → Add to model candidates | Low | Already supported; auto-selected if best |
| 4 | **OCR (Tesseract/EasyOCR)** → Scanned PDF support | Low | Already supported with optional deps |
| 5 | **FastAPI** → Replace Flask | Medium | Routes map 1:1; mostly syntax changes |
| 6 | **React** → Replace vanilla JS frontend | High | CSS design system can be reused |
| 7 | **Whisper** → Speech-to-text for interviews | High | New subsystem for audio analysis |
| 8 | **OpenCV/MediaPipe** → Video interview analysis | High | New subsystem for visual cues |

---

## ⚠️ Known Limitations

- **Heuristic scoring** — `final_score` is a weighted blend, not a calibrated probability. Use it as a ranking signal, not absolute truth.
- **Dictionary-based skills** — Exact keyword match may miss alternate phrasings (e.g., "built REST services" won't match "rest api"). Upgrade to spaCy NER for better recall.
- **OCR dependency** — Scanned/image-only PDFs require optional OCR packages (`pytesseract` or `easyocr`) to be installed.
- **Seed dataset** — The bundled demo dataset is small (168 resumes); train on the full Kaggle dataset for production accuracy.
- **No JWT/Token Auth** — Current auth uses session-based storage; for production, add JWT token authentication.
- **MongoDB credentials** — Default Atlas credentials are embedded; use environment variables (`MONGODB_URI`) in production.

---

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/your-feature`
3. **Commit** your changes: `git commit -m "Add your feature"`
4. **Push** to the branch: `git push origin feature/your-feature`
5. **Open** a Pull Request

---

## 📄 License

This project is developed as a Minor Project for academic purposes. All rights reserved.

---

<p align="center">
  <b>Built with ❤️ using Python, Flask, scikit-learn, and MongoDB</b><br>
  <i>AI-Powered Smart Recruitment & Resume Intelligence Platform</i>
</p>

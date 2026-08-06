# AI-Powered Recruitment Platform — Working Prototype

A functional prototype for the problem statement: resume parsing, skill
extraction, JD matching, and a ranked recruiter dashboard.

**Tested and verified working end-to-end** — form fill → resume parse →
ranking → detail drawer — via both manual and automated (Playwright)
testing before delivery.

## What's actually running here vs. the target stack

Your problem statement lists BERT/Transformers, spaCy, XGBoost, and
FastAPI. This build environment has no internet access to install those,
so this prototype uses the closest available equivalents so it *runs
today*:

| Target stack        | This prototype uses      | Why                                  |
|----------------------|---------------------------|---------------------------------------|
| Transformers (BERT)  | TF-IDF + cosine similarity | No internet to pull model weights    |
| spaCy NER            | Regex skill dictionary     | No internet to `pip install spacy`   |
| XGBoost               | scikit-learn (LogReg/SVM/RF, best auto-selected) | Same reason |
| FastAPI               | Flask                      | FastAPI wasn't installed; Flask was  |
| React                 | Vanilla HTML/CSS/JS        | No npm/build tooling in this sandbox |

Everything is written so each swap is a contained change (see
**Upgrade path** below) — the API contract (`/api/analyze`, `/api/rank`)
won't need to change when you swap the internals.

## Architecture

```
recruit_platform/
├── backend/
│   ├── app.py              # Flask API + serves the frontend
│   ├── intelligence.py     # cleaning, classification, scoring logic
│   ├── seed_resumes.csv    # bundled demo data (6 categories) so the
│   │                       # app works out-of-the-box before you plug
│   │                       # in the real Kaggle dataset
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── style.css            # "case file" design system
    └── script.js            # vanilla JS, talks to the Flask API
```

On first run, if no trained model exists yet, the backend auto-trains on
the bundled `seed_resumes.csv` (168 synthetic resumes across 6
categories) so you get a working demo immediately. Swap in the real
Kaggle dataset any time — see below.

## Setup

```bash
cd backend
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000** — backend serves the frontend directly,
no separate dev server needed.

## Using it

1. Paste a job description in the left panel.
2. Add candidates — drag/drop `.pdf` / `.docx` / `.txt` resume files,
   or paste text manually.
3. Click **Review candidates** — each résumé is scored and the list is
   ranked by final match score.
4. Click any candidate card to open the detail drawer: full score
   breakdown, matched/missing skills, and top keywords.

## Training on your real dataset

Replace the bundled seed data with the actual Kaggle dataset:

```python
# from the backend/ directory
import intelligence as intel
df = intel.load_dataset("/path/to/Resume.csv")   # auto-detects text/category columns
intel.train_category_model(df)                    # saves to backend/models/
```

Restart `app.py` afterward to load the newly trained model.

## Scoring formula

```
final_score = (0.5 * jd_similarity + 0.3 * skill_overlap + 0.2 * category_confidence) * 100
```

(or, with no JD: `0.6 * skill_richness + 0.4 * category_confidence`).
Weights are adjustable in `intelligence.score_resume()`.

## API reference

- `GET /api/status` — model health + available categories
- `POST /api/parse-file` — multipart file upload → `{ text }`
- `POST /api/analyze` — `{ resume_text, jd_text? }` → full score report
- `POST /api/rank` — `{ jd_text, candidates: [{name, resume_text}] }` →
  ranked list with per-candidate breakdown

## Design notes

The UI deliberately avoids the "AI-generated app" look (gradient hero,
glassmorphism, cyan/purple palette). Instead:
- **Palette**: warm paper background, ink-navy text, one restrained
  accent (forest green / amber / clay) used only on the score badge and
  skill chips.
- **Type**: Fraunces (serif, for names/headings) + Inter (body) + IBM
  Plex Mono (scores, data, category tags) — deliberately mixed to feel
  like an editorial/dossier tool, not a SaaS template.
- **Signature element**: the circular dashed "stamp" score badge, a
  nod to a physical reviewed-and-stamped resume folder — used once per
  card, not repeated everywhere, to keep it a deliberate accent rather
  than decoration.

## Known limitations (be upfront about these in your report/demo)

- `final_score` is a heuristic weighted blend, not a calibrated
  probability — treat it as a ranking/triage signal, not ground truth.
- Skill extraction is dictionary-based (exact keyword match), so it
  will miss skills phrased unusually (e.g. "built REST services" won't
  match "rest api" unless the resume also says "REST API"). Swapping in
  spaCy NER (see below) fixes this.
- No OCR yet — scanned/image-only PDFs will fail to parse with a clear
  error message rather than silently returning empty text.
- The bundled seed dataset is small and synthetic; category-prediction
  accuracy on the demo is artificially high. Real accuracy numbers will
  come once you train on the actual Kaggle dataset.

## Upgrade path to the full target stack

Roughly in order of effort:

1. **spaCy NER instead of the skill dictionary** — train a custom NER
   model on the "Resume Entities for NER" Kaggle dataset so skills,
   education, and experience are extracted as structured fields, not
   just keyword lookups. Swap `extract_skills()` in `intelligence.py`.
2. **Sentence-transformers instead of TF-IDF** for `jd_similarity` —
   captures semantic meaning, not just literal keyword overlap
   (`pip install sentence-transformers`, swap the `cosine_similarity`
   call in `score_resume()`).
3. **XGBoost** — add it to the `candidates` dict in
   `train_category_model()` alongside the existing scikit-learn models;
   the auto-comparison logic already picks whichever performs best, so
   this is a small, low-risk addition.
4. **OCR (Tesseract)** for scanned resumes — `pytesseract` is already
   installed in the environment this was built in; wire it into
   `/api/parse-file` as a fallback when `pdfplumber` returns empty text.
5. **FastAPI** — the Flask routes here map almost 1:1 to FastAPI path
   operations; this is mostly a syntax port, not a redesign.
6. **React** — port `script.js`'s state/render logic into components;
   the CSS design system (`style.css` custom properties) can be reused
   directly or converted to Tailwind config tokens.
7. **Aptitude analysis / AI interview support** (from your problem
   statement) — these are new subsystems, not upgrades to this one.
   Suggest scoping them as separate services that write into the same
   candidate record, rather than extending `intelligence.py` further.
8. **Speech (Whisper) / video (OpenCV, MediaPipe)** — only pursue these
   if your timeline allows; they're marked optional in your own
   problem statement, and are the highest-effort, highest-risk parts
   to get working reliably for a project deadline.

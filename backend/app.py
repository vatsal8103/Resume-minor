"""
Flask backend for the AI Recruitment Platform prototype.

Endpoints:
  GET  /                      -> serves the frontend
  POST /api/parse-file        -> extract text from an uploaded pdf/docx/txt resume
  POST /api/analyze           -> score ONE resume (optionally vs. a JD)
  POST /api/rank              -> score + rank MULTIPLE resumes against one JD
  GET  /api/status            -> whether a trained category model is loaded
  GET/POST /api/candidates    -> list candidates or create new candidate
  GET/PUT/DELETE /api/candidates/<id> -> get/update/delete candidate
  GET/POST /api/jobs          -> list jobs or create new job
  GET/PUT/DELETE /api/jobs/<id> -> get/update/delete job
  GET /api/jobs/<id>/applicants -> get applicants for a job
  POST /api/match             -> match candidates to a job (enhanced ranking)

Run:
  pip install -r requirements.txt
  python app.py
  -> open http://127.0.0.1:5000
"""

import io
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime

try:
    import intelligence as intel
except ImportError:
    import backend.intelligence as intel

BASE_DIR = Path(__file__).parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = Flask(__name__, static_folder=None)
# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///recruitment.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Import db and models from models
from models import db, User, Skill, Job, Candidate, Application, Interview, AptitudeTest
# Initialize db with the app
db.init_app(app)

# Create tables
def create_tables():
    db.create_all()
    # Create a default admin user if none exists
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@example.com', full_name='Administrator', role='admin')
        admin.set_password('admin123')  # Change in production
        db.session.add(admin)
        db.session.commit()

# Call create_tables when the app starts
with app.app_context():
    create_tables()

# ---------------------------------------------------------------------------
# Bootstrap: train on the bundled seed dataset if no model has been saved yet.
# Swap in the real Kaggle dataset any time by calling:
#   POST /api/train  (not exposed by default; see train_on_seed.py / README)
# ---------------------------------------------------------------------------
if not intel.models_exist():
    seed_path = BASE_DIR / "seed_resumes.csv"
    if seed_path.exists():
        print("[bootstrap] No trained model found — training on bundled seed data...")
        df = intel.load_dataset(str(seed_path))
        intel.train_category_model(df)
    else:
        print("[bootstrap] WARNING: no model and no seed_resumes.csv found.")

MODEL, TFIDF, LE = intel.load_models()


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/about")
def about():
    return send_from_directory(FRONTEND_DIR, "about.html")

@app.route("/dashboard")
def dashboard():
    return send_from_directory(FRONTEND_DIR, "dashboard.html")

@app.route("/settings")
def settings():
    return send_from_directory(FRONTEND_DIR, "settings.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@app.route("/api/status")
def status():
    return jsonify({
        "model_loaded": True,
        "categories": list(LE.classes_),
    })


@app.route("/api/parse-file", methods=["POST"])
def parse_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    filename = f.filename.lower()
    data = f.read()

    try:
        if filename.endswith(".pdf"):
            import pdfplumber
            text_parts = []
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for page in pdf.pages:
                    text_parts.append(page.extract_text() or "")
            text = "\n".join(text_parts)

        elif filename.endswith(".docx"):
            import docx
            document = docx.Document(io.BytesIO(data))
            text = "\n".join(p.text for p in document.paragraphs)

        elif filename.endswith(".txt"):
            text = data.decode("utf-8", errors="ignore")

        else:
            return jsonify({"error": "Unsupported file type. Use .pdf, .docx, or .txt"}), 400

    except Exception as e:
        return jsonify({"error": f"Failed to parse file: {e}"}), 500

    # If no text was extracted, try OCR as a fallback for scanned documents
    if not text.strip() and OCR_AVAILABLE:
        try:
            from backend.intelligence import extract_text_with_ocr
            ocr_text = extract_text_with_ocr(data, filename)
            if ocr_text.strip():
                text = ocr_text
        except Exception as e:
            logging.warning(f"OCR fallback failed: {e}")

    if not text.strip():
        return jsonify({
            "error": "No extractable text found. This may be a scanned/image resume "
                     "requiring OCR (see README: Tesseract upgrade path)."
        }), 422

    return jsonify({"text": text, "filename": f.filename})


@app.route("/api/analyze", methods=["POST"])
def analyze():
    payload = request.get_json(force=True) or {}
    resume_text = payload.get("resume_text", "")
    jd_text = payload.get("jd_text", "")

    if not resume_text.strip():
        return jsonify({"error": "resume_text is required"}), 400

    result = intel.score_resume(resume_text, jd_text, MODEL, TFIDF, LE)
    return jsonify(result)


@app.route("/api/rank", methods=["POST"])
def rank():
    payload = request.get_json(force=True) or {}
    jd_text = payload.get("jd_text", "")
    candidates = payload.get("candidates", [])

    if not jd_text.strip():
        return jsonify({"error": "jd_text is required for ranking"}), 400
    if not candidates:
        return jsonify({"error": "candidates list is required"}), 400

    ranked = []
    for c in candidates:
        name = c.get("name", "Unnamed")
        resume_text = c.get("resume_text", "")
        if not resume_text.strip():
            continue
        result = intel.score_resume(resume_text, jd_text, MODEL, TFIDF, LE)
        result["name"] = name
        ranked.append(result)

    ranked.sort(key=lambda r: r["final_score"], reverse=True)
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i

    return jsonify({"jd_text": jd_text, "candidates": ranked})


# Candidate Management APIs
@app.route("/api/candidates", methods=["GET", "POST"])
def candidates():
    if request.method == "GET":
        # Get query parameters for filtering
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search', '')
        status = request.args.get('status', '')

        query = Candidate.query

        if search:
            query = query.filter(
                (Candidate.first_name.contains(search)) |
                (Candidate.last_name.contains(search)) |
                (Candidate.email.contains(search))
            )
        if status:
            query = query.filter(Candidate.current_status == status)

        candidates = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'candidates': [{
                'id': c.id,
                'first_name': c.first_name,
                'last_name': c.last_name,
                'email': c.email,
                'phone': c.phone,
                'current_status': c.current_status,
                'source': c.source,
                'created_at': c.created_at.isoformat() if c.created_at else None,
                'full_name': c.full_name
            } for c in candidates.items],
            'total': candidates.total,
            'pages': candidates.pages,
            'current_page': page
        })

    elif request.method == "POST":
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        candidate = Candidate(
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            email=data.get('email'),
            phone=data.get('phone'),
            resume_text=data.get('resume_text', ''),
            parsed_data=data.get('parsed_data'),
            current_status=data.get('current_status', 'new'),
            source=data.get('source', 'manual'),
            notes=data.get('notes')
        )

        db.session.add(candidate)
        db.session.commit()

        return jsonify({
            'id': candidate.id,
            'message': 'Candidate created successfully'
        }), 201


@app.route("/api/candidates/<int:id>", methods=["GET", "PUT", "DELETE"])
def candidate_detail(id):
    candidate = Candidate.query.get_or_404(id)

    if request.method == "GET":
        # Get candidate with skills and applications
        skills = [{'id': s.id, 'name': s.name} for s in candidate.skills]
        applications = [{
            'id': a.id,
            'job_id': a.job_id,
            'job_title': a.job.title if a.job else None,
            'match_score': a.match_score,
            'status': a.status,
            'applied_at': a.applied_at.isoformat() if a.applied_at else None
        } for a in candidate.applications]

        return jsonify({
            'id': candidate.id,
            'first_name': candidate.first_name,
            'last_name': candidate.last_name,
            'email': candidate.email,
            'phone': candidate.phone,
            'resume_text': candidate.resume_text,
            'parsed_data': candidate.parsed_data,
            'current_status': candidate.current_status,
            'source': candidate.source,
            'notes': candidate.notes,
            'skills': skills,
            'applications': applications,
            'created_at': candidate.created_at.isoformat() if candidate.created_at else None,
            'updated_at': candidate.updated_at.isoformat() if candidate.updated_at else None,
            'full_name': candidate.full_name
        })

    elif request.method == "PUT":
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        candidate.first_name = data.get('first_name', candidate.first_name)
        candidate.last_name = data.get('last_name', candidate.last_name)
        candidate.email = data.get('email', candidate.email)
        candidate.phone = data.get('phone', candidate.phone)
        candidate.resume_text = data.get('resume_text', candidate.resume_text)
        candidate.parsed_data = data.get('parsed_data', candidate.parsed_data)
        candidate.current_status = data.get('current_status', candidate.current_status)
        candidate.source = data.get('source', candidate.source)
        candidate.notes = data.get('notes', candidate.notes)

        candidate.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'id': candidate.id,
            'message': 'Candidate updated successfully'
        })

    elif request.method == "DELETE":
        db.session.delete(candidate)
        db.session.commit()

        return jsonify({
            'message': 'Candidate deleted successfully'
        })


# Job Management APIs
@app.route("/api/jobs", methods=["GET", "POST"])
def jobs():
    if request.method == "GET":
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search', '')
        status = request.args.get('status', '')

        query = Job.query

        if search:
            query = query.filter(Job.title.contains(search))
        if status:
            query = query.filter(Job.status == status)

        jobs = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'jobs': [{
                'id': j.id,
                'title': j.title,
                'description': j.description,
                'location': j.location,
                'employment_type': j.employment_type,
                'status': j.status,
                'created_at': j.created_at.isoformat() if j.created_at else None,
                'applicant_count': j.applications.count()
            } for j in jobs.items],
            'total': jobs.total,
            'pages': jobs.pages,
            'current_page': page
        })

    elif request.method == "POST":
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        job = Job(
            title=data.get('title'),
            description=data.get('description'),
            required_skills=data.get('required_skills'),
            experience_required=data.get('experience_required'),
            education_required=data.get('education_required'),
            location=data.get('location'),
            employment_type=data.get('employment_type'),
            salary_min=data.get('salary_min'),
            salary_max=data.get('salary_max'),
            requirements=data.get('requirements'),
            status=data.get('status', 'open'),
            created_by=data.get('created_by', 1)  # Default to admin user
        )

        db.session.add(job)
        db.session.commit()

        return jsonify({
            'id': job.id,
            'message': 'Job created successfully'
        }), 201


@app.route("/api/jobs/<int:id>", methods=["GET", "PUT", "DELETE"])
def job_detail(id):
    job = Job.query.get_or_404(id)

    if request.method == "GET":
        # Get job with applicants
        applicants = [{
            'id': a.id,
            'candidate_id': a.candidate_id,
            'candidate_name': a.candidate.full_name if a.candidate else None,
            'match_score': a.match_score,
            'status': a.status,
            'applied_at': a.applied_at.isoformat() if a.applied_at else None
        } for a in job.applications]

        return jsonify({
            'id': job.id,
            'title': job.title,
            'description': job.description,
            'required_skills': job.required_skills,
            'experience_required': job.experience_required,
            'education_required': job.education_required,
            'location': job.location,
            'employment_type': job.employment_type,
            'salary_min': job.salary_min,
            'salary_max': job.salary_max,
            'requirements': job.requirements,
            'status': job.status,
            'created_by': job.created_by,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'updated_at': job.updated_at.isoformat() if job.updated_at else None,
            'applicants': applicants
        })

    elif request.method == "PUT":
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        job.title = data.get('title', job.title)
        job.description = data.get('description', job.description)
        job.required_skills = data.get('required_skills', job.required_skills)
        job.experience_required = data.get('experience_required', job.experience_required)
        job.education_required = data.get('education_required', job.education_required)
        job.location = data.get('location', job.location)
        job.employment_type = data.get('employment_type', job.employment_type)
        job.salary_min = data.get('salary_min', job.salary_min)
        job.salary_max = data.get('salary_max', job.salary_max)
        job.requirements = data.get('requirements', job.requirements)
        job.status = data.get('status', job.status)
        job.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'id': job.id,
            'message': 'Job updated successfully'
        })

    elif request.method == "DELETE":
        db.session.delete(job)
        db.session.commit()

        return jsonify({
            'message': 'Job deleted successfully'
        })


@app.route("/api/jobs/<int:id>/applicants", methods=["GET"])
def job_applicants(id):
    job = Job.query.get_or_404(id)
    applicants = [{
        'id': a.id,
        'candidate_id': a.candidate_id,
        'candidate_name': a.candidate.full_name if a.candidate else None,
        'match_score': a.match_score,
        'resume_score': a.resume_score,
        'jd_similarity': a.jd_similarity,
        'skill_overlap': a.skill_overlap,
        'role_confidence': a.role_confidence,
        'status': a.status,
        'applied_at': a.applied_at.isoformat() if a.applied_at else None,
        'notes': a.notes
    } for a in job.applications]

    return jsonify({
        'job_id': job.id,
        'job_title': job.title,
        'applicants': applicants,
        'total': len(applicants)
    })


# Enhanced Matching API that saves to database
@app.route("/api/match", methods=["POST"])
def match():
    payload = request.get_json(force=True) or {}
    jd_text = payload.get("jd_text", "")
    candidate_ids = payload.get("candidate_ids", [])
    job_id = payload.get("job_id")

    if not jd_text.strip():
        return jsonify({"error": "jd_text is required for matching"}), 400
    if not candidate_ids:
        return jsonify({"error": "candidate_ids list is required"}), 400
    if not job_id:
        return jsonify({"error": "job_id is required"}), 400

    job = Job.query.get_or_404(job_id)

    # Get candidates
    candidates = Candidate.query.filter(Candidate.id.in_(candidate_ids)).all()
    if not candidates:
        return jsonify({"error": "No valid candidates found"}), 404

    ranked = []
    for candidate in candidates:
        resume_text = candidate.resume_text
        if not resume_text.strip():
            continue
        result = intel.score_resume(resume_text, jd_text, MODEL, TFIDF, LE)
        result["name"] = candidate.full_name
        result["candidate_id"] = candidate.id
        ranked.append(result)

    ranked.sort(key=lambda r: r["final_score"], reverse=True)
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i

        # Save or update application record
        application = Application.query.filter_by(
            candidate_id=r["candidate_id"],
            job_id=job_id
        ).first()

        if not application:
            application = Application(
                candidate_id=r["candidate_id"],
                job_id=job_id
            )
            db.session.add(application)

        application.match_score = r["final_score"]
        application.resume_score = r.get("final_score")  # Simplified
        application.jd_similarity = r.get("jd_similarity", 0) * 100 if r.get("jd_similarity") is not None else 0
        application.skill_overlap = r.get("skill_overlap", 0) * 100 if r.get("skill_overlap") is not None else 0
        application.role_confidence = r.get("category_confidence", 0) * 100 if r.get("category_confidence") is not None else 0
        application.updated_at = datetime.utcnow()

    db.session.commit()

    return jsonify({
        "jd_text": jd_text,
        "candidates": ranked,
        "job_id": job_id
    })


# Skill Gap Roadmap Generation API
@app.route("/api/roadmap", methods=["POST"])
def generate_roadmap():
    payload = request.get_json(force=True) or {}
    resume_text = payload.get("resume_text", "")
    jd_text = payload.get("jd_text", "")

    if not resume_text.strip():
        return jsonify({"error": "resume_text is required"}), 400

    # Get resume analysis to extract skills
    resume_result = intel.score_resume(resume_text, "", MODEL, TFIDF, LE)
    resume_skills = set(resume_result["resume_skills"])

    jd_skills = set()
    if jd_text.strip():
        jd_result = intel.score_resume(jd_text, "", MODEL, TFIDF, LE)
        jd_skills = set(jd_result["resume_skills"])

    missing_skills = jd_skills - resume_skills

    # Generate roadmap
    roadmap = intel.generate_skill_gap_roadmap(
        resume_skills,
        jd_skills,
        missing_skills,
        resume_result["predicted_category"]
    )

    return jsonify({
        "resume_skills": sorted(list(resume_skills)),
        "jd_skills": sorted(list(jd_skills)),
        "missing_skills": sorted(list(missing_skills)),
        "roadmap": roadmap
    })


# Interview Question Generation API
@app.route("/api/questions", methods=["POST"])
def generate_questions():
    payload = request.get_json(force=True) or {}
    resume_text = payload.get("resume_text", "")
    jd_text = payload.get("jd_text", "")

    if not resume_text.strip():
        return jsonify({"error": "resume_text is required"}), 400

    # Get resume analysis
    resume_result = intel.score_resume(resume_text, "", MODEL, TFIDF, LE)
    resume_skills = set(resume_result["resume_skills"])

    jd_skills = set()
    matched_skills = set()
    if jd_text.strip():
        jd_result = intel.score_resume(jd_text, "", MODEL, TFIDF, LE)
        jd_skills = set(jd_result["resume_skills"])
        matched_skills = resume_skills & jd_skills

    # Generate interview questions
    questions = intel.generate_interview_questions(
        jd_text,
        resume_skills,
        matched_skills,
        jd_skills - resume_skills,
        resume_result["predicted_category"]
    )

    return jsonify({
        "resume_skills": sorted(list(resume_skills)),
        "jd_skills": sorted(list(jd_skills)),
        "matched_skills": sorted(list(matched_skills)),
        "missing_skills": sorted(list(jd_skills - resume_skills)),
        "questions": questions
    })


# Model Evaluation API (for admin/testing)
@app.route("/api/evaluate", methods=["POST"])
def evaluate_model():
    payload = request.get_json(force=True) or {}
    test_predictions = payload.get("test_predictions", [])
    test_actuals = payload.get("test_actuals", [])

    if not test_predictions or not test_actuals:
        return jsonify({"error": "test_predictions and test_actuals are required"}), 400

    if len(test_predictions) != len(test_actuals):
        return jsonify({"error": "test_predictions and test_actuals must have the same length"}), 400

    evaluation = intel.evaluate_model_performance(test_predictions, test_actuals)
    return jsonify(evaluation)


# Matching Accuracy API (for admin/testing)
@app.route("/api/matching_accuracy", methods=["POST"])
def calculate_matching_accuracy():
    payload = request.get_json(force=True) or {}
    resume_texts = payload.get("resume_texts", [])
    jd_texts = payload.get("jd_texts", [])
    expected_matches = payload.get("expected_matches", [])

    if not resume_texts:
        return jsonify({"error": "resume_texts is required"}), 400

    if len(resume_texts) != len(jd_texts):
        return jsonify({"error": "resume_texts and jd_texts must have the same length"}), 400

    if expected_matches and len(expected_matches) != len(resume_texts):
        return jsonify({"error": "expected_matches must have the same length as resume_texts"}), 400

    accuracy = intel.calculate_matching_accuracy(resume_texts, jd_texts, expected_matches, MODEL, TFIDF, LE)
    return jsonify(accuracy)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
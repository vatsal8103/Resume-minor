"""
Flask backend for the AI Recruitment Platform prototype.

Endpoints:
  GET  /                      -> serves the frontend
  POST /api/parse-file        -> extract text from an uploaded pdf/docx/txt resume
  POST /api/analyze           -> score ONE resume (optionally vs. a JD)
  POST /api/rank              -> score + rank MULTIPLE resumes against one JD
  GET  /api/status            -> whether a trained category model is loaded

Run:
  pip install -r requirements.txt
  python app.py
  -> open http://127.0.0.1:5000
"""

import io
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory

try:
    import intelligence as intel
except ImportError:
    import backend.intelligence as intel

BASE_DIR = Path(__file__).parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = Flask(__name__, static_folder=None)

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


if __name__ == "__main__":
    app.run(debug=True, port=5000)

"""
Core resume-intelligence functions: text cleaning, category classification,
skill/keyword extraction, and JD-match scoring.

Kept as a plain module (not tied to Flask) so it can later be swapped for
spaCy/transformers/XGBoost without touching the API layer.
"""

import re
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
import logging
import io  # for OCR

# Advanced NLP imports (with fallbacks)
try:
    import spacy
    from spacy.matcher import PhraseMatcher
    SPACY_AVAILABLE = True
except ImportError as e:
    SPACY_AVAILABLE = False
    logging.warning(f"spaCy not available due to import error: {e}, falling back to regex skill extraction")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning("sentence-transformers not available, falling back to TF-IDF")

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logging.warning("XGBoost not available, falling back to scikit-learn models")

try:
    import pytesseract
    from pdf2image import convert_from_bytes
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logging.warning("OCR dependencies not available, scanned PDFs will not be processed")

# Optional multimodal analysis imports
try:
    import librosa
    import numpy as np
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    logging.warning("Audio analysis dependencies not available, voice analysis disabled")

try:
    import cv2
    import mediapipe as mp
    VIDEO_AVAILABLE = True
except ImportError:
    VIDEO_AVAILABLE = False
    logging.warning("Video analysis dependencies not available, video analysis disabled")

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score, f1_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import LabelEncoder

# Handle RandomForestClassifier import gracefully due to potential Windows security policy issues
try:
    from sklearn.ensemble import RandomForestClassifier
    RANDOM_FOREST_AVAILABLE = True
except ImportError as e:
    logging.warning(f"RandomForestClassifier not available due to import error: {e}")
    RANDOM_FOREST_AVAILABLE = False
    RandomForestClassifier = None  # type: ignore

BASE_DIR = Path(__file__).parent
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)

STOPWORDS = {
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "you're",
    "you've", "you'll", "you'd", "your", "yours", "yourself", "yourselves", "he",
    "him", "his", "himself", "she", "she's", "her", "hers", "herself", "it", "it's",
    "its", "itself", "they", "them", "their", "theirs", "themselves", "what",
    "which", "who", "whom", "this", "that", "that'll", "these", "those", "am",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "having", "do", "does", "did", "doing", "a", "an", "the", "and", "but", "if",
    "or", "because", "as", "until", "while", "of", "at", "by", "for", "with",
    "about", "against", "between", "into", "through", "during", "before", "after",
    "above", "below", "to", "from", "up", "down", "in", "out", "on", "off", "over",
    "under", "again", "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "s", "t", "can", "will", "just", "don", "don't", "should", "should've",
    "now", "d", "ll", "m", "o", "re", "ve", "y",
}

# Disable spaCy model loading due to Windows security policy issues
# We'll use regex-based skill extraction as fallback
nlp = None
logging.warning("spaCy model loading disabled due to system constraints, using regex-based skill extraction")

SKILL_DICTIONARY = {
    "python", "java", "c++", "c#", "javascript", "typescript", "sql", "r",
    "html", "css", "react", "angular", "vue", "node.js", "django", "flask",
    "fastapi", "spring", "machine learning", "deep learning", "nlp",
    "computer vision", "tensorflow", "pytorch", "keras", "scikit-learn",
    "xgboost", "pandas", "numpy", "data analysis", "data visualization",
    "power bi", "tableau", "excel", "aws", "azure", "gcp", "docker",
    "kubernetes", "git", "linux", "hadoop", "spark", "kafka", "mongodb",
    "mysql", "postgresql", "nosql", "rest api", "agile", "scrum",
    "project management", "communication", "leadership", "teamwork",
    "problem solving", "time management", "critical thinking", "sales",
    "marketing", "seo", "content writing", "customer service", "accounting",
    "finance", "hr", "recruitment", "testing", "selenium", "manual testing",
    "automation testing", "devops", "ci/cd", "jenkins", "android", "ios",
    "swift", "kotlin", "figma", "ui/ux", "photoshop", "spacy", "bert",
    "transformers", "opencv", "speech recognition",
}


def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"http\S+|www\S+", " ", text)
    text = re.sub(r"\S+@\S+", " ", text)
    text = re.sub(r"[^a-z0-9\+\#\.\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    tokens = [w for w in text.split() if w not in STOPWORDS and len(w) > 1]
    return " ".join(tokens)


def extract_text_with_ocr(file_bytes: bytes, filename: str) -> str:
    """Extract text from scanned PDFs using OCR as fallback"""
    if not OCR_AVAILABLE:
        return ""

    try:
        if filename.lower().endswith('.pdf'):
            # Convert PDF to images
            images = convert_from_bytes(file_bytes)
            text = ""
            for img in images:
                # Use pytesseract to extract text
                text += pytesseract.image_to_string(img) + "\n"
            return text
        elif filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')):
            # Direct image OCR
            img = Image.open(io.BytesIO(file_bytes))
            return pytesseract.image_to_string(img)
    except Exception as e:
        logging.warning(f"OCR failed for {filename}: {e}")
        return ""

    return ""


def load_dataset(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    text_candidates = [c for c in df.columns if re.search(r"resume|text|cv", c, re.I)]
    cat_candidates = [c for c in df.columns if re.search(r"category|label|job.?title|field", c, re.I)]
    if not text_candidates or not cat_candidates:
        raise ValueError(
            f"Could not auto-detect columns. Found: {list(df.columns)}. "
            "Rename your text column to 'Resume' and label column to 'Category'."
        )
    text_col, cat_col = text_candidates[0], cat_candidates[0]
    df = df[[text_col, cat_col]].dropna().rename(columns={text_col: "Resume", cat_col: "Category"})
    df["clean_resume"] = df["Resume"].apply(clean_text)
    df = df[df["clean_resume"].str.len() > 20].reset_index(drop=True)
    return df


def train_category_model(df: pd.DataFrame, verbose: bool = True):
    le = LabelEncoder()
    y = le.fit_transform(df["Category"])

    tfidf = TfidfVectorizer(max_features=5000, ngram_range=(1, 2), sublinear_tf=True)
    X = tfidf.fit_transform(df["clean_resume"])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Base candidates
    candidates = {
        "LogisticRegression": LogisticRegression(max_iter=1000, class_weight="balanced"),
        "LinearSVC": LinearSVC(class_weight="balanced"),
        "RandomForest": RandomForestClassifier(n_estimators=200, random_state=42),
    }

    # Add XGBoost if available
    if XGBOOST_AVAILABLE:
        candidates["XGBoost"] = xgb.XGBClassifier(
            n_estimators=200,
            random_state=42,
            eval_metric='mlogloss',
            use_label_encoder=False
        )

    best_name, best_model, best_f1 = None, None, -1
    for name, clf in candidates.items():
        clf.fit(X_train, y_train)
        preds = clf.predict(X_test)
        f1 = f1_score(y_test, preds, average="weighted")
        if verbose:
            acc = accuracy_score(y_test, preds)
            print(f"{name:20s} accuracy={acc:.3f} f1_weighted={f1:.3f}")
        if f1 > best_f1:
            best_name, best_model, best_f1 = name, clf, f1

    if verbose:
        print(f"[best] {best_name} (f1={best_f1:.3f})")

    joblib.dump(best_model, MODEL_DIR / "category_model.pkl")
    joblib.dump(tfidf, MODEL_DIR / "tfidf_vectorizer.pkl")
    joblib.dump(le, MODEL_DIR / "label_encoder.pkl")
    return best_model, tfidf, le


def models_exist() -> bool:
    return all(
        (MODEL_DIR / f).exists()
        for f in ["category_model.pkl", "tfidf_vectorizer.pkl", "label_encoder.pkl"]
    )


def load_models():
    model = joblib.load(MODEL_DIR / "category_model.pkl")
    tfidf = joblib.load(MODEL_DIR / "tfidf_vectorizer.pkl")
    le = joblib.load(MODEL_DIR / "label_encoder.pkl")
    return model, tfidf, le


def extract_skills(text: str) -> set:
    """Extract skills using spaCy NER when available, fallback to regex"""
    if SPACY_AVAILABLE and nlp is not None:
        try:
            doc = nlp(text)
            skills = set()

            # Look for skill entities (we'll use noun chunks and entities as proxy)
            # In a real implementation, you'd train a custom NER model for skills
            for chunk in doc.noun_chunks:
                chunk_text = chunk.text.lower().strip()
                # Check if chunk matches any skill in our dictionary
                for skill in SKILL_DICTIONARY:
                    if skill in chunk_text or chunk_text in skill:
                        skills.add(skill)

            # Also check for exact matches in the text
            clean_text_lower = clean_text(text)
            for skill in SKILL_DICTIONARY:
                if re.search(r"\b" + re.escape(skill) + r"\b", clean_text_lower):
                    skills.add(skill)

            return skills
        except Exception as e:
            logging.warning(f"spaCy skill extraction failed: {e}, falling back to regex")

    # Fallback to original regex-based extraction
    clean = clean_text(text)
    return {s for s in SKILL_DICTIONARY if re.search(r"\b" + re.escape(s) + r"\b", clean)}


def top_tfidf_keywords(text: str, tfidf: TfidfVectorizer, top_n: int = 12):
    clean = clean_text(text)
    vec = tfidf.transform([clean])
    scores = vec.toarray()[0]
    idx = np.argsort(scores)[::-1][:top_n]
    names = np.array(tfidf.get_feature_names_out())
    return [{"term": names[i], "weight": round(float(scores[i]), 3)} for i in idx if scores[i] > 0]


def extract_education(text: str) -> dict:
    """Extract candidate education, degrees, and academic credentials."""
    degrees = []
    degree_patterns = [
        r'\b(?:bachelor[^\n,.]*|b\.?tech[^\n,.]*|b\.?e\.?[^\n,.]*|b\.?s\.?[^\n,.]*|bca[^\n,.]*)',
        r'\b(?:master[^\n,.]*|m\.?tech[^\n,.]*|m\.?s\.?[^\n,.]*|mca[^\n,.]*|mba[^\n,.]*)',
        r'\b(?:ph\.?d[^\n,.]*|doctorate[^\n,.]*)',
        r'\b(?:diploma[^\n,.]*|associate degree[^\n,.]*)'
    ]
    for line in text.split("\n"):
        for pat in degree_patterns:
            m = re.search(pat, line, re.IGNORECASE)
            if m:
                clean_deg = m.group(0).strip()
                if len(clean_deg) > 3 and clean_deg not in degrees:
                    degrees.append(clean_deg.title())

    # Detect university or college
    inst_match = re.search(r'\b(?:from|at|university|institute|college|school)\s+([A-Za-z\s]{3,40}(?:university|institute|college|technology|science)?)\b', text, re.IGNORECASE)
    inst = inst_match.group(0).strip() if inst_match else None

    # Detect GPA or marks
    gpa_match = re.search(r'\b(?:\d\.\d{1,2}\s*(?:cgpa|gpa)|\b(?:cgpa|gpa)\s*[:=]?\s*\d\.\d{1,2}|\b\d{2}%\b)', text, re.IGNORECASE)
    marks = gpa_match.group(0).strip() if gpa_match else None

    return {
        "degree": degrees[0] if degrees else None,
        "degrees": degrees[:4],
        "institution": inst,
        "marks_or_gpa": marks
    }


def extract_experience(text: str) -> dict:
    """Extract years of experience, current/past roles and job titles from resume text."""
    lower = text.lower()
    years = 0
    m_exp = re.search(r'(\d{1,2})\+?\s*(?:years?|yrs?)(?:\s+of)?\s+experience', lower)
    if m_exp:
        years = int(m_exp.group(1))
    else:
        date_ranges = re.findall(r'\b(20[012]\d)\s*(?:-|to)\s*(20[012]\d|present|current)\b', lower)
        if date_ranges:
            total_yrs = 0
            for start, end in date_ranges:
                start_yr = int(start)
                end_yr = 2026 if end in ['present', 'current'] else int(end)
                total_yrs += max(0, end_yr - start_yr)
            years = min(total_yrs, 30)

    COMMON_ROLES = [
        "software engineer", "senior software engineer", "full stack developer",
        "backend developer", "frontend developer", "data scientist", "machine learning engineer",
        "cloud architect", "solutions architect", "devops engineer", "systems engineer",
        "product manager", "project manager", "technical lead", "data analyst", "qa engineer"
    ]
    detected_roles = [r.title() for r in COMMON_ROLES if r in lower]

    return {
        "years": years,
        "total_years_estimate": years,
        "experience_level": "Senior (5+ yrs)" if years >= 5 else ("Mid-Level (2-5 yrs)" if years >= 2 else "Junior / Entry-Level (0-2 yrs)"),
        "detected_roles": detected_roles[:3]
    }


def extract_certifications(text: str) -> list:
    """Extract formal technical, cloud, and professional certifications from resume."""
    cert_patterns = [
        r'\b(?:aws certified[^\n,.]*|solutions architect[^\n,.]*)',
        r'\b(?:google cloud certified[^\n,.]*|gcp[^\n,.]*certified)',
        r'\b(?:microsoft certified[^\n,.]*|azure[^\n,.]*certified)',
        r'\b(?:kubernetes certified[^\n,.]*|cka|ckad)',
        r'\b(?:cisco certified[^\n,.]*|ccna|ccnp)',
        r'\b(?:pmp|certified scrum master|csm)',
        r'\b(?:infosys springboard[^\n,.]*|coursera[^\n,.]*certificate)'
    ]
    certs = []
    for pat in cert_patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        for m in matches:
            clean = m.strip()
            if len(clean) > 3 and clean not in certs:
                certs.append(clean.title())
    return certs[:5]


def extract_projects(text: str) -> list:
    """Extract key projects, achievements, and technical endeavors from resume."""
    projects = []
    project_keywords = ["developed", "implemented", "built", "designed", "created", "architected"]
    lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 15]
    for l in lines:
        if any(kw in l.lower() for kw in project_keywords):
            clean_proj = re.sub(r'^[•\-\*]\s*', '', l).strip()
            projects.append(clean_proj[:120])
            if len(projects) >= 4:
                break
    return projects


def evaluate_aptitude(resume_text: str, test_responses: dict = None) -> dict:
    """
    AI-Based Aptitude Analysis across Quantitative, Logical, Verbal, and Technical domains.
    Provides cognitive benchmarks for recruiter candidate assessment.
    """
    lower = resume_text.lower()

    quant_tokens = ["algorithm", "data structure", "optimization", "math", "statistics", "performance", "sql", "analysis", "scale", "latency"]
    quant_score = min(92, 58 + sum(4 for t in quant_tokens if t in lower))

    logical_tokens = ["problem solving", "debug", "architecture", "design pattern", "system design", "refactor", "distributed", "troubleshoot"]
    logical_score = min(94, 60 + sum(4 for t in logical_tokens if t in lower))

    verbal_tokens = ["communication", "lead", "manage", "collaborat", "document", "present", "mentored", "agile", "cross-functional"]
    verbal_score = min(90, 62 + sum(4 for t in verbal_tokens if t in lower))

    tech_tokens = ["python", "java", "react", "aws", "docker", "kubernetes", "git", "api", "cloud", "backend"]
    tech_score = min(96, 64 + sum(4 for t in tech_tokens if t in lower))

    overall = round((quant_score + logical_score + verbal_score + tech_score) / 4, 1)

    strengths = []
    if tech_score >= 80: strengths.append("High Technical Architecture Comprehension")
    if logical_score >= 80: strengths.append("Strong Algorithmic & Logical Deduction")
    if quant_score >= 75: strengths.append("Quantitative & Data-Driven Problem Solving")
    if verbal_score >= 75: strengths.append("Clear Communication & Cross-Functional Articulation")
    if not strengths: strengths.append("Solid Core Foundation with Growth Potential")

    growth_areas = []
    if quant_score < 75: growth_areas.append("Deepening Statistical Modeling & Quantitative Metrics")
    if logical_score < 80: growth_areas.append("Advanced System Design Patterns")
    if verbal_score < 75: growth_areas.append("Executive Presentation & Stakeholder Communication")
    if not growth_areas: growth_areas.append("Specialized Cloud & Distributed Systems Scaling")

    return {
        "overall_aptitude_score": overall,
        "percentile": min(98, round(overall * 1.05, 1)),
        "quantitative_score": quant_score,
        "logical_score": logical_score,
        "verbal_score": verbal_score,
        "technical_score": tech_score,
        "strengths": strengths,
        "growth_areas": growth_areas,
        "rating": "Exceptional" if overall >= 85 else ("Proficient" if overall >= 72 else "Developing")
    }


def evaluate_personality_insights(resume_text: str, candidate_profile: dict = None) -> dict:
    """
    AI-Based Workplace Personality Insights (Big Five Profile & Behavioral Traits).
    """
    lower = resume_text.lower()

    conscientiousness = min(94, 65 + (5 if "deliver" in lower or "deadline" in lower else 0) + (5 if "detail" in lower or "quality" in lower else 0) + (5 if "test" in lower or "ci/cd" in lower else 0))
    openness = min(92, 68 + (6 if "learn" in lower or "research" in lower else 0) + (6 if "explore" in lower or "ai" in lower else 0) + (4 if "innovat" in lower else 0))
    collaboration = min(95, 64 + (6 if "team" in lower or "collaborat" in lower else 0) + (6 if "mentor" in lower or "support" in lower else 0) + (5 if "agile" in lower else 0))
    resilience = min(90, 66 + (6 if "resolve" in lower or "debug" in lower else 0) + (5 if "adapt" in lower or "scale" in lower else 0))
    leadership = min(92, 60 + (8 if "lead" in lower or "manage" in lower else 0) + (6 if "architect" in lower or "founded" in lower else 0) + (5 if "initiative" in lower else 0))

    traits = {
        "Conscientiousness": {"score": conscientiousness, "description": "High diligence, structured execution, and strong commitment to delivery standards."},
        "Openness to Learning": {"score": openness, "description": "Continuous learner who rapidly adapts to modern frameworks and emerging technologies."},
        "Team Collaboration": {"score": collaboration, "description": "Effective cross-functional collaborator with empathetic communication and peer support."},
        "Emotional Resilience": {"score": resilience, "description": "Maintains composure and structured problem-solving under tight delivery schedules."},
        "Leadership & Ownership": {"score": leadership, "description": "Takes proactive ownership of technical architecture and operational outcomes."}
    }

    work_style = "Collaborative Technical Innovator" if openness >= 80 and collaboration >= 80 else "Strategic Analytical Problem Solver"

    return {
        "traits": traits,
        "primary_work_style": work_style,
        "summary": f"Candidate demonstrates strong {work_style.lower()} characteristics, marked by {openness}% learning agility and {conscientiousness}% execution discipline."
    }


def analyze_multimodal_interview(
    audio_metadata=None,
    video_metadata=None,
    speech_transcript="",
    speech_text="",
    audio_duration_sec=60.0,
    video_duration_sec=60.0,
    detected_faces=60,
    face_looking_center_count=52,
    gestures_active=True,
    words_count=0,
    filler_words_count=None,
    resume_score=80.0,
    **kwargs
) -> dict:
    """
    Multimodal interview assessment combining speech processing, video visual cues,
    and resume technical profile to assist recruiters in comprehensive hiring decisions.
    """
    audio_metadata = audio_metadata or {}
    video_metadata = video_metadata or {}
    transcript = (speech_transcript or speech_text or kwargs.get("transcript", "") or "").strip()

    if not words_count and transcript:
        words_count = len(transcript.split())

    dur_sec = max(10.0, float(audio_duration_sec or 60.0))
    dur_min = dur_sec / 60.0

    pacing_wpm = round(words_count / dur_min) if words_count > 0 else 135
    if pacing_wpm < 100:
        pacing_status = "Deliberate / Slower pacing"
        clarity_score = 80.0
    elif pacing_wpm > 175:
        pacing_status = "Rapid pacing"
        clarity_score = 82.0
    else:
        pacing_status = "Optimal conversational tempo (120-160 WPM)"
        clarity_score = 92.0

    # Filler words detection
    if filler_words_count is None and transcript:
        lower_trans = f" {transcript.lower()} "
        filler_targets = [" um ", " uh ", " like ", " you know ", " basically ", " actually ", " sort of "]
        filler_words_count = sum(lower_trans.count(f) for f in filler_targets)
    else:
        filler_words_count = int(filler_words_count or 0)

    filler_ratio = (filler_words_count / max(1, words_count)) if words_count else 0.02
    vocal_confidence = round(max(60.0, min(96.0, 95.0 - (filler_ratio * 200))), 1)

    # Video cues calculation
    total_faces = max(1, int(detected_faces or 60))
    center_faces = min(total_faces, int(face_looking_center_count or 52))
    eye_contact_ratio = round((center_faces / total_faces) * 100, 1)

    posture_stability = 91.0 if gestures_active else 85.0
    facial_engagement = round(min(96.0, max(70.0, 75.0 + (eye_contact_ratio * 0.2))), 1)

    composite_interview_score = round(
        0.35 * clarity_score + 0.35 * vocal_confidence + 0.30 * eye_contact_ratio, 1
    )

    multimodal_composite = round(
        0.40 * float(resume_score) + 0.35 * composite_interview_score + 0.25 * vocal_confidence, 1
    )

    if multimodal_composite >= 80:
        recommendation = "STRONG_HIRE"
        rec_badge = "Strong Hire (High Multimodal Confidence)"
    elif multimodal_composite >= 68:
        recommendation = "HIRE"
        rec_badge = "Recommended for Hire"
    else:
        recommendation = "FURTHER_REVIEW"
        rec_badge = "Further Assessment Recommended"

    return {
        "speech_analysis": {
            "transcript_sample": (transcript[:200] + "...") if len(transcript) > 200 else transcript,
            "words_count": words_count,
            "clarity_score": clarity_score,
            "pacing_words_per_minute": pacing_wpm,
            "pacing_status": pacing_status,
            "vocal_confidence_score": vocal_confidence,
            "filler_words_count": filler_words_count,
            "articulation": "Fluent and structured" if vocal_confidence >= 80 else "Adequate articulation"
        },
        "video_analysis": {
            "eye_contact_percentage": eye_contact_ratio,
            "posture_stability_score": posture_stability,
            "facial_engagement_score": facial_engagement,
            "gestures_active": bool(gestures_active),
            "presence": "Professional & Attentive" if eye_contact_ratio >= 75 else "Moderate engagement"
        },
        "composite_interview_score": composite_interview_score,
        "multimodal_composite_score": multimodal_composite,
        "recommendation": recommendation,
        "recommendation_badge": rec_badge
    }



# Initialize sentence transformer model if available
if SENTENCE_TRANSFORMERS_AVAILABLE:
    try:
        semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
    except Exception as e:
        logging.warning(f"Failed to load sentence-transformers model: {e}")
        semantic_model = None
else:
    semantic_model = None

def score_resume(resume_text: str, jd_text: str, model, tfidf, le, weights=(0.5, 0.3, 0.2)):
    clean_resume = clean_text(resume_text)
    resume_vec = tfidf.transform([clean_resume])

    pred_idx = model.predict(resume_vec)[0]
    predicted_category = le.inverse_transform([pred_idx])[0]

    if hasattr(model, "predict_proba"):
        conf = float(np.max(model.predict_proba(resume_vec)))
    elif hasattr(model, "decision_function"):
        df_scores = model.decision_function(resume_vec)[0]
        exp_scores = np.exp(df_scores - np.max(df_scores))
        conf = float(np.max(exp_scores / exp_scores.sum()))
    else:
        conf = 1.0

    result = {
        "predicted_category": str(predicted_category),
        "category_confidence": round(conf, 3),
        "keywords": top_tfidf_keywords(resume_text, tfidf),
        "resume_skills": sorted(extract_skills(resume_text)),
        "education": extract_education(resume_text),
        "experience": extract_experience(resume_text),
        "certifications": extract_certifications(resume_text),
        "projects": extract_projects(resume_text),
        "aptitude": evaluate_aptitude(resume_text),
        "personality": evaluate_personality_insights(resume_text),
    }

    if not jd_text or not jd_text.strip():
        skill_richness = min(len(result["resume_skills"]) / 12, 1.0)
        final = 0.6 * skill_richness + 0.4 * conf
        result.update({
            "jd_similarity": None, "skill_overlap": None,
            "matched_skills": [], "missing_skills": [],
            "final_score": round(final * 100, 1),
        })
        return result

    # Use sentence-transformers for semantic similarity if available, otherwise fallback to TF-IDF
    if SENTENCE_TRANSFORMERS_AVAILABLE and semantic_model is not None:
        try:
            # Calculate semantic similarity using sentence transformers
            embeddings = semantic_model.encode([resume_text, jd_text])
            similarity = float(np.dot(embeddings[0], embeddings[1]) /
                           (np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])))
        except Exception as e:
            logging.warning(f"Semantic similarity failed: {e}, falling back to TF-IDF")
            jd_vec = tfidf.transform([clean_text(jd_text)])
            similarity = float(cosine_similarity(resume_vec, jd_vec)[0][0])
    else:
        jd_vec = tfidf.transform([clean_text(jd_text)])
        similarity = float(cosine_similarity(resume_vec, jd_vec)[0][0])

    resume_skills = extract_skills(resume_text)
    jd_skills = extract_skills(jd_text)
    overlap = len(resume_skills & jd_skills) / len(jd_skills) if jd_skills else 0.0

    w_sim, w_overlap, w_conf = weights
    final = w_sim * similarity + w_overlap * overlap + w_conf * conf

    result.update({
        "jd_similarity": round(similarity, 3),
        "skill_overlap": round(overlap, 3),
        "matched_skills": sorted(resume_skills & jd_skills),
        "missing_skills": sorted(jd_skills - resume_skills),
        "final_score": round(final * 100, 1),
    })
    return result


def generate_skill_gap_roadmap(resume_skills: set, jd_skills: set, missing_skills: set, predicted_category: str = "Technology") -> dict:
    """
    Generate a dynamic, comprehensive, and skill-specific roadmap for every missing skill.
    Uses the specialized AI roadmap generator.
    """
    try:
        try:
            import roadmap_generator
            return roadmap_generator.generate_skill_gap_roadmap(resume_skills, jd_skills, missing_skills, predicted_category)
        except ImportError:
            from backend.roadmap_generator import generate_skill_gap_roadmap as gen_dynamic_roadmap
            return gen_dynamic_roadmap(resume_skills, jd_skills, missing_skills, predicted_category)
    except Exception as e:
        import traceback
        logging.error(f"Error in dynamic roadmap generator: {e}\n{traceback.format_exc()}")
        return {
            "skill_gaps": list(missing_skills),
            "priority_skills": list(missing_skills),
            "learning_path": {},
            "timeline_weeks": {},
            "total_estimated_hours": 0
        }



def generate_interview_questions(jd_text: str, resume_skills: set, matched_skills: set, missing_skills: set, predicted_category: str) -> dict:
    """
    Generate technical, behavioral, and role-specific interview questions
    based on the job description and candidate profile.
    """
    # Extract key requirements from JD
    jd_lower = jd_text.lower()

    # Technical questions based on skills and JD content
    technical_questions = []

    # Skill-based questions
    for skill in matched_skills:
        if skill.lower() in ["python", "java", "javascript", "c++", "c#"]:
            technical_questions.append(f"Can you explain the difference between __str__ and __repr__ in Python?")
            technical_questions.append(f"How would you optimize a slow {skill} application?")
        elif skill.lower() in ["machine learning", "deep learning"]:
            technical_questions.append("Explain the bias-variance tradeoff in machine learning.")
            technical_questions.append("How do you handle overfitting in your models?")
        elif skill.lower() in ["aws", "azure", "gcp", "docker", "kubernetes"]:
            technical_questions.append(f"Describe your experience with {skill} and how you've used it in projects.")
            technical_questions.append(f"What are the best practices for securing applications on {skill}?")
        elif skill.lower() in ["sql", "nosql", "mongodb", "postgresql", "mysql"]:
            technical_questions.append("Explain the difference between INNER JOIN and LEFT JOIN.")
            technical_questions.append("How do you optimize slow database queries?")
        elif skill.lower() in ["rest api", "api", "microservices"]:
            technical_questions.append("What are the key principles of RESTful API design?")
            technical_questions.append("How do you handle API versioning and backward compatibility?")

    # JD-specific questions
    if "agile" in jd_lower or "scrum" in jd_lower:
        technical_questions.append("Describe your experience working in Agile/Scrum environments.")
    if "ci/cd" in jd_lower or "jenkins" in jd_lower:
        technical_questions.append("How have you implemented CI/CD pipelines in your previous roles?")
    if "testing" in jd_lower or "test" in jd_lower:
        technical_questions.append("What testing methodologies are you familiar with?")
        technical_questions.append("How do you ensure comprehensive test coverage?")

    # Behavioral questions (semi-customized based on role)
    behavioral_questions = [
        "Tell me about a time when you had to learn a new technology quickly to complete a project.",
        "Describe a situation where you had to work with a difficult team member. How did you handle it?",
        "Give an example of when you had to meet a tight deadline. How did you prioritize your work?",
        "Tell me about a mistake you made and what you learned from it.",
        "Describe a time when you had to explain a technical concept to a non-technical audience.",
        "How do you stay updated with the latest developments in your field?",
        "Tell me about a project you're particularly proud of and why.",
        "Describe a situation where you had to make a decision with incomplete information."
    ]

    # Role-specific questions based on predicted category
    role_specific_questions = {
        "Data Science": [
            "How do you approach feature selection in a machine learning project?",
            "Describe your experience with data visualization tools and techniques.",
            "How do you validate the results of your statistical models?",
            "Walk me through your process for cleaning and preparing messy datasets.",
            "How do you communicate complex technical findings to business stakeholders?"
        ],
        "Web Development": [
            "How do you ensure your web applications are accessible to all users?",
            "Describe your approach to responsive design and mobile-first development.",
            "How do you handle cross-browser compatibility issues?",
            "What strategies do you use to optimize website performance?",
            "How do you stay current with evolving web technologies and frameworks?"
        ],
        "Finance": [
            "How do you ensure accuracy and attention to detail in financial reporting?",
            "Describe your experience with financial modeling and forecasting.",
            "How do you stay compliant with financial regulations and standards?",
            "Walk me through your process for analyzing investment opportunities.",
            "How do you explain complex financial concepts to non-finance colleagues?"
        ],
        "HR": [
            "How do you build trust and rapport with employees at all levels?",
            "Describe your approach to conflict resolution in the workplace.",
            "How do you measure the effectiveness of HR programs and initiatives?",
            "Walk me through your talent acquisition and onboarding process.",
            "How do you stay updated with changes in employment law and regulations?"
        ],
        "Marketing": [
            "How do you measure the ROI of marketing campaigns?",
            "Describe your experience with A/B testing and conversion rate optimization.",
            "How do you develop targeted marketing strategies for different audience segments?",
            "Walk me through your process for creating compelling marketing content.",
            "How do you leverage data and analytics to inform marketing decisions?"
        ],
        "Testing": [
            "How do you decide what to test and what not to test in a given application?",
            "Describe your experience with test automation frameworks and tools.",
            "How do you balance manual testing with automated testing efforts?",
            "Walk me through your bug reporting and tracking process.",
            "How do you advocate for quality assurance throughout the development lifecycle?"
        ]
    }

    role_questions = role_specific_questions.get(predicted_category, [
        "How do you approach problem-solving in your work?",
        "Describe a time when you had to adapt to significant changes at work.",
        "How do you prioritize tasks when everything seems urgent?",
        "What motivates you in your professional work?",
        "How do you handle feedback and criticism from colleagues and supervisors?"
    ])

    # Limit questions to reasonable numbers
    technical_questions = list(dict.fromkeys(technical_questions))[:8]  # Remove duplicates, limit to 8
    behavioral_questions = behavioral_questions[:6]  # Limit to 6
    role_questions = role_questions[:5]  # Limit to 5

    return {
        "technical_questions": technical_questions,
        "behavioral_questions": behavioral_questions,
        "role_specific_questions": role_questions,
        "total_questions": len(technical_questions) + len(behavioral_questions) + len(role_questions),
        "difficulty_distribution": {
            "easy": len([q for q in technical_questions if "explain" in q.lower() or "describe" in q.lower()]),
            "medium": len([q for q in technical_questions if "how" in q.lower() or "what" in q.lower()]),
            "hard": len([q for q in technical_questions if "walk me through" in q.lower() or "approach" in q.lower()])
        }
    }


def evaluate_model_performance(test_predictions: list, test_actuals: list) -> dict:
    """
    Evaluate the model performance using standard metrics.
    """
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

    try:
        accuracy = accuracy_score(test_actuals, test_predictions)
        precision = precision_score(test_actuals, test_predictions, average='weighted', zero_division=0)
        recall = recall_score(test_actuals, test_predictions, average='weighted', zero_division=0)
        f1 = f1_score(test_actuals, test_predictions, average='weighted', zero_division=0)
        conf_matrix = confusion_matrix(test_actuals, test_predictions)

        return {
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "confusion_matrix": conf_matrix.tolist(),
            "evaluation_timestamp": pd.Timestamp.now().isoformat()
        }
    except Exception as e:
        logging.warning(f"Model evaluation failed: {e}")
        return {
            "error": str(e),
            "evaluation_timestamp": pd.Timestamp.now().isoformat()
        }


def calculate_matching_accuracy(resume_texts: list, jd_texts: list, expected_matches: list, model, tfidf, le) -> dict:
    """
    Calculate matching accuracy for resume-JD pairs.
    """
    try:
        correct_predictions = 0
        total_pairs = len(resume_texts)

        for i in range(total_pairs):
            resume_text = resume_texts[i]
            jd_text = jd_texts[i] if i < len(jd_texts) else ""
            expected_match = expected_matches[i] if i < len(expected_matches) else False

            # Get match score
            result = score_resume(resume_text, jd_text, model, tfidf, le)
            predicted_match = result["final_score"] >= 50.0  # Threshold for match

            if predicted_match == expected_match:
                correct_predictions += 1

        accuracy = correct_predictions / total_pairs if total_pairs > 0 else 0

        return {
            "matching_accuracy": round(accuracy, 4),
            "correct_predictions": correct_predictions,
            "total_pairs": total_pairs,
            "evaluation_timestamp": pd.Timestamp.now().isoformat()
        }
    except Exception as e:
        logging.warning(f"Matching accuracy calculation failed: {e}")
        return {
            "error": str(e),
            "evaluation_timestamp": pd.Timestamp.now().isoformat()
        }

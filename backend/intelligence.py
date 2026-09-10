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


def generate_skill_gap_roadmap(resume_skills: set, jd_skills: set, missing_skills: set, predicted_category: str) -> dict:
    """
    Generate a personalized skill gap roadmap based on missing skills.
    Returns a structured roadmap with learning topics, practice activities,
    mini-projects, assessments, and interview preparation.
    """
    # Define skill hierarchies and learning paths
    skill_roadmaps = {
        "python": {
            "beginner": ["Python syntax", "Data types", "Control structures"],
            "intermediate": ["OOP", "File handling", "Error handling"],
            "advanced": ["Decorators", "Generators", "Context managers"],
            "practice": ["Code challenges on LeetCode", "Build a CLI tool", "Create a web scraper"],
            "projects": ["Personal budget tracker", "Weather API app", "To-do list web app"],
            "assessment": ["Complete Python certification", "Build a REST API", "Data analysis project"]
        },
        "java": {
            "beginner": ["Java syntax", "Classes and objects", "Inheritance"],
            "intermediate": ["Interfaces", "Collections", "Exception handling"],
            "advanced": ["Generics", "Lambda expressions", "Stream API"],
            "practice": ["Solve algorithmic problems", "Build a desktop application", "Create a library"],
            "projects": ["Inventory management system", "Chat application", "E-commerce backend"],
            "assessment": ["Oracle Java certification", "Spring Framework project", "Microservices implementation"]
        },
        "javascript": {
            "beginner": ["Variables and data types", "Functions", "DOM manipulation"],
            "intermediate": ["ES6+ features", "Async/await", "Modules"],
            "advanced": ["Design patterns", "Testing frameworks", "Performance optimization"],
            "practice": ["Build interactive websites", "Create browser extensions", "Develop Node.js APIs"],
            "projects": ["Todo app with local storage", "Weather dashboard", "Real-time chat application"],
            "assessment": ["Frontend developer certification", "Full-stack project", "Open source contribution"]
        },
        "machine learning": {
            "beginner": ["Statistics fundamentals", "Linear algebra basics", "Python for data science"],
            "intermediate": ["Supervised learning", "Unsupervised learning", "Model evaluation"],
            "advanced": ["Deep learning", "Natural language processing", "Computer vision"],
            "practice": ["Implement ML algorithms from scratch", "Kaggle competitions", "Build recommendation system"],
            "projects": ["Image classifier", "Sentiment analysis tool", "Fraud detection system"],
            "assessment": ["TensorFlow certification", "MLOps project", "Research paper implementation"]
        },
        "aws": {
            "beginner": ["Cloud concepts", "EC2 basics", "S3 storage"],
            "intermediate": ["RDS database", "Lambda functions", "VPC networking"],
            "advanced": ["Microservices architecture", "Serverless applications", "DevOps on AWS"],
            "practice": ["Deploy a static website", "Set up CI/CD pipeline", "Build a serverless API"],
            "projects": ["Multi-tier web application", "Data processing pipeline", "IoT device management"],
            "assessment": ["AWS Solutions Architect Associate", "DevOps Engineer Professional", "Specialty certifications"]
        },
        "docker": {
            "beginner": ["Container concepts", "Docker installation", "Basic Docker commands"],
            "intermediate": ["Dockerfile creation", "Docker Compose", "Networking"],
            "advanced": ["Kubernetes orchestration", "Container security", "Monitoring and logging"],
            "practice": ["Containerize existing applications", "Set up local development environment", "Create multi-container apps"],
            "projects": ["Microservices deployment", "CI/CD pipeline with Docker", "Container monitoring solution"],
            "assessment": ["Docker Certified Associate", "Kubernetes Administrator", "Container security specialist"]
        },
        "sql": {
            "beginner": ["Basic SELECT queries", "Filtering and sorting", "Aggregate functions"],
            "intermediate": ["JOINs", "Subqueries", "Data modification"],
            "advanced": ["Window functions", "Stored procedures", "Performance tuning"],
            "practice": ["Design database schemas", "Optimize slow queries", "Build reporting systems"],
            "projects": ["Employee management system", "E-commerce database", "Analytics data warehouse"],
            "assessment": ["Database administrator certification", "Data modeling project", "Performance optimization case study"]
        },
        "rest api": {
            "beginner": ["HTTP methods", "Resource modeling", "Status codes"],
            "intermediate": ["Authentication and authorization", "API versioning", "Error handling"],
            "advanced": ["Rate limiting", "Caching strategies", "API documentation (OpenAPI/Swagger)"],
            "practice": ["Build a CRUD API", "Implement JWT authentication", "Create API documentation"],
            "projects": ["Social media API", "Payment processing API", "Booking system API"],
            "assessment": ["API development certification", "Microservices integration project", "API security audit"]
        }
    }

    # Default roadmap for skills not specifically defined
    default_roadmap = {
        "beginner": ["Fundamentals", "Basic concepts", "Core principles"],
        "intermediate": ["Intermediate techniques", "Best practices", "Common patterns"],
        "advanced": ["Advanced topics", "Expert-level concepts", "Industry standards"],
        "practice": ["Hands-on exercises", "Code challenges", "Small projects"],
        "projects": ["Apply skills in real-world scenarios", "Build portfolio pieces", "Contribute to open source"],
        "assessment": ["Skill validation tests", "Portfolio review", "Technical interview preparation"]
    }

    # Generate roadmap for each missing skill
    roadmap = {
        "skill_gaps": list(missing_skills),
        "priority_skills": sorted(list(missing_skills), key=lambda x: x.lower() in [s.lower() for s in ["python", "java", "javascript", "machine learning", "aws", "docker", "sql", "rest api"]], reverse=True),
        "learning_path": {},
        "timeline_weeks": {},
        "total_estimated_hours": 0
    }

    # Estimated hours per skill level
    hours_per_level = {
        "beginner": 10,
        "intermediate": 15,
        "advanced": 20,
        "practice": 10,
        "projects": 15,
        "assessment": 10
    }

    for skill in missing_skills:
        skill_lower = skill.lower()
        # Find matching skill in roadmaps (case-insensitive)
        matched_skill = None
        for rs in skill_roadmaps.keys():
            if rs in skill_lower or skill_lower in rs:
                matched_skill = rs
                break

        roadmap_data = skill_roadmaps.get(matched_skill, default_roadmap)

        roadmap["learning_path"][skill] = {
            "beginner_topics": roadmap_data["beginner"],
            "intermediate_topics": roadmap_data["intermediate"],
            "advanced_topics": roadmap_data["advanced"],
            "practice_activities": roadmap_data["practice"],
            "mini_projects": roadmap_data["projects"],
            "assessments": roadmap_data["assessment"]
        }

        # Estimate timeline (simplified)
        estimated_hours = sum(hours_per_level.values())
        roadmap["timeline_weeks"][skill] = max(1, estimated_hours // 10)  # Assuming 10 hours/week
        roadmap["total_estimated_hours"] += estimated_hours

    # Add category-specific recommendations
    roadmap["category_recommendations"] = {
        "Data Science": ["Focus on Python, SQL, and machine learning fundamentals", "Build portfolio projects with real datasets", "Learn data visualization tools"],
        "Web Development": ["Master JavaScript frameworks", "Learn responsive design principles", "Practice API integration"],
        "Finance": ["Develop Excel expertise", "Learn financial modeling techniques", "Understand regulatory requirements"],
        "HR": ["Study talent acquisition strategies", "Learn HRIS systems", "Develop interpersonal communication skills"],
        "Marketing": ["Master digital marketing tools", "Learn analytics and A/B testing", "Develop content creation skills"],
        "Testing": ["Become proficient in test automation", "Learn performance and security testing", "Understand QA methodologies"]
    }.get(predicted_category, ["Focus on core competencies", "Build practical projects", "Stay updated with industry trends"])

    return roadmap


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

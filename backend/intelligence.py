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

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import LabelEncoder

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

    candidates = {
        "LogisticRegression": LogisticRegression(max_iter=1000, class_weight="balanced"),
        "LinearSVC": LinearSVC(class_weight="balanced"),
        "RandomForest": RandomForestClassifier(n_estimators=200, random_state=42),
    }

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
    clean = clean_text(text)
    return {s for s in SKILL_DICTIONARY if re.search(r"\b" + re.escape(s) + r"\b", clean)}


def top_tfidf_keywords(text: str, tfidf: TfidfVectorizer, top_n: int = 12):
    clean = clean_text(text)
    vec = tfidf.transform([clean])
    scores = vec.toarray()[0]
    idx = np.argsort(scores)[::-1][:top_n]
    names = np.array(tfidf.get_feature_names_out())
    return [{"term": names[i], "weight": round(float(scores[i]), 3)} for i in idx if scores[i] > 0]


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

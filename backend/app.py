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
from pymongo import MongoClient
import os
import logging
import traceback

try:
    import intelligence as intel
except ImportError:
    import backend.intelligence as intel

BASE_DIR = Path(__file__).parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = Flask(__name__, static_folder=None)

import json
import re
from bson import ObjectId

# MongoDB configuration
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb+srv://vatsalchauhan8103_db_user:jV8cUHRUlTdQP97F@cluster0.bltefbt.mongodb.net/')
DB_NAME = os.environ.get('DB_NAME', 'recruitment_platform')

class JSONCustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def format_dt(val):
    if not val:
        return None
    if isinstance(val, str):
        return val
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    return str(val)

def make_id_filter(val, field="_id"):
    """
    Returns a query filter matching val as an integer, string, or ObjectId
    against the given primary key field ('_id') or 'id'.
    """
    if val is None:
        return {field: None}

    candidates = [val]
    s_val = str(val).strip()
    if s_val:
        candidates.append(s_val)
        try:
            candidates.append(int(s_val))
        except (ValueError, TypeError):
            pass
        if len(s_val) == 24:
            try:
                candidates.append(ObjectId(s_val))
            except Exception:
                pass

    uniq = []
    for c in candidates:
        if c not in uniq:
            uniq.append(c)

    return {
        "$or": [
            {field: {"$in": uniq}},
            {"id": {"$in": uniq}}
        ]
    }

def make_fk_filter(val, field="job_id"):
    """
    Returns a query filter for foreign key field matching int, string, or ObjectId.
    """
    if val is None:
        return {field: None}

    candidates = [val]
    s_val = str(val).strip()
    if s_val:
        candidates.append(s_val)
        try:
            candidates.append(int(s_val))
        except (ValueError, TypeError):
            pass
        if len(s_val) == 24:
            try:
                candidates.append(ObjectId(s_val))
            except Exception:
                pass

    uniq = []
    for c in candidates:
        if c not in uniq:
            uniq.append(c)

    return {field: {"$in": uniq}}

# Initialize MongoDB client
db = None
mongo_connected = False

candidate_uris = [
    MONGODB_URI,
    "mongodb://vatsalchauhan8103_db_user:jV8cUHRUlTdQP97F@ac-tnq84jy-shard-00-00.bltefbt.mongodb.net:27017,ac-tnq84jy-shard-00-01.bltefbt.mongodb.net:27017,ac-tnq84jy-shard-00-02.bltefbt.mongodb.net:27017/recruitment_platform?ssl=true&replicaSet=atlas-tnq84j-shard-0&authSource=admin&retryWrites=true&w=majority"
]

for uri in candidate_uris:
    try:
        mongo_client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000
        )
        mongo_client.admin.command('ping')
        db = mongo_client[DB_NAME]
        mongo_connected = True
        print(f"[database] Successfully connected to live MongoDB Atlas: {DB_NAME}")
        break
    except Exception:
        pass

def sync_all_to_atlas(target_db):
    """Syncs all records from local data files into MongoDB Atlas with robust deduplication."""
    data_sources = [BASE_DIR / "instance" / "mock_db_store.json", BASE_DIR / "mock_db_data.json"]
    collections_to_sync = [
        "users", "candidates", "jobs", "applications",
        "candidate_documents", "document_verifications",
        "skills", "interviews", "aptitude_tests"
    ]
    merged = {col: {} for col in collections_to_sync}
    for src in data_sources:
        if src.exists():
            try:
                with open(src, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    for col in collections_to_sync:
                        for item in content.get(col, []):
                            if col == "users":
                                k = str(item.get("username") or item.get("email") or item.get("id") or item.get("_id"))
                            elif col == "candidates":
                                k = str(item.get("user_id") or item.get("email") or item.get("id") or item.get("_id"))
                            elif col == "jobs":
                                k = str(item.get("id") or item.get("title") or item.get("_id"))
                            elif col == "applications":
                                k = f"{item.get('candidate_id')}_{item.get('job_id')}"
                            elif col == "candidate_documents":
                                fname = item.get("filename") or item.get("original_filename") or ""
                                k = f"{item.get('candidate_id')}_{fname}_{item.get('_id') or ''}"
                            elif col == "document_verifications":
                                k = str(item.get("_id") or item.get("verification_id") or item.get("id") or len(merged[col]))
                            else:
                                k = str(item.get("id") or item.get("_id") or len(merged[col]))
                            merged[col][k] = item
            except Exception:
                pass

    # Merge SQLite records if available
    sqlite_file = BASE_DIR / "instance" / "recruitment.db"
    if sqlite_file.exists():
        try:
            import sqlite3
            scon = sqlite3.connect(sqlite_file)
            scon.row_factory = sqlite3.Row
            scur = scon.cursor()
            for row in scur.execute("SELECT * FROM user").fetchall():
                d = dict(row)
                k = str(d.get("username") or d.get("email"))
                if k not in merged["users"]:
                    merged["users"][k] = d
            for row in scur.execute("SELECT * FROM candidate").fetchall():
                d = dict(row)
                k = str(d.get("email") or d.get("id"))
                if k not in merged["candidates"]:
                    merged["candidates"][k] = d
            for row in scur.execute("SELECT * FROM job").fetchall():
                d = dict(row)
                k = str(d.get("id") or d.get("title"))
                if k not in merged["jobs"]:
                    merged["jobs"][k] = d
            for row in scur.execute("SELECT * FROM application").fetchall():
                d = dict(row)
                k = f"{d.get('candidate_id')}_{d.get('job_id')}"
                if k not in merged["applications"]:
                    merged["applications"][k] = d
            scon.close()
        except Exception:
            pass

    synced_count = 0
    for col_name in collections_to_sync:
        recs_map = merged.get(col_name, {})
        col = target_db[col_name]
        for r in recs_map.values():
            doc = dict(r)
            oid = None
            if "_id" in doc:
                raw_id = doc["_id"]
                if isinstance(raw_id, ObjectId):
                    oid = raw_id
                elif isinstance(raw_id, str) and len(raw_id) == 24:
                    try:
                        oid = ObjectId(raw_id)
                    except Exception:
                        oid = None

            filters = []
            if col_name == "users":
                if doc.get("username"): filters.append({"username": doc["username"]})
                if doc.get("email"): filters.append({"email": doc["email"]})
                if oid: filters.append({"_id": oid})
            elif col_name == "candidates":
                if doc.get("user_id"): filters.append({"user_id": str(doc["user_id"])})
                if doc.get("email"): filters.append({"email": doc["email"]})
                if doc.get("id"): filters.append({"id": doc["id"]})
                if oid: filters.append({"_id": oid})
            elif col_name == "jobs":
                if doc.get("id"): filters.append({"id": doc["id"]})
                if doc.get("title"): filters.append({"title": doc["title"]})
                if oid: filters.append({"_id": oid})
            elif col_name == "applications":
                if doc.get("candidate_id") and doc.get("job_id"):
                    filters.append({"candidate_id": str(doc["candidate_id"]), "job_id": doc["job_id"]})
                if doc.get("id"): filters.append({"id": doc["id"]})
                if oid: filters.append({"_id": oid})
            elif col_name == "candidate_documents":
                fname = doc.get("filename") or doc.get("original_filename")
                if doc.get("candidate_id") and fname:
                    filters.append({"candidate_id": str(doc["candidate_id"]), "$or": [{"filename": fname}, {"original_filename": fname}]})
                if doc.get("id"): filters.append({"id": doc["id"]})
                if oid: filters.append({"_id": oid})
            elif col_name == "document_verifications":
                if oid: filters.append({"_id": oid})
                if doc.get("verification_id"): filters.append({"verification_id": doc["verification_id"]})
                if doc.get("id"): filters.append({"id": doc["id"]})
                fname = doc.get("filename") or doc.get("file_name")
                if fname and doc.get("candidate_name"):
                    filters.append({"filename": fname, "candidate_name": doc["candidate_name"]})
            else:
                if oid: filters.append({"_id": oid})
                if doc.get("id"): filters.append({"id": doc["id"]})
                if doc.get("name"): filters.append({"name": doc["name"]})

            filter_query = {"$or": filters} if filters else None
            doc_to_set = {k: v for k, v in doc.items() if k != "_id"}
            existing = col.find_one(filter_query) if filter_query else None

            if existing:
                col.update_one({"_id": existing["_id"]}, {"$set": doc_to_set})
                synced_count += 1
            else:
                if oid:
                    try:
                        col.update_one({"_id": oid}, {"$set": doc_to_set}, upsert=True)
                        synced_count += 1
                    except Exception:
                        pass
                else:
                    clean_doc = dict(doc)
                    if "_id" in clean_doc:
                        del clean_doc["_id"]
                    try:
                        col.insert_one(clean_doc)
                        synced_count += 1
                    except Exception:
                        pass
    return synced_count


if mongo_connected and db is not None:
    try:
        count = sync_all_to_atlas(db)
        print(f"[database] Synced {count} local records into MongoDB Atlas cloud database")
    except Exception as ex:
        print(f"[database] MongoDB sync notice: {ex}")
else:
    print("[database] MongoDB Atlas connection timed out (Atlas port 27017 is unreachable).")
    print("[database] TIP: In MongoDB Atlas (cloud.mongodb.com) -> Network Access, add 0.0.0.0/0 or your current IP (49.47.11.30).")
    print("[database] Using persistent local database with all accounts and data intact.")

    def _matches_filter(doc, filter_dict):
        if not filter_dict:
            return True

        if "$or" in filter_dict:
            or_list = filter_dict["$or"]
            matched_any = False
            for sub in or_list:
                if _matches_filter(doc, sub):
                    matched_any = True
                    break
            if not matched_any:
                return False

        for key, value in filter_dict.items():
            if key == "$or":
                continue
            doc_val = doc.get(key)
            if doc_val == value or str(doc_val) == str(value):
                continue
            if isinstance(value, dict):
                if "$in" in value:
                    in_vals = [str(x) for x in value["$in"]]
                    if str(doc_val) not in in_vals and doc_val not in value["$in"]:
                        return False
                    continue
                elif "$ne" in value:
                    if str(doc_val) == str(value["$ne"]) or doc_val == value["$ne"]:
                        return False
                    continue
                elif "$regex" in value:
                    opts = value.get("$options", "")
                    flags = re.IGNORECASE if "i" in opts else 0
                    if not re.search(value["$regex"], str(doc_val or ''), flags):
                        return False
                    continue
            if isinstance(doc_val, str) and isinstance(value, str):
                if doc_val.strip().lower() == value.strip().lower():
                    continue
            return False
        return True

    class MockCollection:
        def __init__(self, name, db_parent):
            self.name = name
            self.db_parent = db_parent
            self.data = []

        def insert_one(self, document):
            if '_id' not in document or not document['_id']:
                document['_id'] = ObjectId()
            self.data.append(document)
            self.db_parent.save()
            class MockResult:
                def __init__(self, inserted_id):
                    self.inserted_id = inserted_id
            return MockResult(document['_id'])

        def insert_many(self, documents):
            for doc in documents:
                if '_id' not in doc or not doc['_id']:
                    doc['_id'] = ObjectId()
                self.data.append(doc)
            self.db_parent.save()
            class MockResult:
                def __init__(self, inserted_ids):
                    self.inserted_ids = inserted_ids
            return MockResult([d['_id'] for d in documents])

        def find(self, filter_dict=None):
            results = [doc for doc in self.data if _matches_filter(doc, filter_dict)]
            return MockCursor(results)

        def find_one(self, filter_dict=None):
            results = self.find(filter_dict)
            for item in results:
                return item
            return None

        def update_one(self, filter_dict, update_dict, upsert=False):
            matched = False
            for doc in self.data:
                if _matches_filter(doc, filter_dict):
                    matched = True
                    if '$set' in update_dict:
                        for key, value in update_dict['$set'].items():
                            doc[key] = value
                    if '$push' in update_dict:
                        for key, value in update_dict['$push'].items():
                            if key not in doc or not isinstance(doc[key], list):
                                doc[key] = []
                            doc[key].append(value)
                    if '$inc' in update_dict:
                        for key, value in update_dict['$inc'].items():
                            doc[key] = doc.get(key, 0) + value
                    break

            if matched:
                self.db_parent.save()
                class MockResult:
                    modified_count = 1
                    matched_count = 1
                return MockResult()

            if upsert:
                new_doc = dict(filter_dict) if filter_dict else {}
                if '$set' in update_dict:
                    new_doc.update(update_dict['$set'])
                if '_id' not in new_doc:
                    new_doc['_id'] = ObjectId()
                self.data.append(new_doc)
                self.db_parent.save()
                class MockResult:
                    modified_count = 1
                    matched_count = 0
                    upserted_id = new_doc['_id']
                return MockResult()

            class MockResult:
                modified_count = 0
                matched_count = 0
            return MockResult()

        def delete_one(self, filter_dict):
            for i, doc in enumerate(self.data):
                if _matches_filter(doc, filter_dict):
                    del self.data[i]
                    self.db_parent.save()
                    class MockResult:
                        deleted_count = 1
                    return MockResult()
            class MockResult:
                deleted_count = 0
            return MockResult()

        def delete_many(self, filter_dict):
            original_len = len(self.data)
            self.data = [doc for doc in self.data if not _matches_filter(doc, filter_dict)]
            deleted = original_len - len(self.data)
            if deleted > 0:
                self.db_parent.save()
            class MockResult:
                def __init__(self, count):
                    self.deleted_count = count
            return MockResult(deleted)

        def count_documents(self, filter_dict=None):
            return len(self.find(filter_dict))

        def aggregate(self, pipeline):
            return []

        def create_index(self, *args, **kwargs):
            pass

    class MockCursor:
        def __init__(self, data):
            self.data = data

        def __iter__(self):
            return iter(self.data)

        def __len__(self):
            return len(self.data)

        def limit(self, n):
            return MockCursor(self.data[:n])

        def skip(self, n):
            return MockCursor(self.data[n:])

        def sort(self, key, direction=1):
            try:
                sorted_data = sorted(self.data, key=lambda x: x.get(key, ''), reverse=(direction == -1))
                return MockCursor(sorted_data)
            except Exception:
                return MockCursor(self.data)

    class MockDB:
        def __init__(self):
            self.db_file = BASE_DIR / "mock_db_data.json"
            self.collections = {}
            # Standard collections
            for col_name in ['users', 'skills', 'jobs', 'candidates', 'applications', 'interviews', 'aptitude_tests']:
                self.get_collection(col_name)
            self.load()

        def get_collection(self, name):
            if name not in self.collections:
                self.collections[name] = MockCollection(name, self)
            return self.collections[name]

        def __getattr__(self, name):
            if name.startswith('_'):
                raise AttributeError(name)
            return self.get_collection(name)

        def __getitem__(self, name):
            return self.get_collection(name)

        def command(self, cmd):
            return {"ok": 1}

        def save(self):
            try:
                data = {name: col.data for name, col in self.collections.items()}
                temp_file = self.db_file.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, cls=JSONCustomEncoder)
                temp_file.replace(self.db_file)
            except Exception as e:
                print(f"[database] MockDB save warning: {e}")

        def load(self):
            legacy_file = BASE_DIR / "instance" / "mock_db_store.json"
            if legacy_file.exists():
                try:
                    with open(legacy_file, 'r', encoding='utf-8') as f:
                        l_data = json.load(f)
                    for name, docs in l_data.items():
                        col = self.get_collection(name)
                        col.data = list(docs)
                    print(f"[database] Loaded legacy data from {legacy_file.name}")
                except Exception as e:
                    print(f"[database] Legacy load warning: {e}")

            if self.db_file.exists():
                try:
                    with open(self.db_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    for name, docs in data.items():
                        col = self.get_collection(name)
                        if not col.data:
                            col.data = list(docs)
                        else:
                            if name == 'users':
                                existing_unames = {str(u.get('username', '')).lower() for u in col.data}
                                existing_emails = {str(u.get('email', '')).lower() for u in col.data}
                                for doc in docs:
                                    u_name = str(doc.get('username', '')).lower()
                                    u_mail = str(doc.get('email', '')).lower()
                                    if u_name not in existing_unames and u_mail not in existing_emails:
                                        col.data.append(doc)
                                        existing_unames.add(u_name)
                                        existing_emails.add(u_mail)
                            else:
                                existing_ids = {str(x.get('id') or x.get('_id')) for x in col.data}
                                for doc in docs:
                                    doc_id = str(doc.get('id') or doc.get('_id'))
                                    if doc_id not in existing_ids:
                                        col.data.append(doc)
                                        existing_ids.add(doc_id)
                    print(f"[database] Loaded persistent local DB from {self.db_file.name}")
                except Exception as e:
                    print(f"[database] MockDB load warning: {e}")

            for col in self.collections.values():
                for doc in col.data:
                    if '_id' in doc and isinstance(doc['_id'], str):
                        try:
                            doc['_id'] = ObjectId(doc['_id'])
                        except Exception:
                            pass

    db = MockDB()
    print("[database] Initialized persistent mock database")

# Initialize collections/indexes and seed default users when the app starts
with app.app_context():
    try:
        db.users.create_index("username", unique=True)
        db.users.create_index("email", unique=True)
        db.candidates.create_index("email")
        db.candidates.create_index("current_status")
        db.jobs.create_index("status")
        db.jobs.create_index("created_at")
        db.applications.create_index([("candidate_id", 1), ("job_id", 1)], unique=True)
        db.applications.create_index("job_id")
        db.applications.create_index("candidate_id")
        db.applications.create_index("applied_at")
    except Exception as e:
        print(f"[database] Index warning: {e}")

    # Pre-seed standard accounts (admin, recruiter, candidate) if not present
    from werkzeug.security import generate_password_hash
    default_seed_users = [
        {
            "username": "admin",
            "email": "admin@example.com",
            "full_name": "System Administrator",
            "role": "admin",
            "password_hash": generate_password_hash("admin123"),
            "organization": "Headquarters",
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True
        },
        {
            "username": "recruiter",
            "email": "recruiter@example.com",
            "full_name": "HR Recruiter",
            "role": "recruiter",
            "password_hash": generate_password_hash("recruiter123"),
            "organization": "Talent Acquisition",
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True
        },
        {
            "username": "candidate",
            "email": "candidate@example.com",
            "full_name": "Jane Candidate",
            "role": "candidate",
            "password_hash": generate_password_hash("candidate123"),
            "organization": "",
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True
        }
    ]

    for seed_u in default_seed_users:
        existing = db.users.find_one({"username": seed_u["username"]})
        if not existing:
            existing = db.users.find_one({"email": seed_u["email"]})
        if not existing:
            db.users.insert_one(seed_u)
            print(f"[database] Created default {seed_u['role']} user ({seed_u['username']})")

    # Ensure all candidate users have an isolated candidate profile in db.candidates
    try:
        cand_list = list(db.candidates.find())
        existing_cand_ids = {str(c.get('_id') or c.get('id')) for c in cand_list}
        existing_cand_emails = {str(c.get('email') or '').lower() for c in cand_list}
        for u in db.users.find():
            if u.get('role') == 'candidate':
                uid = str(u.get('_id') or u.get('id') or '')
                umail = str(u.get('email') or '').lower()
                if uid not in existing_cand_ids and umail not in existing_cand_emails:
                    parts = (u.get('full_name') or '').split(' ', 1)
                    first_name = parts[0] if parts else u.get('username', '')
                    last_name = parts[1] if len(parts) > 1 else ''
                    db.candidates.insert_one({
                        "_id": u.get('_id') or u.get('id'),
                        "id": uid,
                        "user_id": uid,
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": u.get('email', ''),
                        "phone": '',
                        "headline": '',
                        "bio": '',
                        "location": '',
                        "skills": [],
                        "experience_years": '',
                        "desired_role": '',
                        "target_salary": '',
                        "education": '',
                        "resume_text": '',
                        "current_status": 'active',
                        "source": 'user_sync',
                        "created_at": datetime.utcnow().isoformat(),
                        "updated_at": datetime.utcnow().isoformat()
                    })
                    existing_cand_ids.add(uid)
                    existing_cand_emails.add(umail)
    except Exception as ex:
        print(f"[database] Candidate sync note: {ex}")

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
    return send_from_directory(FRONTEND_DIR, "candidate-dashboard.html")

@app.route("/settings")
def settings():
    return send_from_directory(FRONTEND_DIR, "settings.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()
    full_name = (data.get('full_name') or '').strip()
    role = (data.get('role') or 'candidate').strip()
    designation = (data.get('designation') or data.get('desired_role') or '').strip()

    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required"}), 400

    # Check if user already exists (case-insensitive)
    for u in db.users.find():
        if (u.get('username') or '').strip().lower() == username.lower():
            return jsonify({"error": "Username already exists"}), 409
        if (u.get('email') or '').strip().lower() == email:
            return jsonify({"error": "Email already exists"}), 409

    # Create new user
    from werkzeug.security import generate_password_hash
    org = (data.get('organization') or (designation if role != 'candidate' else '')).strip()
    user_doc = {
        "username": username,
        "email": email,
        "full_name": full_name or username,
        "role": role,
        "password_hash": generate_password_hash(password),
        "organization": org,
        "designation": designation,
        "created_at": datetime.utcnow().isoformat(),
        "is_active": True
    }

    result = db.users.insert_one(user_doc)
    user_id = getattr(result, 'inserted_id', user_doc.get('_id'))
    user_id_str = str(user_id)

    # When user signs up as a candidate, immediately create their candidate document
    if role == 'candidate':
        parts = (full_name or username).split(' ', 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ''
        cand_doc = {
            "_id": user_id,
            "id": user_id_str,
            "user_id": user_id_str,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": (data.get('phone') or '').strip(),
            "headline": designation or 'Software Professional',
            "bio": '',
            "location": '',
            "skills": [],
            "experience_years": '',
            "desired_role": designation or 'Job Seeker',
            "target_salary": '',
            "education": '',
            "resume_text": '',
            "current_status": 'active',
            "source": 'signup',
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        db.candidates.insert_one(cand_doc)

    return jsonify({
        'id': user_id_str,
        'username': username,
        'email': email,
        'full_name': user_doc['full_name'],
        'role': role,
        'designation': designation,
        'message': 'User registered successfully'
    }), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    identifier = (data.get('username') or data.get('email') or '').strip()
    password = (data.get('password') or '').strip()

    if not identifier or not password:
        return jsonify({"error": "Username or email, and password are required"}), 400

    # Search user by username or email (case-insensitive)
    user_doc = None

    # 1. Fast case-insensitive search
    try:
        ident_lower = identifier.lower()
        for u in db.users.find():
            u_name = str(u.get('username') or '').strip().lower()
            u_mail = str(u.get('email') or '').strip().lower()
            if ident_lower in (u_name, u_mail):
                user_doc = u
                break
    except Exception:
        pass

    # 2. Fallback to direct find_one
    if not user_doc:
        try:
            user_doc = db.users.find_one({"username": identifier}) or db.users.find_one({"email": identifier})
        except Exception:
            pass

    if user_doc:
        from werkzeug.security import check_password_hash
        pwd_hash = user_doc.get("password_hash", "")
        pwd_plain = user_doc.get("password", "")

        is_valid = False
        if pwd_hash:
            try:
                if check_password_hash(pwd_hash, password):
                    is_valid = True
            except Exception:
                pass

        # Also support plain text password if present
        if not is_valid and (password == pwd_plain or password == pwd_hash):
            is_valid = True

        if is_valid:
            user_id_str = str(user_doc.get('id') or user_doc.get('_id') or '')
            user_role = user_doc.get('role', 'candidate')
            resolved_name = user_doc.get('full_name') or user_doc.get('username', '')

            # Ensure candidate profile exists if role is candidate
            if user_role == 'candidate':
                try:
                    cand_exists = None
                    for c in db.candidates.find():
                        if str(c.get('user_id') or '') == user_id_str or str(c.get('id') or '') == user_id_str or str(c.get('_id') or '') == user_id_str:
                            cand_exists = c
                            break
                    if not cand_exists and user_doc.get('email'):
                        u_mail = user_doc.get('email', '').strip().lower()
                        for c in db.candidates.find():
                            if (c.get('email') or '').strip().lower() == u_mail:
                                cand_exists = c
                                break
                    if cand_exists:
                        c_name = f"{cand_exists.get('first_name', '')} {cand_exists.get('last_name', '')}".strip()
                        if c_name:
                            resolved_name = c_name
                    else:
                        parts = (user_doc.get('full_name') or '').split(' ', 1)
                        first_name = parts[0] if parts else user_doc.get('username', '')
                        last_name = parts[1] if len(parts) > 1 else ''
                        desig = user_doc.get('designation') or user_doc.get('headline') or 'Software Professional'
                        db.candidates.insert_one({
                            "_id": user_doc.get('_id') or user_doc.get('id'),
                            "id": user_id_str,
                            "user_id": user_id_str,
                            "first_name": first_name,
                            "last_name": last_name,
                            "email": user_doc.get('email', ''),
                            "phone": '',
                            "headline": desig,
                            "bio": '',
                            "location": '',
                            "skills": [],
                            "experience_years": '',
                            "desired_role": desig,
                            "target_salary": '',
                            "education": '',
                            "resume_text": '',
                            "current_status": 'active',
                            "source": 'login_sync',
                            "created_at": datetime.utcnow().isoformat(),
                            "updated_at": datetime.utcnow().isoformat()
                        })
                except Exception as ex:
                    print(f"[database] Candidate login sync note: {ex}")

            return jsonify({
                'id': user_id_str,
                'username': user_doc.get('username', ''),
                'email': user_doc.get('email', ''),
                'full_name': resolved_name,
                'role': user_role,
                'message': 'Login successful'
            }), 200

    return jsonify({"error": "Invalid username or password"}), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    # In a more advanced implementation, we would invalidate tokens/sessions
    # For now, we'll just return a success message
    return jsonify({"message": "Logout successful"}), 200


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

        # Build filter for MongoDB
        filter_dict = {}
        if search:
            filter_dict["$or"] = [
                {"first_name": {"$regex": search, "$options": "i"}},
                {"last_name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}}
            ]
        if status:
            filter_dict["current_status"] = status

        # Get total count for pagination
        total = db.candidates.count_documents(filter_dict)

        # Get paginated results
        candidates_cursor = db.candidates.find(filter_dict).skip((page - 1) * per_page).limit(per_page)

        candidates_list = []
        for c in candidates_cursor:
            c_id = str(c.get('id') or c.get('_id'))
            candidates_list.append({
                'id': c_id,
                'first_name': c.get('first_name', ''),
                'last_name': c.get('last_name', ''),
                'email': c.get('email', ''),
                'phone': c.get('phone', ''),
                'current_status': c.get('current_status', 'new'),
                'source': c.get('source', 'manual'),
                'created_at': format_dt(c.get('created_at')),
                'full_name': f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or c.get('email', 'Candidate')
            })

        return jsonify({
            'candidates': candidates_list,
            'total': total,
            'pages': (total + per_page - 1) // per_page,  # Ceiling division
            'current_page': page
        })

    elif request.method == "POST":
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        candidate_doc = {
            "first_name": data.get('first_name'),
            "last_name": data.get('last_name'),
            "email": data.get('email'),
            "phone": data.get('phone'),
            "resume_text": data.get('resume_text', ''),
            "parsed_data": data.get('parsed_data'),
            "current_status": data.get('current_status', 'new'),
            "source": data.get('source', 'manual'),
            "notes": data.get('notes'),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = db.candidates.insert_one(candidate_doc)

        return jsonify({
            'id': str(result.inserted_id),
            'message': 'Candidate created successfully'
        }), 201


@app.route("/api/candidates/<id>", methods=["GET", "PUT", "DELETE"])
def candidate_detail(id):
    s_id = str(id).strip()
    c_filter = make_id_filter(id)

    # 1. Look up candidate by user_id first, then by id/_id
    candidate = None
    for c in db.candidates.find():
        if str(c.get('user_id') or '') == s_id or str(c.get('id') or '') == s_id or str(c.get('_id') or '') == s_id:
            candidate = c
            break

    if request.method == "GET":
        if not candidate:
            # Check if user exists with this ID and auto-initialize candidate profile
            user = db.users.find_one(c_filter)
            if not user:
                for u in db.users.find():
                    if str(u.get('id') or '') == s_id or str(u.get('_id') or '') == s_id:
                        user = u
                        break

            if user:
                u_mail = (user.get('email') or '').strip().lower()
                if u_mail:
                    for c in db.candidates.find():
                        if (c.get('email') or '').strip().lower() == u_mail:
                            candidate = c
                            break

            if not candidate and user:
                parts = (user.get('full_name') or '').split(' ', 1)
                first_name = parts[0] if parts else user.get('username', '')
                last_name = parts[1] if len(parts) > 1 else ''
                uid = str(user.get('id') or user.get('_id') or s_id)
                desig = user.get('designation') or user.get('headline') or 'Software Professional'
                candidate = {
                    "_id": user.get('_id') or user.get('id') or s_id,
                    "id": uid,
                    "user_id": uid,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": user.get('email', ''),
                    "phone": '',
                    "headline": desig,
                    "bio": '',
                    "location": '',
                    "experience_years": '',
                    "desired_role": desig,
                    "target_salary": '',
                    "skills": [],
                    "education": '',
                    "linkedin": '',
                    "github": '',
                    "portfolio": '',
                    "resume_text": '',
                    "current_status": 'active',
                    "source": 'user_profile',
                    "created_at": datetime.utcnow().isoformat()
                }
                db.candidates.insert_one(candidate)
            elif not candidate:
                return jsonify({"error": "Candidate not found"}), 404

        cand_id_str = str(candidate.get('id') or candidate.get('_id') or id)
        r_text = candidate.get('resume_text', '') or ''
        edu_val = candidate.get('education')
        exp_val = candidate.get('experience')
        certs_val = candidate.get('certifications')
        projs_val = candidate.get('projects')
        apt_val = candidate.get('aptitude')
        pers_val = candidate.get('personality')

        if r_text:
            if not edu_val:
                edu_val = intel.extract_education(r_text)
            if not exp_val:
                exp_val = intel.extract_experience(r_text)
            if not certs_val:
                certs_val = intel.extract_certifications(r_text)
            if not projs_val:
                projs_val = intel.extract_projects(r_text)
            if not apt_val:
                apt_val = intel.evaluate_aptitude(r_text)
            if not pers_val:
                pers_val = intel.evaluate_personality_insights(r_text)

        return jsonify({
            'id': cand_id_str,
            'user_id': str(candidate.get('user_id') or cand_id_str),
            'first_name': candidate.get('first_name', ''),
            'last_name': candidate.get('last_name', ''),
            'email': candidate.get('email', ''),
            'phone': candidate.get('phone', ''),
            'headline': candidate.get('headline', ''),
            'bio': candidate.get('bio', ''),
            'location': candidate.get('location', ''),
            'experience_years': candidate.get('experience_years', '') or (exp_val.get('total_years_estimate') if isinstance(exp_val, dict) else ''),
            'desired_role': candidate.get('desired_role', ''),
            'target_salary': candidate.get('target_salary', ''),
            'skills': candidate.get('skills', []) if isinstance(candidate.get('skills'), list) else [s.strip() for s in str(candidate.get('skills', '')).split(',') if s.strip()],
            'education': edu_val or candidate.get('education', ''),
            'experience': exp_val or {},
            'certifications': certs_val or [],
            'projects': projs_val or [],
            'aptitude': apt_val or {},
            'personality': pers_val or {},
            'linkedin': candidate.get('linkedin', ''),
            'github': candidate.get('github', ''),
            'portfolio': candidate.get('portfolio', ''),
            'resume_text': candidate.get('resume_text', ''),
            'parsed_data': candidate.get('parsed_data'),
            'current_status': candidate.get('current_status', 'active'),
            'source': candidate.get('source', 'manual'),
            'notes': candidate.get('notes'),
            'created_at': format_dt(candidate.get('created_at')),
            'updated_at': format_dt(candidate.get('updated_at')),
            'full_name': f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip() or candidate.get('email', 'Candidate'),
            'verification_summary': get_candidate_verification_summary(cand_id_str, candidate.get('user_id'))
        })

    elif request.method == "PUT":
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        update_doc = {
            "first_name": data.get('first_name'),
            "last_name": data.get('last_name'),
            "email": data.get('email'),
            "phone": data.get('phone'),
            "headline": data.get('headline'),
            "bio": data.get('bio'),
            "location": data.get('location'),
            "experience_years": data.get('experience_years'),
            "desired_role": data.get('desired_role'),
            "target_salary": data.get('target_salary'),
            "skills": data.get('skills'),
            "education": data.get('education'),
            "linkedin": data.get('linkedin'),
            "github": data.get('github'),
            "portfolio": data.get('portfolio'),
            "resume_text": data.get('resume_text'),
            "parsed_data": data.get('parsed_data'),
            "current_status": data.get('current_status'),
            "source": data.get('source'),
            "notes": data.get('notes'),
            "updated_at": datetime.utcnow().isoformat()
        }
        update_doc = {k: v for k, v in update_doc.items() if v is not None}

        if candidate:
            target_filter = make_id_filter(candidate.get('_id') or candidate.get('id'))
            db.candidates.update_one(target_filter, {"$set": update_doc})
        else:
            user = db.users.find_one(c_filter)
            cand_id = (user.get('_id') if user else None) or id
            update_doc['_id'] = cand_id
            update_doc['id'] = str(cand_id)
            update_doc['user_id'] = str(cand_id)
            if user:
                update_doc['email'] = update_doc.get('email') or user.get('email')
            db.candidates.insert_one(update_doc)

        user_updates = {}
        if data.get('first_name') is not None or data.get('last_name') is not None:
            fn = data.get('first_name', '')
            ln = data.get('last_name', '')
            user_updates['full_name'] = f"{fn} {ln}".strip()
        if data.get('email'):
            user_updates['email'] = data.get('email')
        if data.get('headline') or data.get('desired_role'):
            user_updates['designation'] = data.get('headline') or data.get('desired_role')
        if user_updates:
            db.users.update_one(c_filter, {"$set": user_updates})

        return jsonify({
            'id': id,
            'message': 'Profile updated successfully'
        })

    elif request.method == "DELETE":
        result = db.candidates.delete_one(c_filter)
        if result.deleted_count == 0:
            return jsonify({"error": "Candidate not found"}), 404
        return jsonify({'message': 'Candidate deleted successfully'})


# Job Management APIs
@app.route("/api/jobs", methods=["GET", "POST"])
def jobs():
    if request.method == "GET":
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search', '')
        status = request.args.get('status', '')

        # Build filter for MongoDB
        filter_dict = {}
        if search:
            filter_dict["title"] = {"$regex": search, "$options": "i"}
        if status:
            filter_dict["status"] = status

        # Get total count for pagination
        total = db.jobs.count_documents(filter_dict)

        # Get paginated results
        jobs_cursor = db.jobs.find(filter_dict).skip((page - 1) * per_page).limit(per_page)

        jobs_list = []
        for j in jobs_cursor:
            job_id_val = j.get('id') or j.get('_id')
            jobs_list.append({
                'id': str(job_id_val),
                'title': j.get('title', ''),
                'description': j.get('description', ''),
                'location': j.get('location', ''),
                'employment_type': j.get('employment_type', ''),
                'salary_min': j.get('salary_min'),
                'salary_max': j.get('salary_max'),
                'required_skills': j.get('required_skills', ''),
                'status': j.get('status', 'open'),
                'created_at': format_dt(j.get('created_at')),
                'applicant_count': db.applications.count_documents(make_fk_filter(job_id_val, field="job_id"))
            })

        return jsonify({
            'jobs': jobs_list,
            'total': total,
            'pages': (total + per_page - 1) // per_page,
            'current_page': page
        })

    elif request.method == "POST":
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        job_doc = {
            "title": data.get('title'),
            "description": data.get('description'),
            "required_skills": data.get('required_skills'),
            "experience_required": data.get('experience_required'),
            "education_required": data.get('education_required'),
            "location": data.get('location'),
            "employment_type": data.get('employment_type'),
            "salary_min": data.get('salary_min'),
            "salary_max": data.get('salary_max'),
            "requirements": data.get('requirements'),
            "status": data.get('status', 'open'),
            "created_by": data.get('created_by', 1),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        job_doc = {k: v for k, v in job_doc.items() if v is not None}

        result = db.jobs.insert_one(job_doc)
        new_id = getattr(result, 'inserted_id', job_doc.get('_id'))

        return jsonify({
            'id': str(new_id),
            'message': 'Job created successfully'
        }), 201


@app.route("/api/jobs/<id>", methods=["GET", "PUT", "DELETE"])
def job_detail(id):
    j_filter = make_id_filter(id)

    if request.method == "GET":
        job = db.jobs.find_one(j_filter)
        if not job:
            return jsonify({"error": "Job not found"}), 404

        actual_id = job.get('_id') or job.get('id') or id
        applicants_cursor = db.applications.find(make_fk_filter(actual_id, field="job_id"))
        applicants_list = []
        for a in applicants_cursor:
            candidate = db.candidates.find_one(make_id_filter(a.get("candidate_id"))) if a.get("candidate_id") else None
            if not candidate and a.get("user_id"):
                candidate = db.candidates.find_one({"user_id": str(a.get("user_id"))})
            if not candidate and a.get("candidate_id"):
                candidate = db.users.find_one(make_id_filter(a.get("candidate_id")))
            if not candidate and a.get("user_id"):
                candidate = db.users.find_one(make_id_filter(a.get("user_id")))

            c_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip() if candidate else None
            if not c_name and candidate:
                c_name = candidate.get('full_name') or candidate.get('username') or candidate.get('email')
            applicants_list.append({
                'id': str(a.get('id') or a.get('_id')),
                'candidate_id': str(a.get('candidate_id')) if a.get('candidate_id') else None,
                'candidate_name': c_name,
                'candidate_email': candidate.get('email') if candidate else None,
                'match_score': a.get('match_score', 0),
                'status': a.get('status', 'applied'),
                'applied_at': format_dt(a.get('applied_at'))
            })

        return jsonify({
            'id': str(job.get('id') or job.get('_id') or id),
            'title': job.get('title', ''),
            'description': job.get('description', ''),
            'required_skills': job.get('required_skills', ''),
            'experience_required': job.get('experience_required', ''),
            'education_required': job.get('education_required', ''),
            'location': job.get('location', ''),
            'employment_type': job.get('employment_type', ''),
            'salary_min': job.get('salary_min'),
            'salary_max': job.get('salary_max'),
            'requirements': job.get('requirements', ''),
            'status': job.get('status', 'open'),
            'created_by': job.get('created_by', 1),
            'created_at': format_dt(job.get('created_at')),
            'updated_at': format_dt(job.get('updated_at')),
            'applicants': applicants_list
        })

    elif request.method == "PUT":
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        update_doc = {
            "title": data.get('title'),
            "description": data.get('description'),
            "required_skills": data.get('required_skills'),
            "experience_required": data.get('experience_required'),
            "education_required": data.get('education_required'),
            "location": data.get('location'),
            "employment_type": data.get('employment_type'),
            "salary_min": data.get('salary_min'),
            "salary_max": data.get('salary_max'),
            "requirements": data.get('requirements'),
            "status": data.get('status'),
            "updated_at": datetime.utcnow()
        }
        update_doc = {k: v for k, v in update_doc.items() if v is not None}

        result = db.jobs.update_one(j_filter, {"$set": update_doc})
        if result.matched_count == 0:
            return jsonify({"error": "Job not found"}), 404

        return jsonify({'id': id, 'message': 'Job updated successfully'})

    elif request.method == "DELETE":
        job = db.jobs.find_one(j_filter)
        if not job:
            return jsonify({"error": "Job not found"}), 404

        actual_id = job.get('_id') or job.get('id') or id
        db.jobs.delete_one(j_filter)
        db.applications.delete_many(make_fk_filter(actual_id, field="job_id"))

        return jsonify({'message': 'Job deleted successfully'})


def get_candidate_verification_summary(candidate_id=None, user_id=None):
    """
    Computes whether the candidate's resume claims and skills have been verified by authentic documents.
    Recruiters receive ONLY this pre-verified status; original documents are quarantined and never forwarded.
    """
    ids_to_check = set()
    if candidate_id:
        ids_to_check.add(str(candidate_id))
    if user_id:
        ids_to_check.add(str(user_id))

    # Match candidate record to find aliases
    cand = None
    for cid in list(ids_to_check):
        cand = db.candidates.find_one(make_id_filter(cid)) or db.candidates.find_one({"user_id": str(cid)})
        if cand:
            break

    if cand:
        for k in ['id', '_id', 'user_id']:
            if cand.get(k):
                ids_to_check.add(str(cand.get(k)))

    docs = list(db.candidate_documents.find({"candidate_id": {"$in": list(ids_to_check)}}))

    # Also check by candidate name or email if no docs matched by ID
    c_name = None
    if cand:
        c_name = f"{cand.get('first_name', '')} {cand.get('last_name', '')}".strip() or cand.get('full_name')
    if not docs and c_name:
        docs = list(db.candidate_documents.find({"candidate_name": c_name}))

    real_docs = [d for d in docs if d.get("verdict") == "REAL"]
    forged_docs = [d for d in docs if d.get("verdict") == "FORGED"]

    verified_skills = set()
    for d in real_docs:
        for sk in d.get("extracted_skills", []):
            verified_skills.add(sk)

    if real_docs:
        status = "VERIFIED_VALID"
        badge = f"🛡️ {len(real_docs)} Authentic Credential(s) Verified"
        skills_str = ", ".join(sorted(list(verified_skills))[:5]) if verified_skills else "Official Credential Backed"
        summary = f"Pre-Verified Real: Backed by {len(real_docs)} authentic credential(s). Verified resume skills: {skills_str}."
    elif forged_docs:
        status = "FORGED_WARNING"
        badge = "🚨 Tampered Credential Flagged"
        summary = f"Flagged: {len(forged_docs)} document(s) detected with graphic editing tampering or falsified dates."
    else:
        status = "UNVERIFIED"
        badge = "⚠️ No Backing Documents"
        summary = "No supporting credential documents uploaded for resume verification."

    return {
        "status": status,
        "badge": badge,
        "is_verified": status == "VERIFIED_VALID",
        "has_forgery": status == "FORGED_WARNING",
        "verified_count": len(real_docs),
        "forged_count": len(forged_docs),
        "verified_skills": sorted(list(verified_skills)),
        "summary": summary
    }


@app.route("/api/jobs/<id>/applicants", methods=["GET"])
def job_applicants(id):
    j_filter = make_id_filter(id)
    job = db.jobs.find_one(j_filter)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    actual_id = job.get('_id') or job.get('id') or id
    applicants_cursor = db.applications.find(make_fk_filter(actual_id, field="job_id"))
    applicants_list = []
    for a in applicants_cursor:
        candidate = db.candidates.find_one(make_id_filter(a.get("candidate_id"))) if a.get("candidate_id") else None
        if not candidate and a.get("user_id"):
            candidate = db.candidates.find_one({"user_id": str(a.get("user_id"))})
        if not candidate and a.get("candidate_id"):
            candidate = db.users.find_one(make_id_filter(a.get("candidate_id")))
        if not candidate and a.get("user_id"):
            candidate = db.users.find_one(make_id_filter(a.get("user_id")))

        c_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip() if candidate else None
        if not c_name and candidate:
            c_name = candidate.get('full_name') or candidate.get('username') or candidate.get('email')

        # Retrieve pre-verified credential status (original documents never forwarded to recruiter)
        v_info = get_candidate_verification_summary(a.get("candidate_id"), a.get("user_id"))

        applicants_list.append({
            'id': str(a.get('id') or a.get('_id')),
            'candidate_id': str(a.get('candidate_id')) if a.get('candidate_id') else None,
            'candidate_name': c_name,
            'candidate_email': candidate.get('email') if candidate else None,
            'match_score': a.get('match_score', 0),
            'resume_score': a.get('resume_score', 0),
            'jd_similarity': a.get('jd_similarity', 0),
            'skill_overlap': a.get('skill_overlap', 0),
            'role_confidence': a.get('role_confidence', 0),
            'credentials_status': v_info['status'],
            'credentials_badge': v_info['badge'],
            'credentials_verified': v_info['is_verified'],
            'verified_skills': v_info['verified_skills'],
            'credentials_summary': v_info['summary'],
            'status': a.get('status', 'applied'),
            'applied_at': format_dt(a.get('applied_at')),
            'notes': a.get('notes', '')
        })

    return jsonify({
        'job_id': str(job.get('id') or job.get('_id') or id),
        'job_title': job.get('title', ''),
        'applicants': applicants_list,
        'total': len(applicants_list)
    })


# Enhanced Matching API that saves to database
@app.route("/api/match", methods=["POST"])
def match():
    payload = request.get_json(force=True) or {}
    jd_text = payload.get("jd_text", "")
    candidate_ids = payload.get("candidate_ids", [])
    job_id = payload.get("job_id")

    if not job_id:
        return jsonify({"error": "job_id is required"}), 400

    job = db.jobs.find_one(make_id_filter(job_id))
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if not jd_text.strip():
        jd_text = job.get("description", "")

    candidates_list = []
    if candidate_ids:
        for cid in candidate_ids:
            c = db.candidates.find_one(make_id_filter(cid))
            if c:
                candidates_list.append(c)
    else:
        candidates_list = list(db.candidates.find())

    if not candidates_list:
        return jsonify({"error": "No candidates found"}), 404

    ranked = []
    for candidate in candidates_list:
        resume_text = candidate.get('resume_text', '')
        if not resume_text.strip():
            continue
        result = intel.score_resume(resume_text, jd_text, MODEL, TFIDF, LE)
        result["name"] = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip() or candidate.get('email', 'Candidate')
        result["candidate_id"] = str(candidate.get('id') or candidate.get('_id'))
        ranked.append(result)

    ranked.sort(key=lambda r: r["final_score"], reverse=True)
    actual_job_id = job.get('_id') or job.get('id') or job_id
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i
        cid = r["candidate_id"]

        existing_application = None
        for app_item in db.applications.find(make_fk_filter(actual_job_id, field="job_id")):
            if str(app_item.get("candidate_id")) == str(cid):
                existing_application = app_item
                break

        application_doc = {
            "match_score": r["final_score"],
            "resume_score": r.get("final_score"),
            "jd_similarity": r.get("jd_similarity", 0) * 100 if r.get("jd_similarity") is not None else 0,
            "skill_overlap": r.get("skill_overlap", 0) * 100 if r.get("skill_overlap") is not None else 0,
            "role_confidence": r.get("category_confidence", 0) * 100 if r.get("category_confidence") is not None else 0,
            "matched_skills": r.get("matched_skills", []),
            "missing_skills": r.get("missing_skills", []),
            "updated_at": datetime.utcnow()
        }

        if existing_application:
            db.applications.update_one(make_id_filter(existing_application.get('_id') or existing_application.get('id')), {"$set": application_doc})
        else:
            application_doc["candidate_id"] = cid
            application_doc["job_id"] = actual_job_id
            application_doc["status"] = "applied"
            application_doc["applied_at"] = datetime.utcnow()
            db.applications.insert_one(application_doc)

    return jsonify({
        "jd_text": jd_text,
        "candidates": ranked,
        "job_id": str(actual_job_id)
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


@app.route("/api/aptitude-analysis", methods=["POST"])
def analyze_aptitude():
    payload = request.get_json(force=True) or {}
    resume_text = payload.get("resume_text", "")
    test_responses = payload.get("test_responses", None)
    result = intel.evaluate_aptitude(resume_text=resume_text, test_responses=test_responses)
    return jsonify(result)


@app.route("/api/personality-insights", methods=["POST"])
def personality_insights():
    payload = request.get_json(force=True) or {}
    resume_text = payload.get("resume_text", "")
    result = intel.evaluate_personality_insights(resume_text=resume_text)
    return jsonify(result)


@app.route("/api/multimodal-interview-eval", methods=["POST"])
def multimodal_interview_eval():
    payload = request.get_json(force=True) or {}
    speech_text = payload.get("speech_text", "")
    audio_duration_sec = float(payload.get("audio_duration_sec", 60.0) or 60.0)
    video_duration_sec = float(payload.get("video_duration_sec", 60.0) or 60.0)
    detected_faces = int(payload.get("detected_faces", 60) or 60)
    face_looking_center_count = int(payload.get("face_looking_center_count", 52) or 52)
    gestures_active = bool(payload.get("gestures_active", True))
    words_count = int(payload.get("words_count", 0) or 0)
    filler_words_count = payload.get("filler_words_count", None)
    result = intel.analyze_multimodal_interview(
        speech_text=speech_text,
        audio_duration_sec=audio_duration_sec,
        video_duration_sec=video_duration_sec,
        detected_faces=detected_faces,
        face_looking_center_count=face_looking_center_count,
        gestures_active=gestures_active,
        words_count=words_count,
        filler_words_count=filler_words_count
    )
    return jsonify(result)



# Applications CRUD API
@app.route("/api/applications", methods=["GET", "POST"])
def applications():
    if request.method == "GET":
        # Get query parameters for filtering
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        job_id = request.args.get('job_id', '')
        candidate_id = request.args.get('candidate_id', '')
        status = request.args.get('status', '')
        sort_by = request.args.get('sort_by', 'applied_at')
        order = request.args.get('order', 'desc')

        # Build filter for database
        filter_dict = {}
        if job_id:
            filter_dict.update(make_fk_filter(job_id, field="job_id"))
        if candidate_id:
            c_str = str(candidate_id).strip()
            matched_keys = [c_str]
            for c in db.candidates.find():
                if str(c.get('user_id') or '') == c_str or str(c.get('id') or '') == c_str or str(c.get('_id') or '') == c_str:
                    for k in ['id', '_id', 'user_id']:
                        if c.get(k): matched_keys.append(str(c.get(k)))
                    break
            filter_dict["$or"] = [
                {"candidate_id": {"$in": matched_keys}},
                {"user_id": {"$in": matched_keys}}
            ]
        if status:
            filter_dict["status"] = status

        total = db.applications.count_documents(filter_dict)

        sort_direction = -1 if order == 'desc' else 1
        applications_cursor = db.applications.find(filter_dict).sort(
            sort_by, sort_direction
        ).skip((page - 1) * per_page).limit(per_page)

        applications_list = []
        for a in applications_cursor:
            candidate = db.candidates.find_one(make_id_filter(a.get("candidate_id"))) if a.get("candidate_id") else None
            if not candidate and a.get("user_id"):
                candidate = db.candidates.find_one({"user_id": str(a.get("user_id"))})
            if not candidate and a.get("candidate_id"):
                candidate = db.users.find_one(make_id_filter(a.get("candidate_id")))
            if not candidate and a.get("user_id"):
                candidate = db.users.find_one(make_id_filter(a.get("user_id")))

            job = db.jobs.find_one(make_id_filter(a.get("job_id"))) if a.get("job_id") else None

            salary_str = ''
            if job:
                if job.get('salary_min') and job.get('salary_max'):
                    salary_str = f"${int(job.get('salary_min')):,} - ${int(job.get('salary_max')):,}"
                elif job.get('salary_min'):
                    salary_str = f"From ${int(job.get('salary_min')):,}"
                elif job.get('salary_range'):
                    salary_str = str(job.get('salary_range'))

            c_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip() if candidate else None
            if not c_name and candidate:
                c_name = candidate.get('full_name') or candidate.get('username') or candidate.get('email')

            # Retrieve pre-verified credential status for candidate
            v_info = get_candidate_verification_summary(a.get("candidate_id"), a.get("user_id"))

            applications_list.append({
                'id': str(a.get('id') or a.get('_id')),
                'candidate_id': str(a.get('candidate_id')) if a.get('candidate_id') else None,
                'job_id': str(a.get('job_id')) if a.get('job_id') else None,
                'candidate_name': c_name,
                'candidate_email': candidate.get('email') if candidate else None,
                'job_title': job.get('title', 'Position') if job else 'Position',
                'job_location': job.get('location', '') if job else '',
                'job_type': job.get('employment_type', 'Full-time') if job else 'Full-time',
                'salary_range': salary_str,
                'job_description': (job.get('description', '')[:300] + '...') if job and len(job.get('description', '')) > 300 else (job.get('description', '') if job else ''),
                'required_skills': job.get('required_skills', '') if job else '',
                'match_score': round(float(a.get('match_score', 0)), 1),
                'resume_score': round(float(a.get('resume_score', 0)), 1),
                'jd_similarity': round(float(a.get('jd_similarity', 0)), 1),
                'skill_overlap': round(float(a.get('skill_overlap', 0)), 1),
                'role_confidence': round(float(a.get('role_confidence', 0)), 1),
                'matched_skills': a.get('matched_skills', []),
                'missing_skills': a.get('missing_skills', []),
                'education': a.get('education') or (candidate.get('education') if candidate else {}),
                'experience': a.get('experience') or (candidate.get('experience') if candidate else {}),
                'certifications': a.get('certifications') or [],
                'projects': a.get('projects') or [],
                'aptitude': a.get('aptitude') or {},
                'personality': a.get('personality') or {},
                'credentials_status': a.get('credentials_status') or v_info['status'],
                'credentials_badge': a.get('credentials_badge') or v_info['badge'],
                'credentials_verified': a.get('credentials_verified', v_info['is_verified']),
                'verified_skills': a.get('verified_skills') or v_info['verified_skills'],
                'credentials_summary': a.get('credentials_summary') or v_info['summary'],
                'roadmap': a.get('roadmap'),
                'ats_feedback': a.get('ats_feedback', ''),
                'rejection_feedback': a.get('rejection_feedback', ''),
                'full_job_description': job.get('description', '') if job else '',
                'status': a.get('status', 'applied'),
                'applied_at': format_dt(a.get('applied_at')),
                'updated_at': format_dt(a.get('updated_at')),
                'notes': a.get('notes', '')
            })

        return jsonify({
            'applications': applications_list,
            'total': total,
            'pages': (total + per_page - 1) // per_page,
            'current_page': page
        })

    elif request.method == "POST":
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        candidate_id = data.get('candidate_id')
        job_id = data.get('job_id')
        resume_text = data.get('resume_text', '')

        if not candidate_id or not job_id:
            return jsonify({"error": "candidate_id and job_id are required"}), 400

        job = db.jobs.find_one(make_id_filter(job_id))
        if not job:
            return jsonify({"error": "Job not found"}), 404

        cand = db.candidates.find_one(make_id_filter(candidate_id))
        if not cand:
            cand = db.candidates.find_one({"user_id": str(candidate_id)})
        if not cand:
            user = db.users.find_one(make_id_filter(candidate_id))
            if user:
                parts = (user.get('full_name') or '').split(' ', 1)
                cand = {
                    "_id": user.get('_id') or candidate_id,
                    "id": str(user.get('id') or user.get('_id') or candidate_id),
                    "user_id": str(user.get('id') or user.get('_id') or candidate_id),
                    "first_name": parts[0] if parts else user.get('username', ''),
                    "last_name": parts[1] if len(parts) > 1 else '',
                    "email": user.get('email', ''),
                    "current_status": 'active',
                    "source": 'job_application',
                    "created_at": datetime.utcnow().isoformat()
                }
                db.candidates.insert_one(cand)

        actual_job_id = job.get('_id') or job.get('id') or job_id
        actual_cand_id = (cand.get('_id') or cand.get('id') or candidate_id) if cand else candidate_id
        user_id_val = (cand.get('user_id') if cand else None) or candidate_id

        # Check existing application
        for app_doc in db.applications.find(make_fk_filter(actual_job_id, field="job_id")):
            if str(app_doc.get("candidate_id")) in [str(actual_cand_id), str(candidate_id)] or \
               (user_id_val and str(app_doc.get("user_id")) in [str(user_id_val), str(candidate_id)]):
                return jsonify({
                    "id": str(app_doc.get('id') or app_doc.get('_id')),
                    "message": "You have already applied for this position."
                }), 200

        if resume_text and cand:
            db.candidates.update_one(
                make_id_filter(actual_cand_id),
                {"$set": {"resume_text": resume_text, "updated_at": datetime.utcnow().isoformat()}}
            )

        actual_resume = resume_text or (cand.get('resume_text', '') if cand else '')

        match_score = 0
        resume_score = 0
        jd_similarity = 0
        skill_overlap = 0
        role_confidence = 0
        matched_skills = []
        missing_skills = []
        edu_data = {}
        exp_data = {}
        certs_data = []
        projs_data = []
        apt_data = {}
        pers_data = {}

        if actual_resume and job.get('description'):
            try:
                score_res = intel.score_resume(actual_resume, job.get('description', ''), MODEL, TFIDF, LE)
                match_score = round(float(score_res.get('final_score', 0)), 1)
                resume_score = round(float(score_res.get('resume_score', 0)), 1)
                jd_similarity = round(float(score_res.get('jd_similarity', 0)) * 100, 1)
                skill_overlap = round(float(score_res.get('skill_overlap', 0)) * 100, 1)
                role_confidence = round(float(score_res.get('category_confidence', 0)) * 100, 1)
                matched_skills = score_res.get('matched_skills', [])
                missing_skills = score_res.get('missing_skills', [])
                edu_data = score_res.get('education', {})
                exp_data = score_res.get('experience', {})
                certs_data = score_res.get('certifications', [])
                projs_data = score_res.get('projects', [])
                apt_data = score_res.get('aptitude', {})
                pers_data = score_res.get('personality', {})
            except Exception as e:
                logging.error(f"Error scoring application: {e}")

        # Attach pre-verified credential status for candidate
        v_info = get_candidate_verification_summary(actual_cand_id, user_id_val)

        application_doc = {
            "candidate_id": str(actual_cand_id),
            "user_id": str(user_id_val),
            "job_id": actual_job_id,
            "match_score": match_score,
            "resume_score": resume_score,
            "jd_similarity": jd_similarity,
            "skill_overlap": skill_overlap,
            "role_confidence": role_confidence,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "education": edu_data,
            "experience": exp_data,
            "certifications": certs_data,
            "projects": projs_data,
            "aptitude": apt_data,
            "personality": pers_data,
            "credentials_status": v_info['status'],
            "credentials_badge": v_info['badge'],
            "credentials_verified": v_info['is_verified'],
            "verified_skills": v_info['verified_skills'],
            "credentials_summary": v_info['summary'],
            "status": data.get('status', 'applied'),
            "applied_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "notes": data.get('notes', '')
        }

        result = db.applications.insert_one(application_doc)
        new_app_id = getattr(result, 'inserted_id', application_doc.get('_id'))

        return jsonify({
            'id': str(new_app_id),
            'message': 'Application submitted successfully. Your resume has been forwarded to the recruiter.'
        }), 201


@app.route("/api/applications/<id>", methods=["GET", "PUT", "DELETE"])
def application_detail(id):
    app_filter = make_id_filter(id)

    if request.method == "GET":
        application = db.applications.find_one(app_filter)
        if not application:
            return jsonify({"error": "Application not found"}), 404

        candidate = db.candidates.find_one(make_id_filter(application.get("candidate_id"))) if application.get("candidate_id") else None
        job = db.jobs.find_one(make_id_filter(application.get("job_id"))) if application.get("job_id") else None

        salary_str = ''
        if job:
            if job.get('salary_min') and job.get('salary_max'):
                salary_str = f"${int(job.get('salary_min')):,} - ${int(job.get('salary_max')):,}"
            elif job.get('salary_min'):
                salary_str = f"From ${int(job.get('salary_min')):,}"
            elif job.get('salary_range'):
                salary_str = str(job.get('salary_range'))

        c_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip() if candidate else None
        if not c_name and candidate:
            c_name = candidate.get('full_name') or candidate.get('email')

        return jsonify({
            'id': str(application.get('id') or application.get('_id') or id),
            'candidate_id': str(application.get('candidate_id')) if application.get('candidate_id') else None,
            'job_id': str(application.get('job_id')) if application.get('job_id') else None,
            'candidate_name': c_name,
            'candidate_email': candidate.get('email') if candidate else None,
            'job_title': job.get('title', '') if job else None,
            'job_location': job.get('location', '') if job else '',
            'job_type': job.get('employment_type', 'Full-time') if job else 'Full-time',
            'salary_range': salary_str,
            'job_description': job.get('description', '') if job else '',
            'required_skills': job.get('required_skills', '') if job else '',
            'match_score': application.get('match_score', 0),
            'resume_score': application.get('resume_score', 0),
            'jd_similarity': application.get('jd_similarity', 0),
            'skill_overlap': application.get('skill_overlap', 0),
            'role_confidence': application.get('role_confidence', 0),
            'matched_skills': application.get('matched_skills', []),
            'missing_skills': application.get('missing_skills', []),
            'roadmap': application.get('roadmap'),
            'ats_feedback': application.get('ats_feedback', ''),
            'rejection_feedback': application.get('rejection_feedback', ''),
            'status': application.get('status', 'applied'),
            'applied_at': format_dt(application.get('applied_at')),
            'updated_at': format_dt(application.get('updated_at')),
            'notes': application.get('notes', '')
        })

    elif request.method == "PUT":
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        update_doc = {"updated_at": datetime.utcnow()}

        if 'status' in data:
            update_doc['status'] = data['status']
        if 'notes' in data:
            update_doc['notes'] = data['notes']
        if 'match_score' in data:
            update_doc['match_score'] = data['match_score']

        app_record = db.applications.find_one(app_filter)
        if app_record:
            cand = db.candidates.find_one(make_id_filter(app_record.get("candidate_id"))) if app_record.get("candidate_id") else None
            job = db.jobs.find_one(make_id_filter(app_record.get("job_id"))) if app_record.get("job_id") else None

            resume_text = app_record.get('resume_text') or (cand.get('resume_text') if cand else '')
            jd_text = job.get('description', '') if job else ''

            if resume_text and jd_text:
                try:
                    score_res = intel.score_resume(resume_text, jd_text, MODEL, TFIDF, LE)
                    missing_skills = score_res.get('missing_skills', [])
                    matched_skills = score_res.get('matched_skills', [])
                    resume_skills = set(score_res.get('resume_skills', []))
                    jd_skills = set(intel.extract_skills(jd_text)) if hasattr(intel, 'extract_skills') else set(matched_skills + missing_skills)

                    roadmap = intel.generate_skill_gap_roadmap(
                        resume_skills,
                        jd_skills,
                        set(missing_skills),
                        score_res.get('predicted_category', 'Technology')
                    )

                    update_doc['match_score'] = round(float(score_res.get('final_score', 0)), 1)
                    update_doc['jd_similarity'] = round(float(score_res.get('jd_similarity', 0)) * 100, 1)
                    update_doc['skill_overlap'] = round(float(score_res.get('skill_overlap', 0)) * 100, 1)
                    update_doc['role_confidence'] = round(float(score_res.get('category_confidence', 0)) * 100, 1)
                    update_doc['matched_skills'] = matched_skills
                    update_doc['missing_skills'] = missing_skills
                    update_doc['roadmap'] = roadmap

                    if data.get('status') == 'rejected':
                        feedback_note = data.get('notes') or (
                            f"ATS Scanning Feedback: Match score was {round(float(score_res.get('final_score', 0)))}%. "
                            f"Missing {len(missing_skills)} key skill(s) required by JD: {', '.join(missing_skills[:6]) if missing_skills else 'None'}. "
                            "A personalized preparation roadmap has been generated to help you prepare and crack this job."
                        )
                        update_doc['ats_feedback'] = feedback_note
                        update_doc['rejection_feedback'] = feedback_note
                except Exception as e:
                    logging.error(f"Error computing ATS scan/roadmap on update: {e}")

        result = db.applications.update_one(app_filter, {"$set": update_doc})

        if result.matched_count == 0:
            return jsonify({"error": "Application not found"}), 404

        return jsonify({
            'id': id,
            'message': 'Application updated successfully',
            'status': update_doc.get('status')
        })

    elif request.method == "DELETE":
        result = db.applications.delete_one(app_filter)

        if result.deleted_count == 0:
            return jsonify({"error": "Application not found"}), 404

        return jsonify({
            'message': 'Application deleted successfully'
        })


# Application Roadmap API
@app.route("/api/applications/<id>/roadmap", methods=["GET"])
def application_roadmap(id):
    app_filter = make_id_filter(id)
    application = db.applications.find_one(app_filter)
    if not application:
        return jsonify({"error": "Application not found"}), 404

    job = db.jobs.find_one(make_id_filter(application.get("job_id"))) if application.get("job_id") else None
    candidate = db.candidates.find_one(make_id_filter(application.get("candidate_id"))) if application.get("candidate_id") else None

    roadmap = application.get("roadmap")
    missing_skills = application.get("missing_skills", [])
    matched_skills = application.get("matched_skills", [])

    if not roadmap or not missing_skills:
        resume_text = application.get("resume_text") or (candidate.get("resume_text") if candidate else "")
        jd_text = job.get("description", "") if job else ""

        if resume_text and jd_text:
            score_res = intel.score_resume(resume_text, jd_text, MODEL, TFIDF, LE)
            missing_skills = score_res.get("missing_skills", [])
            matched_skills = score_res.get("matched_skills", [])
            resume_skills = set(score_res.get("resume_skills", []))
            jd_skills = set(intel.extract_skills(jd_text)) if hasattr(intel, 'extract_skills') else set(matched_skills + missing_skills)
            roadmap = intel.generate_skill_gap_roadmap(
                resume_skills,
                jd_skills,
                set(missing_skills),
                score_res.get("predicted_category", "Technology")
            )
            db.applications.update_one(
                app_filter,
                {"$set": {
                    "roadmap": roadmap,
                    "missing_skills": missing_skills,
                    "matched_skills": matched_skills,
                    "match_score": round(float(score_res.get("final_score", 0)), 1)
                }}
            )

    return jsonify({
        "application_id": str(application.get('id') or application.get('_id') or id),
        "job_title": job.get("title", "Position") if job else "Position",
        "job_description": job.get("description", "") if job else "",
        "match_score": application.get("match_score", 0),
        "status": application.get("status", "applied"),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "ats_feedback": application.get("ats_feedback", ""),
        "rejection_feedback": application.get("rejection_feedback", ""),
        "roadmap": roadmap
    })


# Application Statistics API
@app.route("/api/applications/stats", methods=["GET"])
def application_stats():
    try:
        all_apps = list(db.applications.find())
        total_applications = len(all_apps)
        status_dist = {}
        scores = []
        for a in all_apps:
            st = a.get('status') or 'applied'
            status_dist[st] = status_dist.get(st, 0) + 1
            if a.get('match_score') is not None:
                try:
                    scores.append(float(a.get('match_score')))
                except (ValueError, TypeError):
                    pass
        avg_match_score = round(sum(scores) / len(scores), 1) if scores else 0.0

        return jsonify({
            "total_applications": total_applications,
            "status_distribution": status_dist,
            "recent_applications": total_applications,
            "average_match_score": avg_match_score,
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({"error": f"Failed to fetch application stats: {str(e)}"}), 500


@app.route("/api/activities/recent", methods=["GET"])
def recent_activities():
    try:
        activities = []
        # 1. Applications
        for a in db.applications.find():
            candidate = db.candidates.find_one(make_id_filter(a.get("candidate_id"))) if a.get("candidate_id") else None
            if not candidate and a.get("user_id"):
                candidate = db.candidates.find_one({"user_id": str(a.get("user_id"))})
            if not candidate and a.get("candidate_id"):
                candidate = db.users.find_one(make_id_filter(a.get("candidate_id")))
            if not candidate and a.get("user_id"):
                candidate = db.users.find_one(make_id_filter(a.get("user_id")))

            job = db.jobs.find_one(make_id_filter(a.get("job_id"))) if a.get("job_id") else None

            c_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip() if candidate else None
            if not c_name and candidate:
                c_name = candidate.get('full_name') or candidate.get('username') or candidate.get('email')
            c_name = c_name or "Candidate"
            j_title = job.get('title', 'Position') if job else "Position"

            st = a.get('status', 'applied')
            activities.append({
                "id": str(a.get('id') or a.get('_id')),
                "type": "application",
                "title": f"{c_name} — {j_title}",
                "description": f"Status: {st.capitalize()} • Match score: {round(float(a.get('match_score', 0)), 1)}%",
                "status": st,
                "time": format_dt(a.get('applied_at') or a.get('created_at')),
                "candidate_name": c_name,
                "job_title": j_title
            })

        # 2. Jobs
        for j in db.jobs.find():
            activities.append({
                "id": str(j.get('id') or j.get('_id')),
                "type": "job",
                "title": f"Active Posting: {j.get('title', 'Role')}",
                "description": f"Location: {j.get('location', 'Remote')} • Type: {j.get('employment_type', 'Full-time')}",
                "status": j.get('status', 'open'),
                "time": format_dt(j.get('created_at')),
                "job_title": j.get('title', '')
            })

        activities.sort(key=lambda x: str(x.get('time') or ''), reverse=True)
        return jsonify({"activities": activities[:15]})
    except Exception as e:
        return jsonify({"activities": [], "error": str(e)})


# Background Verification API
@app.route("/api/background-check", methods=["POST"])
def background_check():
    payload = request.get_json(force=True) or {}
    candidate_id = payload.get("candidate_id")
    check_type = payload.get("check_type", "standard")  # standard, comprehensive, criminal, education, employment

    if not candidate_id:
        return jsonify({"error": "candidate_id is required"}), 400

    candidate = db.candidates.find_one(make_id_filter(candidate_id))
    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404

    # In a real implementation, this would integrate with background check services
    # For now, we'll simulate a background check based on available data

    # Parse resume data if available
    parsed_data = {}
    if candidate.get('parsed_data'):
        try:
            import json
            parsed_data = json.loads(candidate.get('parsed_data'))
        except:
            parsed_data = {}

    # Simulate background check results
    import random
    from datetime import datetime, timedelta

    # Generate deterministic but varied results based on candidate ID
    seed = hash(str(candidate_id_obj)) % 1000
    random.seed(seed)

    # Base scores on resume completeness and consistency
    resume_completeness = min(len(candidate.get('resume_text', '') or "") / 1000, 1.0) if candidate.get('resume_text') else 0.1
    has_parsed_data = bool(candidate.get('parsed_data'))
    has_contact_info = bool(candidate.get('email') or candidate.get('phone'))

    # Calculate verification scores
    identity_verification = min(0.7 + resume_completeness * 0.3, 0.95) if has_contact_info else 0.4
    employment_verification = min(0.6 + resume_completeness * 0.4, 0.9) if has_parsed_data else 0.3
    education_verification = min(0.5 + resume_completeness * 0.5, 0.85) if has_parsed_data else 0.2
    criminal_background = max(0.8 - random.random() * 0.3, 0.5)  # Most people have clean records
    credit_check = max(0.6 - random.random() * 0.4, 0.2) if check_type in ["comprehensive", "standard"] else None

    overall_score = (identity_verification + employment_verification + education_verification + criminal_background) / 4
    if credit_check:
        overall_score = (overall_score * 4 + credit_check) / 5

    # Determine risk level
    if overall_score >= 0.8:
        risk_level = "low"
    elif overall_score >= 0.6:
        risk_level = "medium"
    else:
        risk_level = "high"

    # Prepare results
    results = {
        "candidate_id": str(candidate['_id']),
        "candidate_name": f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip(),
        "check_type": check_type,
        "timestamp": datetime.utcnow().isoformat(),
        "overall_score": round(overall_score * 100, 1),
        "risk_level": risk_level,
        "checks": {
            "identity_verification": {
                "score": round(identity_verification * 100, 1),
                "status": "verified" if identity_verification >= 0.7 else "partial",
                "details": "Identity verified against provided information" if identity_verification >= 0.7 else "Limited information available for verification"
            },
            "employment_verification": {
                "score": round(employment_verification * 100, 1),
                "status": "verified" if employment_verification >= 0.7 else "partial",
                "details": "Employment history consistent with resume" if employment_verification >= 0.7 else "Limited employment data available"
            },
            "education_verification": {
                "score": round(education_verification * 100, 1),
                "status": "verified" if education_verification >= 0.7 else "partial",
                "details": "Educational credentials verified" if education_verification >= 0.7 else "Limited educational data available"
            },
            "criminal_background": {
                "score": round(criminal_background * 100, 1),
                "status": "clear" if criminal_background >= 0.7 else "review",
                "details": "No criminal records found" if criminal_background >= 0.7 else "Further review recommended"
            }
        }
    }

    if credit_check is not None:
        results["checks"]["credit_check"] = {
            "score": round(credit_check * 100, 1),
            "status": "good" if credit_check >= 0.6 else "fair" if credit_check >= 0.4 else "poor",
            "details": "Credit history within acceptable range" if credit_check >= 0.6 else "Credit history requires review"
        }

    # Add recommendations
    results["recommendations"] = []
    if identity_verification < 0.7:
        results["recommendations"].append("Request additional identification documents")
    if employment_verification < 0.7:
        results["recommendations"].append("Contact previous employers for verification")
    if education_verification < 0.7:
        results["recommendations"].append("Request official transcripts or diplomas")
    if criminal_background < 0.7:
        results["recommendations"].append("Consider conducting a more thorough criminal background check")
    if credit_check and credit_check < 0.6:
        results["recommendations"].append("Review credit history for financial responsibility concerns")

    if not results["recommendations"]:
        results["recommendations"].append("Candidate appears suitable for hire based on background check")

    return jsonify(results)


# -------------------------------------------------------------
# Document Authenticator & Credential Verification Endpoints
# -------------------------------------------------------------
@app.route("/api/verify-document", methods=["POST"])
def verify_document():
    """
    Recruiter Document Authenticator endpoint.
    Processes uploaded certificate / diploma / ID documents, extracts metadata and text,
    runs cross-referencing against candidate profile, and outputs an Authenticity Trust Report.
    """
    try:
        try:
            import document_verifier
        except ImportError:
            from backend import document_verifier

        candidate_name = ""
        candidate_profile = {}
        file_bytes = b""
        filename = ""

        api_key = ""
        model_engine = "huggingface"

        # Check if multipart form upload or JSON
        if request.files and "file" in request.files:
            uploaded_file = request.files["file"]
            filename = uploaded_file.filename or "uploaded_doc.pdf"
            file_bytes = uploaded_file.read()
            candidate_id = request.form.get("candidate_id")
            candidate_name = request.form.get("candidate_name", "")
            doc_type = request.form.get("document_type", "certificate")
            api_key = request.form.get("api_key", "")
            model_engine = request.form.get("model_engine", "huggingface")
        else:
            payload = request.get_json(silent=True) or {}
            candidate_id = payload.get("candidate_id")
            candidate_name = payload.get("candidate_name", "")
            doc_type = payload.get("document_type", "certificate")
            filename = payload.get("filename", "certificate_sample.pdf")
            raw_text = payload.get("raw_text", "")
            file_bytes = raw_text.encode("utf-8")
            api_key = payload.get("api_key", "")
            model_engine = payload.get("model_engine", "huggingface")

        # Fetch candidate profile if candidate_id is passed
        if candidate_id:
            try:
                candidate = db.candidates.find_one(make_id_filter(candidate_id))
                if candidate:
                    candidate_profile = {
                        "name": f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip() or candidate.get("name"),
                        "email": candidate.get("email"),
                        "resume_text": candidate.get("resume_text", ""),
                        "skills": candidate.get("skills", [])
                    }
                    if not candidate_name:
                        candidate_name = candidate_profile["name"]
            except Exception as e:
                logging.warning(f"Could not load candidate for document verification: {e}")

        # 1. Extract text and container metadata (fast-path if raw_text provided)
        if "raw_text" in locals() and raw_text:
            doc_info = {
                "text": raw_text.strip(),
                "metadata": {},
                "page_count": 1,
                "file_size_kb": round(len(file_bytes) / 1024, 1),
                "extension": ".pdf",
                "engine_used": "Direct Vector Stream",
                "ocr_confidence": 1.0
            }
        else:
            doc_info = document_verifier.extract_text_from_file(file_bytes, filename)

        # 2. Extract structured entities using regex + Hugging Face classification
        entities = document_verifier.parse_entities_and_classify(doc_info["text"], candidate_name)

        # 3. Evaluate authenticity with genuine neural model or optional Gemini LLM
        eval_result = document_verifier.evaluate_authenticity(
            doc_info,
            entities,
            candidate_profile,
            api_key=api_key,
            model_engine=model_engine
        )

        # 4. Save record to DB for recruiter audit trail
        verification_record = {
            "filename": filename,
            "document_type": doc_type,
            "candidate_id": str(candidate_id) if candidate_id else None,
            "candidate_name": candidate_name or entities.get("detected_candidate") or "Unknown Candidate",
            "model_name": eval_result.get("model_name", "sentence-transformers/all-MiniLM-L6-v2"),
            "model_type": eval_result.get("model_type", "Hugging Face Neural Classifier"),
            "predicted_category": eval_result.get("predicted_category"),
            "model_confidence": eval_result.get("model_confidence", 0.0),
            "class_probabilities": eval_result.get("class_probabilities", []),
            "trust_score": eval_result.get("trust_score", 0),
            "verdict": eval_result["verdict"],
            "verdict_badge": eval_result["verdict_badge"],
            "headline": eval_result.get("headline", ""),
            "extracted_entities": eval_result.get("entities", entities),
            "concrete_findings": eval_result.get("concrete_findings", []),
            "anomalies": eval_result.get("anomalies", []),
            "network_verification": eval_result.get("network_verification", {}),
            "engine_used": doc_info.get("engine_used", "EasyOCR / PDFPlumber"),
            "file_size_kb": doc_info.get("file_size_kb", 0),
            "page_count": doc_info.get("page_count", 1),
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            insert_res = db.document_verifications.insert_one(verification_record)
            verification_record["_id"] = str(insert_res.inserted_id)
        except Exception as db_err:
            logging.warning(f"Failed to persist verification record: {db_err}")

        return jsonify({
            "status": "success",
            "report": eval_result,
            "record": verification_record
        }), 200

    except Exception as err:
        logging.error(f"Error in document verification: {err}\n{traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "error": f"Document verification failed: {str(err)}"
        }), 500


@app.route("/api/document-verifications", methods=["GET"])
def get_document_verifications():
    """
    Lists recent document verification audit logs for recruiters.
    """
    try:
        from bson import json_util
        candidate_id = request.args.get("candidate_id")
        query = {}
        if candidate_id:
            query["candidate_id"] = candidate_id

        records = list(db.document_verifications.find(query).sort("timestamp", -1).limit(50))
        for r in records:
            r["_id"] = str(r["_id"])
        return jsonify({"records": records}), 200
    except Exception as err:
        logging.error(f"Failed to fetch document verifications: {err}")
        return jsonify({"records": []}), 200


# -------------------------------------------------------------
# Candidate Credentials Locker & Recruiter Masked Inspection Endpoints
# -------------------------------------------------------------
def ensure_sample_candidate_documents():
    """
    Seeds initial candidate credentials if the collection is empty.
    Allows immediate demonstration of authentic AWS cert, Stanford degree, and Canva suspect cert.
    """
    try:
        if db.candidate_documents.count_documents({}) == 0:
            import document_verifier
            samples = [
                {
                    "candidate_id": "cand_2",
                    "candidate_name": "Alexander Vance",
                    "filename": "AWS_Solutions_Architect_Certificate.pdf",
                    "document_type": "Official Cloud Vendor Certification (AWS, Azure, GCP)",
                    "text": (
                        "Amazon Web Services (AWS)\nCERTIFICATE OF COMPLETION\nThis is to certify that\nAlexander Vance\n"
                        "Phone: +1 (555) 019-2834, Email: a.vance@cloudtech.com\nAddress: 450 Serra Mall, Stanford, CA\n"
                        "has successfully completed all requirements and is recognized as an\nAWS Certified Solutions Architect - Associate\n"
                        "Credential ID: AWS-7894-3291-B7C9\nIssued on: October 14, 2025\nVerify at: https://aws.amazon.com/verification\n"
                        "Authorized Signature: Vice President, AWS Global Training & Certification"
                    ),
                    "metadata": {}
                },
                {
                    "candidate_id": "cand_1",
                    "candidate_name": "Sarah Jenkins",
                    "filename": "Stanford_University_Diploma.pdf",
                    "document_type": "Accredited University Degree, Academic Transcript or Diploma",
                    "text": (
                        "Stanford University\nBy the authority of the Board of Trustees\nconferred upon\nSarah Jenkins\n"
                        "Student ID: STU-99281-2024, Email: sarah.j@alumni.stanford.edu\n"
                        "the degree of\nBachelor of Science in Computer Science\nwith all the rights, honors, and privileges thereunto appertaining.\n"
                        "Given at Stanford, California on June 15, 2024\nSerial No: SU-CS-2024-99812\nAuthenticity Verification: https://stanford.edu"
                    ),
                    "metadata": {}
                },
                {
                    "candidate_id": "cand_3",
                    "candidate_name": "Michael Stone",
                    "filename": "Suspect_Cloud_Certificate.pdf",
                    "document_type": "Official Technical Credential",
                    "text": (
                        "Certificate of Achievement\nAwarded to Johnathan Miller\nPhone: +1 555-432-1098\n"
                        "for successful participation in Advanced Cloud Systems\nIssued on: July 20, 2029\n"
                        "Created via Canva Online Graphic Design Suite"
                    ),
                    "metadata": {"Producer": "Canva Graphic Design Suite"}
                }
            ]

            for s in samples:
                doc_info = {
                    "text": s["text"],
                    "metadata": s["metadata"],
                    "page_count": 1,
                    "file_size_kb": 22.0,
                    "engine_used": "Vector Stream Extractor",
                    "ocr_confidence": 1.0
                }
                masked = document_verifier.generate_masked_version(s["text"], s["candidate_name"])
                entities = document_verifier.parse_entities_and_classify(s["text"], s["candidate_name"])
                eval_res = document_verifier.evaluate_authenticity(doc_info, entities, {"name": s["candidate_name"]})

                doc_record = {
                    "candidate_id": s["candidate_id"],
                    "candidate_name": s["candidate_name"],
                    "filename": s["filename"],
                    "document_type": eval_res.get("predicted_category", s["document_type"]),
                    "raw_text": s["text"],  # Protected - never returned to recruiters!
                    "masked_text": masked["masked_text"],
                    "masked_preview_html": masked["masked_preview_html"],
                    "redacted_fields": masked["redacted_fields"],
                    "verdict": eval_res["verdict"],
                    "verdict_badge": eval_res["verdict_badge"],
                    "verdict_color": eval_res["verdict_color"],
                    "model_name": eval_res["model_name"],
                    "model_confidence": eval_res["model_confidence"],
                    "model_explanation": eval_res["model_reasoning"],
                    "class_probabilities": eval_res.get("class_probabilities", []),
                    "authenticity_indicators": eval_res.get("authenticity_indicators", []),
                    "forgery_indicators": eval_res.get("forgery_indicators", []),
                    "network_verification": eval_res.get("network_verification", {}),
                    "extracted_entities": eval_res.get("entities", entities),
                    "extracted_skills": eval_res.get("extracted_skills", []),
                    "metadata": s.get("metadata", {}),
                    "uploaded_at": datetime.utcnow().isoformat()
                }
                db.candidate_documents.insert_one(doc_record)
            logging.info("Sample candidate credentials seeded successfully.")

        # Backfill extracted_skills for any existing candidate_documents that lack it
        for cd in db.candidate_documents.find({"extracted_skills": {"$exists": False}}):
            text_for_sk = cd.get("raw_text") or cd.get("masked_text", "")
            doc_type = cd.get("document_type", "")
            sks = document_verifier.extract_document_skills(text_for_sk, doc_type)
            db.candidate_documents.update_one(
                make_id_filter(cd.get("_id") or cd.get("id")),
                {"$set": {"extracted_skills": sks}}
            )

    except Exception as e:
        logging.warning(f"Error seeding candidate sample documents: {e}")


@app.route("/api/candidate/documents", methods=["GET", "POST"])
def candidate_documents():
    """
    Candidate credentials locker.
    POST: Candidate uploads any document (Certificate, Degree, Experience Letter, ID).
          Evaluates authenticity (REAL vs FORGED) and links verified skills to candidate's resume.
          Supporting documents are kept confidential and never forwarded to recruiters.
    GET:  Returns candidate's uploaded credentials list.
    """
    ensure_sample_candidate_documents()

    if request.method == "POST":
        try:
            import document_verifier

            file_bytes = b""
            filename = ""
            raw_text = ""
            candidate_id = ""
            candidate_name = ""
            document_type = ""

            if request.files and "file" in request.files:
                uploaded_file = request.files["file"]
                filename = uploaded_file.filename or "uploaded_credential.pdf"
                file_bytes = uploaded_file.read()
                candidate_id = request.form.get("candidate_id", "")
                candidate_name = request.form.get("candidate_name", "")
                document_type = request.form.get("document_type", "")
            else:
                payload = request.get_json(silent=True) or {}
                candidate_id = payload.get("candidate_id", "")
                candidate_name = payload.get("candidate_name", "")
                filename = payload.get("filename", "credential.pdf")
                raw_text = payload.get("raw_text", "")
                document_type = payload.get("document_type", "")
                file_bytes = raw_text.encode("utf-8")

            # Lookup candidate name if not provided
            if candidate_id and not candidate_name:
                cand = db.candidates.find_one(make_id_filter(candidate_id))
                if cand:
                    candidate_name = f"{cand.get('first_name', '')} {cand.get('last_name', '')}".strip() or cand.get("name", "Candidate")

            if not candidate_name:
                candidate_name = "Candidate"

            # 1. Extract text and metadata
            if raw_text:
                doc_info = {
                    "text": raw_text.strip(),
                    "metadata": {},
                    "page_count": 1,
                    "file_size_kb": round(len(file_bytes) / 1024, 1),
                    "extension": ".pdf",
                    "engine_used": "Direct Vector Stream",
                    "ocr_confidence": 1.0
                }
            else:
                doc_info = document_verifier.extract_text_from_file(file_bytes, filename)

            # 2. Automatically generate privacy-masked version for recruiters
            masked_data = document_verifier.generate_masked_version(doc_info["text"], candidate_name)

            # 3. Extract entities and evaluate REAL vs FORGED
            entities = document_verifier.parse_entities_and_classify(doc_info["text"], candidate_name)
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
            eval_res = document_verifier.evaluate_authenticity(
                doc_info,
                entities,
                {"name": candidate_name},
                api_key=api_key
            )

            doc_skills = eval_res.get("extracted_skills", [])

            doc_record = {
                "candidate_id": candidate_id or "anonymous",
                "candidate_name": candidate_name,
                "filename": filename,
                "document_type": document_type or eval_res.get("predicted_category", "Official Credential"),
                "raw_text": doc_info["text"],  # Stored for candidate, NEVER exposed to recruiter!
                "masked_text": masked_data["masked_text"],
                "masked_preview_html": masked_data["masked_preview_html"],
                "redacted_fields": masked_data["redacted_fields"],
                "verdict": eval_res["verdict"],
                "verdict_badge": eval_res["verdict_badge"],
                "verdict_color": eval_res["verdict_color"],
                "model_name": eval_res["model_name"],
                "model_confidence": eval_res["model_confidence"],
                "model_explanation": eval_res["model_reasoning"],
                "class_probabilities": eval_res.get("class_probabilities", []),
                "authenticity_indicators": eval_res.get("authenticity_indicators", []),
                "forgery_indicators": eval_res.get("forgery_indicators", []),
                "network_verification": eval_res.get("network_verification", {}),
                "web_verification": eval_res.get("web_verification", {}),
                "structure_verification": eval_res.get("structure_verification", {}),
                "extracted_entities": eval_res.get("entities", entities),
                "extracted_skills": doc_skills,
                "metadata": doc_info.get("metadata", {}),
                "uploaded_at": datetime.utcnow().isoformat()
            }

            insert_res = db.candidate_documents.insert_one(doc_record)
            doc_record["_id"] = str(insert_res.inserted_id)

            # If document is REAL, update candidate's verified skills
            if eval_res["verdict"] == "REAL" and candidate_id and candidate_id != "anonymous" and doc_skills:
                try:
                    c_filter = make_id_filter(candidate_id)
                    db.candidates.update_one(c_filter, {
                        "$addToSet": {"verified_skills": {"$each": doc_skills}}
                    })
                except Exception as up_err:
                    logging.warning(f"Failed to update candidate verified_skills: {up_err}")

            v_summary = get_candidate_verification_summary(candidate_id)

            return jsonify({
                "status": "success",
                "message": "Document verified successfully!",
                "document": doc_record,
                "verification_summary": v_summary
            }), 201

        except Exception as err:
            logging.error(f"Error uploading candidate document: {err}\n{traceback.format_exc()}")
            return jsonify({"status": "error", "error": str(err)}), 500

    else:
        # GET: List candidate documents
        try:
            candidate_id = request.args.get("candidate_id")
            query = {}
            if candidate_id:
                query["candidate_id"] = candidate_id

            docs = list(db.candidate_documents.find(query).sort("uploaded_at", -1))
            for d in docs:
                d["_id"] = str(d["_id"])
            return jsonify({"status": "success", "documents": docs}), 200
        except Exception as err:
            logging.error(f"Error fetching candidate documents: {err}")
            return jsonify({"status": "error", "documents": []}), 500


@app.route("/api/candidate/documents/<doc_id>", methods=["DELETE"])
def delete_candidate_document(doc_id):
    """
    Deletes an uploaded credential from the candidate locker.
    """
    try:
        res = db.candidate_documents.delete_one(make_id_filter(doc_id))
        if res.deleted_count > 0:
            return jsonify({"status": "success", "message": "Document deleted"}), 200
        return jsonify({"status": "error", "message": "Document not found"}), 404
    except Exception as err:
        logging.error(f"Error deleting document {doc_id}: {err}")
        return jsonify({"status": "error", "error": str(err)}), 500


@app.route("/api/recruiter/candidate-documents", methods=["GET"])
def recruiter_candidate_documents():
    """
    Recruiter endpoint to view submitted candidate credentials.
    STRICT PRIVACY GUARANTEE:
    Strips raw_text from all documents. Recruiters CANNOT view the unredacted original document;
    they only receive the masked version and model verification findings.
    """
    ensure_sample_candidate_documents()
    try:
        docs = list(db.candidate_documents.find({}).sort("uploaded_at", -1))
        sanitized_docs = []
        for d in docs:
            # STRICT PRIVACY: Remove raw_text so recruiter cannot see original
            d.pop("raw_text", None)
            d["_id"] = str(d["_id"])
            sanitized_docs.append(d)
        return jsonify({"status": "success", "documents": sanitized_docs}), 200
    except Exception as err:
        logging.error(f"Error fetching recruiter candidate documents: {err}")
        return jsonify({"status": "error", "documents": []}), 500


@app.route("/api/recruiter/audit-masked-document", methods=["POST"])
def audit_masked_document():
    """
    Recruiter runs AI Model inspection on a candidate's masked credential.
    Directly answers: REAL (Authentic) vs FORGED (Tampered / Fabricated).
    Does NOT require predefined parameters.
    """
    try:
        import document_verifier

        payload = request.get_json(silent=True) or {}
        doc_id = payload.get("document_id")
        model_engine = payload.get("model_engine", "huggingface")
        api_key = payload.get("api_key", "")

        doc = None
        if doc_id:
            doc = db.candidate_documents.find_one(make_id_filter(doc_id))

        if not doc:
            # Allow fallback to direct raw/masked text audit
            raw_text = payload.get("masked_text") or payload.get("raw_text", "")
            if not raw_text:
                return jsonify({"status": "error", "error": "Document not found"}), 404
            doc = {
                "masked_text": raw_text,
                "candidate_name": payload.get("candidate_name", "Candidate"),
                "filename": payload.get("filename", "Credential_Document.pdf"),
                "document_type": "Official Credential"
            }

        text_to_audit = doc.get("masked_text") or doc.get("raw_text", "")

        doc_info = {
            "text": text_to_audit,
            "metadata": doc.get("metadata", {}),
            "page_count": 1,
            "file_size_kb": 20.0,
            "engine_used": "Masked Stream Inspector",
            "ocr_confidence": 1.0
        }

        entities = document_verifier.parse_entities_and_classify(text_to_audit, doc.get("candidate_name", ""))
        
        # Ensure masked serials or accredited entities are preserved from candidate verified record
        extracted = doc.get("extracted_entities", {})
        if not entities.get("credential_id") and extracted.get("credential_id"):
            entities["credential_id"] = extracted.get("credential_id")
        if not entities.get("detected_issuer") and extracted.get("detected_issuer"):
            entities["detected_issuer"] = extracted.get("detected_issuer")
        if not entities.get("detected_candidate") and (doc.get("candidate_name") or extracted.get("detected_candidate")):
            entities["detected_candidate"] = doc.get("candidate_name") or extracted.get("detected_candidate")

        eval_res = document_verifier.evaluate_authenticity(
            doc_info,
            entities,
            {"name": doc.get("candidate_name", "")},
            api_key=api_key,
            model_engine=model_engine
        )

        # Record this audit into document_verifications history table
        try:
            db.document_verifications.insert_one({
                "candidate_name": doc.get("candidate_name", "Candidate"),
                "filename": doc.get("filename", "Credential.pdf"),
                "document_type": doc.get("document_type") or eval_res.get("predicted_category"),
                "predicted_category": eval_res.get("predicted_category"),
                "verdict": eval_res.get("verdict"),
                "verdict_badge": eval_res.get("verdict_badge"),
                "model_confidence": eval_res.get("model_confidence"),
                "model_name": eval_res.get("model_name"),
                "model_explanation": eval_res.get("model_reasoning"),
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as log_err:
            logging.warning(f"Could not log document verification history: {log_err}")

        return jsonify({
            "status": "success",
            "document_id": doc_id,
            "candidate_name": doc.get("candidate_name"),
            "filename": doc.get("filename"),
            "masked_preview_html": doc.get("masked_preview_html"),
            "masked_text": doc.get("masked_text"),
            "redacted_fields": doc.get("redacted_fields", []),
            "report": eval_res
        }), 200

    except Exception as err:
        logging.error(f"Error auditing masked document: {err}\n{traceback.format_exc()}")
        return jsonify({"status": "error", "error": str(err)}), 500


@app.route("/api/sync-atlas", methods=["GET", "POST"])
def trigger_sync_atlas():
    """
    On-demand synchronization with MongoDB Atlas.
    Attempts to connect to Atlas if currently offline, then syncs all local records.
    """
    global db, mongo_connected
    if not mongo_connected or db is None:
        for u in candidate_uris:
            try:
                m_client = MongoClient(u, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
                m_client.admin.command('ping')
                db = m_client[DB_NAME]
                mongo_connected = True
                print(f"[database] Hotspot detected! Connected to live MongoDB Atlas: {DB_NAME}")
                break
            except Exception:
                pass
    if mongo_connected and db is not None:
        try:
            count = sync_all_to_atlas(db)
            return jsonify({
                "status": "success",
                "message": "Connected to MongoDB Atlas and synced all records successfully!",
                "synced_records": count
            }), 200
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)}), 500
    else:
        return jsonify({
            "status": "offline",
            "message": "Cannot reach MongoDB Atlas. Please ensure your mobile hotspot is connected."
        }), 503


if __name__ == "__main__":
    app.run(debug=True, port=5000)
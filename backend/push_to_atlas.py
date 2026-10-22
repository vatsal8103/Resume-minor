"""
Push Local Database to MongoDB Atlas
Syncs all users, candidates, jobs, applications, candidate_documents, and document_verifications
from local persistent database files directly into your MongoDB Atlas cloud cluster with robust
deduplication and zero index collision.
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from pymongo import MongoClient
from bson import ObjectId

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).parent
MONGODB_URI = os.environ.get(
    'MONGODB_URI',
    'mongodb+srv://vatsalchauhan8103_db_user:jV8cUHRUlTdQP97F@cluster0.bltefbt.mongodb.net/'
)
DB_NAME = os.environ.get('DB_NAME', 'recruitment_platform')

print("=" * 65)
print("[SYNC] MONGODB ATLAS SYNCHRONIZATION TOOL")
print("=" * 65)
print(f"Target Database : {DB_NAME}")
print(f"Target Cluster  : cluster0.bltefbt.mongodb.net")
print("-" * 65)

# 1. Connect to Atlas
print("Connecting to live MongoDB Atlas...")
candidate_uris = [
    MONGODB_URI,
    "mongodb://vatsalchauhan8103_db_user:jV8cUHRUlTdQP97F@ac-tnq84jy-shard-00-00.bltefbt.mongodb.net:27017,ac-tnq84jy-shard-00-01.bltefbt.mongodb.net:27017,ac-tnq84jy-shard-00-02.bltefbt.mongodb.net:27017/recruitment_platform?ssl=true&replicaSet=atlas-tnq84j-shard-0&authSource=admin&retryWrites=true&w=majority"
]

atlas_db = None
last_err = None
for u in candidate_uris:
    try:
        client = MongoClient(
            u,
            serverSelectionTimeoutMS=8000,
            connectTimeoutMS=8000
        )
        client.admin.command('ping')
        atlas_db = client[DB_NAME]
        print("[SUCCESS] Successfully connected to live MongoDB Atlas!")
        break
    except Exception as e:
        last_err = e

if atlas_db is None:
    print("\n[FAILED] CONNECTION FAILED:")
    print(f"Error: {last_err}\n")
    print("=" * 65)
    print("WHY DID THIS HAPPEN?")
    print("Your Internet connection / Wi-Fi router dropped outbound port 27017.")
    print("Make sure your VPN (e.g. Cloudflare WARP 1.1.1.1) or Mobile Hotspot is active,")
    print("then re-run: python push_to_atlas.py")
    print("=" * 65)
    sys.exit(1)

# Helper for ObjectId conversion
def to_object_id(val):
    if isinstance(val, ObjectId):
        return val
    if isinstance(val, str) and len(val) == 24:
        try:
            return ObjectId(val)
        except Exception:
            return None
    return None

# 2. Gather data from local database files
data_sources = [
    BASE_DIR / "instance" / "mock_db_store.json",
    BASE_DIR / "mock_db_data.json"
]

collections_to_sync = [
    "users",
    "candidates",
    "jobs",
    "applications",
    "candidate_documents",
    "document_verifications",
    "skills",
    "interviews",
    "aptitude_tests"
]

merged_data = {col: {} for col in collections_to_sync}

for src in data_sources:
    if src.exists():
        try:
            with open(src, "r", encoding="utf-8") as f:
                content = json.load(f)
                for col in collections_to_sync:
                    items = content.get(col, [])
                    for item in items:
                        if col == "users":
                            key = str(item.get("username") or item.get("email") or item.get("id") or item.get("_id"))
                        elif col == "candidates":
                            key = str(item.get("user_id") or item.get("email") or item.get("id") or item.get("_id"))
                        elif col == "jobs":
                            key = str(item.get("id") or item.get("title") or item.get("_id"))
                        elif col == "applications":
                            key = f"{item.get('candidate_id')}_{item.get('job_id')}"
                        elif col == "candidate_documents":
                            fname = item.get("filename") or item.get("original_filename") or ""
                            key = f"{item.get('candidate_id')}_{fname}_{item.get('_id') or ''}"
                        elif col == "document_verifications":
                            key = str(item.get("_id") or item.get("verification_id") or item.get("id") or len(merged_data[col]))
                        else:
                            key = str(item.get("id") or item.get("_id") or len(merged_data[col]))
                        merged_data[col][key] = item
            print(f"Loaded records from: {src.name}")
        except Exception as e:
            print(f"Warning reading {src.name}: {e}")

# Also load any records from SQLite if available
sqlite_file = BASE_DIR / "instance" / "recruitment.db"
if sqlite_file.exists():
    try:
        scon = sqlite3.connect(sqlite_file)
        scon.row_factory = sqlite3.Row
        scur = scon.cursor()
        
        # User
        for row in scur.execute("SELECT * FROM user").fetchall():
            d = dict(row)
            key = str(d.get("username") or d.get("email"))
            if key not in merged_data["users"]:
                merged_data["users"][key] = d
        # Candidate
        for row in scur.execute("SELECT * FROM candidate").fetchall():
            d = dict(row)
            key = str(d.get("email") or d.get("id"))
            if key not in merged_data["candidates"]:
                merged_data["candidates"][key] = d
        # Job
        for row in scur.execute("SELECT * FROM job").fetchall():
            d = dict(row)
            key = str(d.get("id") or d.get("title"))
            if key not in merged_data["jobs"]:
                merged_data["jobs"][key] = d
        # Application
        for row in scur.execute("SELECT * FROM application").fetchall():
            d = dict(row)
            key = f"{d.get('candidate_id')}_{d.get('job_id')}"
            if key not in merged_data["applications"]:
                merged_data["applications"][key] = d

        print(f"Loaded records from SQLite: {sqlite_file.name}")
    except Exception as sq_err:
        print(f"Warning reading SQLite {sqlite_file.name}: {sq_err}")

print("-" * 65)

# 3. Upsert cleanly into MongoDB Atlas (zero DuplicateKeyErrors)
total_synced = 0
for col_name in collections_to_sync:
    records_map = merged_data[col_name]
    records = list(records_map.values())
    if not records:
        continue
    
    col = atlas_db[col_name]
    inserted = 0
    updated = 0
    
    for r in records:
        doc = dict(r)
        oid = to_object_id(doc.get("_id"))
        
        # Determine unique query filter based on collection
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
                filters.append({
                    "candidate_id": str(doc["candidate_id"]),
                    "job_id": doc["job_id"]
                })
            if doc.get("id"): filters.append({"id": doc["id"]})
            if oid: filters.append({"_id": oid})
        elif col_name == "candidate_documents":
            fname = doc.get("filename") or doc.get("original_filename")
            if doc.get("candidate_id") and fname:
                filters.append({
                    "candidate_id": str(doc["candidate_id"]),
                    "$or": [{"filename": fname}, {"original_filename": fname}]
                })
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

        # Clean document data for update
        doc_to_set = {k: v for k, v in doc.items() if k != "_id"}
        existing = col.find_one(filter_query) if filter_query else None

        if existing:
            # Preserve existing Atlas _id and update all other fields
            col.update_one({"_id": existing["_id"]}, {"$set": doc_to_set})
            updated += 1
        else:
            # Not found: insert with specified ObjectId or upsert
            if oid:
                try:
                    col.update_one({"_id": oid}, {"$set": doc_to_set}, upsert=True)
                    inserted += 1
                except Exception as up_err:
                    print(f"Notice upserting {col_name}: {up_err}")
            else:
                clean_doc = dict(doc)
                if "_id" in clean_doc:
                    del clean_doc["_id"]
                try:
                    col.insert_one(clean_doc)
                    inserted += 1
                except Exception as ins_err:
                    print(f"Skipped item in {col_name}: {ins_err}")

    total_synced += (inserted + updated)
    print(f"Collection '{col_name:23s}' -> {inserted:2d} inserted, {updated:2d} updated (Local: {len(records)})")

print("=" * 65)
print(f"[COMPLETE] Total {total_synced} documents synchronized into MongoDB Atlas.")
print(f"Open https://cloud.mongodb.com -> Browse Collections -> '{DB_NAME}' to see all your live data!")
print("=" * 65)

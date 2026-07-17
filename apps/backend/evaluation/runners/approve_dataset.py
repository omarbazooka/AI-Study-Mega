import os
import sys
import json
import csv
import argparse
import hashlib
import subprocess
from datetime import datetime, timezone
from typing import List, Dict, Any

# Add parent directory to sys.path so we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.db.repositories.chunk_repository import get_chunks_by_document
from evaluation.runners.build_golden_dataset import validate_case

def get_git_commit() -> str:
    """Gets the current git commit hash, falling back gracefully if git is not available."""
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "git-not-available"

def get_file_hash(filepath: str) -> str:
    """Calculates the SHA-256 hash of a file."""
    if not os.path.exists(filepath):
        return ""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        sha256.update(f.read())
    return sha256.hexdigest()

async def approve_dataset_async():
    parser = argparse.ArgumentParser(description="Programmatic dataset approval and versioning tool.")
    parser.add_argument("--approve-ids", type=str, help="Comma-separated Case IDs to approve (e.g. TC-001,TC-002)")
    parser.add_argument("--approve-all", action="store_true", help="Attempt to validate and approve all cases in dataset.")
    args = parser.parse_args()

    if not args.approve_ids and not args.approve_all:
        print("[APPROVE] ERROR: You must specify either --approve-ids or --approve-all.")
        sys.exit(1)

    dataset_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "datasets"))
    jsonl_path = os.path.join(dataset_dir, "golden_dataset.jsonl")
    csv_path = os.path.join(dataset_dir, "golden_dataset.csv")
    report_path = os.path.join(dataset_dir, "dataset_validation_report.json")
    manifest_path = os.path.join(dataset_dir, "document_manifest.json")
    metadata_path = os.path.join(dataset_dir, "frozen_metadata.json")

    if not os.path.exists(jsonl_path):
        print(f"[APPROVE] ERROR: Dataset file '{jsonl_path}' not found. Run build_golden_dataset.py first.")
        sys.exit(1)

    # 1. Load manifest and database chunks to validate
    if not os.path.exists(manifest_path):
        print(f"[APPROVE] ERROR: Manifest file '{manifest_path}' not found.")
        sys.exit(1)
        
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    print("[APPROVE] Fetching document chunks from DB for validation...")
    manifest_chunks = {}
    for doc in manifest.values():
        doc_id = doc["document_id"]
        filename = doc["filename"]
        chunks = await get_chunks_by_document(doc_id)
        manifest_chunks[filename] = chunks or []

    # 2. Read dataset cases
    print("[APPROVE] Loading golden dataset cases...")
    cases: List[Dict[str, Any]] = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))

    # Parse targeted IDs
    target_ids = []
    if args.approve_ids:
        target_ids = [cid.strip() for cid in args.approve_ids.split(",") if cid.strip()]

    # 3. Update review status with strict validations
    approved_count = 0
    pending_count = 0
    
    for c in cases:
        cid = c["test_case_id"]
        should_approve = (args.approve_all) or (cid in target_ids)
        
        if should_approve:
            # Re-run strict validation before changing status
            is_valid, reason = validate_case(c, manifest_chunks)
            if not is_valid:
                print(f"[APPROVE] ERROR: Case {cid} is invalid: {reason}. Cannot approve placeholders or malformed cases.")
                sys.exit(1)
                
            c["review_status"] = "approved"
            approved_count += 1
        else:
            if c["review_status"] == "approved":
                approved_count += 1
            else:
                pending_count += 1

    # 4. Save updated dataset to JSONL
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
            
    # Save to CSV
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "test_case_id", "document_id", "document_filename", "document_hash",
            "question", "language", "category", "difficulty", "answerable",
            "expected_behavior", "reference_answer", "required_facts", "reference_page_numbers",
            "reference_chunk_ids", "cross_lingual", "review_status", "generation_notes"
        ])
        writer.writeheader()
        for c in cases:
            row = {k: v for k, v in c.items() if k in writer.fieldnames}
            row["required_facts"] = json.dumps(row["required_facts"], ensure_ascii=False)
            row["reference_page_numbers"] = json.dumps(row["reference_page_numbers"])
            row["reference_chunk_ids"] = json.dumps(row["reference_chunk_ids"])
            writer.writerow(row)

    # 5. Update validation report
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
        report["review_status_counts"] = {
            "pending": pending_count,
            "approved": approved_count,
            "rejected": 0
        }
        report["validation_timestamp"] = datetime.now(timezone.utc).isoformat()
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"[APPROVE] Progress saved. Total Approved: {approved_count}/30")

    # 6. Freeze and Lock versioning metadata if and only if exactly 30 cases are approved
    if approved_count == 30:
        print("[APPROVE] Exactly 30 valid cases approved! Compiling versioning freeze-lock metadata...")
        
        # Calculate hashes
        dataset_hash = get_file_hash(jsonl_path)
        manifest_hash = get_file_hash(manifest_path)
        git_commit = get_git_commit()
        
        meta = {
            "dataset_name": "Source-Verified Synthetic Golden Dataset",
            "dataset_sha256": dataset_hash,
            "document_set_hash": manifest_hash,
            "freeze_timestamp": datetime.now(timezone.utc).isoformat(),
            "git_commit": git_commit,
            "prompt_version": "v1.0",
            "approved_case_ids": [c["test_case_id"] for c in cases]
        }
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
            
        print(f"[APPROVE] SUCCESS: Dataset version frozen and locked! Metadata saved to: {metadata_path}")
    else:
        # If not fully approved, remove the frozen metadata to prevent invalid execution runs
        if os.path.exists(metadata_path):
            os.remove(metadata_path)
        print("[APPROVE] Warning: Dataset not fully approved (30 approved cases required to freeze). Freeze lock removed.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(approve_dataset_async())

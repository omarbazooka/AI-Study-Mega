"""
Deep investigation: nine RETRIEVAL_EMPTY answerable cases.
Checks Supabase for document ownership, chunk count, embedding dimension.
Zero-LLM. Writes CSV + MD report.
"""
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BACKEND = r"c:\Users\omara\OneDrive\Desktop\Machine Leraning DEPI\Mega Project\NHA-4-094\apps\backend"
sys.path.insert(0, BACKEND)

from dotenv import load_dotenv
load_dotenv(os.path.join(BACKEND, ".env"))

import pandas as pd
from supabase import create_client

GOLDEN_PATH = os.path.join(BACKEND, "evaluation", "datasets", "golden_dataset.jsonl")
FA_PATH     = os.path.join(BACKEND, "evaluation", "results", "diagnostics", "false_refusal_case_analysis.csv")
RAW_PATH    = os.path.join(BACKEND, "evaluation", "results", "raw", "pipeline_outputs.jsonl")
OUT_CSV     = os.path.join(BACKEND, "evaluation", "results", "diagnostics", "retrieval_empty_investigation.csv")
OUT_MD      = os.path.join(BACKEND, "evaluation", "results", "diagnostics", "retrieval_empty_investigation.md")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
EVAL_USER_ID = "dc803d72-f5d6-46e2-82a9-5c32bcda2815"

# ── load golden ──────────────────────────────────────────────────────────────
golden = {}
with open(GOLDEN_PATH, encoding="utf-8") as f:
    for line in f:
        if line.strip():
            c = json.loads(line)
            golden[c["test_case_id"]] = c

# ── load pipeline cache ──────────────────────────────────────────────────────
raw_cache = {}
with open(RAW_PATH, encoding="utf-8") as f:
    for line in f:
        if line.strip():
            d = json.loads(line)
            raw_cache[d["test_case_id"]] = d

# ── RETRIEVAL_EMPTY cases ────────────────────────────────────────────────────
fa_df = pd.read_csv(FA_PATH)
empty_ids = fa_df[fa_df["root_cause_classification"] == "RETRIEVAL_EMPTY"]["test_case_id"].tolist()

print(f"Investigating {len(empty_ids)} RETRIEVAL_EMPTY cases...\n")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set in environment.")
    sys.exit(1)

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

rows = []
for cid in empty_ids:
    g = golden.get(cid, {})
    doc_id      = g.get("document_id", "")
    filename    = g.get("document_filename", "")
    category    = g.get("category", "")
    lang        = g.get("language", "")
    answerable  = g.get("answerable", False)

    # What doc_id actually reached the retriever (from cache)
    cached = raw_cache.get(cid)
    doc_id_in_run  = cached.get("document_id", "NOT_IN_CACHE") if cached else "NOT_IN_CACHE"
    chunks_in_run  = len(cached.get("retrieved_chunk_ids") or []) if cached else 0
    answer_in_run  = (cached.get("actual_answer") or "")[:80] if cached else ""

    # ── Supabase: document record ────────────────────────────────────────────
    doc_resp    = sb.table("documents").select(
        "id,user_id,upload_status,original_filename,page_count,chunk_count,error_message"
    ).eq("id", doc_id).execute()
    doc_records = doc_resp.data or []

    doc_exists    = len(doc_records) > 0
    doc_record    = doc_records[0] if doc_records else {}
    doc_owned     = doc_record.get("user_id") == EVAL_USER_ID if doc_records else False
    doc_status    = doc_record.get("upload_status", "N/A")
    db_page_count = doc_record.get("page_count", 0) or 0
    db_chunk_count_from_doc = doc_record.get("chunk_count", 0) or 0
    db_error      = doc_record.get("error_message") or ""
    db_orig_name  = doc_record.get("original_filename", "")

    # ── Supabase: actual chunk count ─────────────────────────────────────────
    chunk_resp  = (sb.table("document_chunks")
                   .select("id", count="exact")
                   .eq("document_id", doc_id)
                   .execute())
    actual_chunk_count = chunk_resp.count or 0

    # ── Supabase: embedding sample ───────────────────────────────────────────
    emb_resp    = (sb.table("document_chunks")
                   .select("id,embedding,user_id")
                   .eq("document_id", doc_id)
                   .limit(3)
                   .execute())
    emb_samples = emb_resp.data or []
    has_embeddings = any(r.get("embedding") is not None for r in emb_samples)
    emb_dim        = len(emb_samples[0]["embedding"]) if emb_samples and emb_samples[0].get("embedding") else 0
    chunk_user_id  = emb_samples[0].get("user_id", "") if emb_samples else ""
    chunk_owned    = chunk_user_id == EVAL_USER_ID if emb_samples else False

    # ── Root cause ───────────────────────────────────────────────────────────
    if not doc_exists:
        root_cause = "DOCUMENT_NOT_IN_DB"
    elif not doc_owned:
        root_cause = "DOCUMENT_WRONG_USER"
    elif doc_status != "ready":
        root_cause = f"DOC_STATUS_{doc_status.upper()}"
    elif actual_chunk_count == 0:
        root_cause = "NO_CHUNKS_IN_DB"
    elif not has_embeddings:
        root_cause = "CHUNKS_MISSING_EMBEDDINGS"
    elif doc_id_in_run not in ("NOT_IN_CACHE", doc_id):
        root_cause = "WRONG_DOC_ID_TO_RETRIEVER"
    elif doc_id_in_run == "NOT_IN_CACHE":
        root_cause = "PIPELINE_RUN_MISSING_FROM_CACHE"
    elif chunks_in_run == 0:
        root_cause = "RETRIEVER_RETURNED_ZERO"
    else:
        root_cause = "UNKNOWN"

    row = dict(
        test_case_id         = cid,
        language             = lang,
        category             = category,
        answerable           = answerable,
        expected_filename    = filename,
        db_filename          = db_orig_name,
        document_id          = doc_id,
        doc_exists           = doc_exists,
        doc_owned_by_eval    = doc_owned,
        upload_status        = doc_status,
        db_page_count        = db_page_count,
        doc_chunk_count_col  = db_chunk_count_from_doc,
        actual_chunk_count   = actual_chunk_count,
        has_embeddings       = has_embeddings,
        embedding_dim        = emb_dim,
        chunk_owned_by_eval  = chunk_owned,
        doc_id_in_run        = doc_id_in_run,
        retriever_returned   = chunks_in_run,
        db_error             = db_error,
        root_cause           = root_cause,
    )
    rows.append(row)
    print(f"  {cid}: exists={doc_exists}, owned={doc_owned}, status={doc_status!r}, "
          f"chunks={actual_chunk_count}, emb={has_embeddings}({emb_dim}d), "
          f"retriever={chunks_in_run} → {root_cause}")

# ── Write CSV ────────────────────────────────────────────────────────────────
df_out = pd.DataFrame(rows)
df_out.to_csv(OUT_CSV, index=False, encoding="utf-8")

# ── Write MD ─────────────────────────────────────────────────────────────────
from collections import Counter
causes = Counter(r["root_cause"] for r in rows)

with open(OUT_MD, "w", encoding="utf-8") as f:
    f.write("# RETRIEVAL_EMPTY Answerable Case Investigation\n\n")
    f.write(f"**Evaluation user ID**: `{EVAL_USER_ID}`  \n")
    f.write(f"**Cases investigated**: {len(rows)}\n\n")

    f.write("## Per-Case Findings\n\n")
    f.write("| Case | Lang | Category | Exists | Owned | Status | Chunks (DB) | Embeddings | Dim | Retriever→0 | Root Cause |\n")
    f.write("|---|---|---|---|---|---|---|---|---|---|---|\n")
    for r in rows:
        f.write(
            f"| `{r['test_case_id']}` | {r['language']} | {r['category']} | "
            f"{'✓' if r['doc_exists'] else '**✗ MISSING**'} | "
            f"{'✓' if r['doc_owned_by_eval'] else '**✗ WRONG USER**'} | "
            f"`{r['upload_status']}` | {r['actual_chunk_count']} | "
            f"{'✓' if r['has_embeddings'] else '**✗ NONE**'} | "
            f"{r['embedding_dim']} | "
            f"{'**YES**' if r['retriever_returned'] == 0 else r['retriever_returned']} | "
            f"`{r['root_cause']}` |\n"
        )

    f.write("\n## Root Cause Summary\n\n")
    for cause, cnt in causes.most_common():
        f.write(f"- **{cause}**: {cnt} case(s)\n")

    f.write("\n## Required Remediation Actions\n\n")
    for r in rows:
        rc = r["root_cause"]
        cid = r["test_case_id"]
        if rc == "DOCUMENT_NOT_IN_DB":
            f.write(f"- `{cid}`: **Re-upload** `{r['expected_filename']}` for eval user `{EVAL_USER_ID}`.\n")
        elif rc == "DOCUMENT_WRONG_USER":
            f.write(f"- `{cid}`: Document `{r['document_id']}` owned by wrong user. "
                    f"Re-upload as eval user or update `user_id`.\n")
        elif rc.startswith("DOC_STATUS_"):
            f.write(f"- `{cid}`: Upload status `{r['upload_status']}`. "
                    f"Re-trigger ingestion pipeline for doc `{r['document_id']}`.\n")
        elif rc == "NO_CHUNKS_IN_DB":
            f.write(f"- `{cid}`: No chunks found. Re-run chunker for doc `{r['document_id']}`.\n")
        elif rc == "CHUNKS_MISSING_EMBEDDINGS":
            f.write(f"- `{cid}`: Chunks exist but embeddings are null. "
                    f"Re-run embedding job for doc `{r['document_id']}`.\n")
        elif rc == "WRONG_DOC_ID_TO_RETRIEVER":
            f.write(f"- `{cid}`: Pipeline sent wrong doc_id `{r['doc_id_in_run']}` "
                    f"instead of `{r['document_id']}`. Debug PipelineState propagation.\n")
        elif rc == "PIPELINE_RUN_MISSING_FROM_CACHE":
            f.write(f"- `{cid}`: No cached run found for this case. Must re-run pipeline.\n")
        elif rc == "RETRIEVER_RETURNED_ZERO":
            f.write(f"- `{cid}`: Doc + chunks + embeddings exist but retriever returned 0 results. "
                    f"Investigate similarity threshold, RLS, or query normalisation.\n")

print(f"\nDone. Reports:\n  {OUT_CSV}\n  {OUT_MD}")

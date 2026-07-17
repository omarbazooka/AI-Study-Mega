import os
import sys
import json
import csv
import random
import asyncio
from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone
import hashlib

# Add parent directory to sys.path so we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Reconfigure stdout/stderr to utf-8 to prevent charmap/CP1252 errors on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from app.core.config import settings
from app.db.repositories.chunk_repository import get_chunks_by_document
from app.ai_system.services.llm.generate import generate as llm_generate
from app.ai_system.services.llm.schemas import LLMEngineerPayload, ExpectedLLMOutputFormat, SourceInfo, StrictGroundingPolicy, ChunkContext
from app.ai_system.providers.embedding_client import EmbeddingClient
from evaluation.runners.auth_helper import authenticate_evaluation_user

# Random seed for reproducibility
random.seed(42)

# Cosine similarity helper
def dot_product(a, b):
    return sum(x * y for x, y in zip(a, b))

def magnitude(a):
    return sum(x * x for x in a) ** 0.5

def cosine_similarity(a, b):
    mag_a = magnitude(a)
    mag_b = magnitude(b)
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot_product(a, b) / (mag_a * mag_b)

def get_jaccard_similarity(q1: str, q2: str) -> float:
    import re
    words1 = set(re.findall(r'\w+', q1.lower()))
    words2 = set(re.findall(r'\w+', q2.lower()))
    if not words1 or not words2:
        return 0.0
    return len(words1 & words2) / len(words1 | words2)

def get_semantic_similarity(q1: str, q2: str) -> float:
    """Computes similarity using BGE-M3 embedding client, falling back to Jaccard similarity."""
    try:
        client = EmbeddingClient()
        embeddings = client.embed_texts([q1, q2])
        if len(embeddings) == 2:
            return cosine_similarity(embeddings[0], embeddings[1])
    except Exception as e:
        pass
    
    # Fallback to Jaccard
    return get_jaccard_similarity(q1, q2)

def validate_case(c: Dict[str, Any], manifest_chunks: Dict[str, List[Dict[str, Any]]]) -> Tuple[bool, str]:
    """Strictly validates a single test case against all formatting and database constraints."""
    q = c.get("question", "").strip()
    ans = c.get("reference_answer")
    notes = c.get("generation_notes", "")
    
    if not q:
        return False, "Empty question"
        
    # 1. No placeholders
    placeholders = ["template fallback", "احتياطي", "question about", "reference answer for", "generic placeholder"]
    for p in placeholders:
        if p in q.lower() or (ans and p in ans.lower()) or p in notes.lower():
            return False, f"Contains placeholder phrase: '{p}'"
            
    # 2. Check document chunks exist in DB
    doc_name = c.get("document_filename")
    if doc_name not in manifest_chunks:
        return False, f"Document '{doc_name}' not found in manifest chunks"
        
    doc_chunks = manifest_chunks[doc_name]
    doc_chunk_ids = {str(ch.get("id") or ch.get("chunk_id")) for ch in doc_chunks}
    
    ref_chunks = c.get("reference_chunk_ids", [])
    if c.get("answerable"):
        if not ref_chunks:
            return False, "Answerable case has no reference chunk IDs"
        for cid in ref_chunks:
            if cid not in doc_chunk_ids:
                return False, f"Reference chunk ID '{cid}' does not exist in DB for document '{doc_name}'"
    else:
        if ref_chunks:
            return False, "Unanswerable case should not have reference chunk IDs"
            
    # 3. Category specific validation
    cat = c.get("category")
    if cat == "multi_chunk" and len(ref_chunks) < 2:
        return False, f"Multi-chunk case contains {len(ref_chunks)} chunks (requires at least 2)"
        
    if cat == "unanswerable":
        if ans is not None:
            return False, "Unanswerable case has non-null reference answer"
        if c.get("expected_behavior") != "fallback":
            return False, "Unanswerable case expected behavior must be 'fallback'"
        if not c.get("unanswerable_rationale"):
            return False, "Unanswerable case is missing 'unanswerable_rationale'"
    else:
        if not ans:
            return False, f"Answerable case '{cat}' is missing reference answer"
        if not c.get("required_facts"):
            return False, f"Answerable case '{cat}' is missing required facts"
            
    # 4. Standalone, natural question formatting (no Generation context)
    avoid_phrases = ["according to the snippet", "according to the passage", "according to the excerpts", "in the snippet", "في هذا المقتطف", "وفقاً للمقتطف"]
    for phrase in avoid_phrases:
        if phrase in q.lower():
            return False, f"Wording violation: contains generation metadata context phrase '{phrase}'"
            
    return True, "Valid"

async def generate_candidates():
    print("[DATASET] Starting golden dataset generation...")
    
    # 1. Load document manifest
    manifest_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "datasets", "document_manifest.json"))
    if not os.path.exists(manifest_path):
        print(f"[DATASET] ERROR: Manifest file '{manifest_path}' does not exist. Run document ingestion first.")
        sys.exit(1)
        
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    if len(manifest) != 3:
        print(f"[DATASET] ERROR: Expected exactly 3 documents in manifest, but found {len(manifest)}.")
        sys.exit(1)
        
    # Authenticate evaluation user (respects RLS)
    try:
        user_id, _ = authenticate_evaluation_user()
    except Exception as e:
        print(f"[DATASET] ERROR: Authentication failed: {e}")
        sys.exit(1)

    # 2. Load all chunks from Supabase DB to validate presence
    print("[DATASET] Fetching and caching document chunks from DB...")
    manifest_chunks = {}
    for doc in manifest.values():
        doc_id = doc["document_id"]
        filename = doc["filename"]
        chunks = await get_chunks_by_document(doc_id)
        manifest_chunks[filename] = chunks or []
        print(f"[DATASET] Cached {len(manifest_chunks[filename])} chunks for {filename}.")

    # 3. Load configuration budget parameters
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "evaluation.yaml"))
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    budget_limit = config["budget"]["max_dataset_generation_calls"]
    
    # 4. Load existing golden dataset (Resume/Cache)
    dataset_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "datasets"))
    jsonl_path = os.path.join(dataset_dir, "golden_dataset.jsonl")
    
    existing_valid_cases = []
    if os.path.exists(jsonl_path):
        print(f"[DATASET] Found existing dataset at {jsonl_path}. Validating cases...")
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        c = json.loads(line)
                        is_valid, reason = validate_case(c, manifest_chunks)
                        if is_valid:
                            existing_valid_cases.append(c)
                        else:
                            print(f"[DATASET] Warning: Discarding invalid cached case {c.get('test_case_id')}: {reason}")
                    except Exception as e:
                        print(f"[DATASET] Warning: Failed to parse cached line: {e}")
                        
        print(f"[DATASET] Loaded {len(existing_valid_cases)} valid cached cases.")
        
    # 5. Define generation plan
    generation_plan = [
        # Arabic Document 2.pdf (10 cases - AR)
        {"filename": "Arabic Document 2.pdf", "category": "direct_factual", "lang": "ar", "difficulty": "easy"},
        {"filename": "Arabic Document 2.pdf", "category": "direct_factual", "lang": "ar", "difficulty": "medium"},
        {"filename": "Arabic Document 2.pdf", "category": "direct_factual", "lang": "ar", "difficulty": "hard"},
        {"filename": "Arabic Document 2.pdf", "category": "explanation", "lang": "ar", "difficulty": "medium"},
        {"filename": "Arabic Document 2.pdf", "category": "explanation", "lang": "ar", "difficulty": "hard"},
        {"filename": "Arabic Document 2.pdf", "category": "multi_chunk", "lang": "ar", "difficulty": "medium"},
        {"filename": "Arabic Document 2.pdf", "category": "multi_chunk", "lang": "ar", "difficulty": "hard"},
        {"filename": "Arabic Document 2.pdf", "category": "comparison", "lang": "ar", "difficulty": "medium"},
        {"filename": "Arabic Document 2.pdf", "category": "summary", "lang": "ar", "difficulty": "medium"},
        {"filename": "Arabic Document 2.pdf", "category": "unanswerable", "lang": "ar", "difficulty": "easy"},
        
        # English Document 1.pdf (10 cases - EN)
        {"filename": "English Document 1.pdf", "category": "direct_factual", "lang": "en", "difficulty": "easy"},
        {"filename": "English Document 1.pdf", "category": "direct_factual", "lang": "en", "difficulty": "medium"},
        {"filename": "English Document 1.pdf", "category": "direct_factual", "lang": "en", "difficulty": "hard"},
        {"filename": "English Document 1.pdf", "category": "explanation", "lang": "en", "difficulty": "medium"},
        {"filename": "English Document 1.pdf", "category": "explanation", "lang": "en", "difficulty": "hard"},
        {"filename": "English Document 1.pdf", "category": "multi_chunk", "lang": "en", "difficulty": "medium"},
        {"filename": "English Document 1.pdf", "category": "multi_chunk", "lang": "en", "difficulty": "hard"},
        {"filename": "English Document 1.pdf", "category": "comparison", "lang": "en", "difficulty": "medium"},
        {"filename": "English Document 1.pdf", "category": "summary", "lang": "en", "difficulty": "medium"},
        {"filename": "English Document 1.pdf", "category": "unanswerable", "lang": "en", "difficulty": "easy"},
        
        # Document 3 Advanced.pdf (10 cases - EN & Cross-lingual AR)
        {"filename": "Document 3 Advanced.pdf", "category": "direct_factual", "lang": "en", "difficulty": "easy"},
        {"filename": "Document 3 Advanced.pdf", "category": "direct_factual", "lang": "en", "difficulty": "medium"},
        {"filename": "Document 3 Advanced.pdf", "category": "direct_factual", "lang": "ar", "difficulty": "hard", "cross_lingual": True},
        {"filename": "Document 3 Advanced.pdf", "category": "explanation", "lang": "en", "difficulty": "medium"},
        {"filename": "Document 3 Advanced.pdf", "category": "explanation", "lang": "ar", "difficulty": "hard", "cross_lingual": True},
        {"filename": "Document 3 Advanced.pdf", "category": "multi_chunk", "lang": "en", "difficulty": "medium"},
        {"filename": "Document 3 Advanced.pdf", "category": "multi_chunk", "lang": "en", "difficulty": "hard"},
        {"filename": "Document 3 Advanced.pdf", "category": "comparison", "lang": "en", "difficulty": "medium"},
        {"filename": "Document 3 Advanced.pdf", "category": "summary", "lang": "en", "difficulty": "medium"},
        {"filename": "Document 3 Advanced.pdf", "category": "unanswerable", "lang": "ar", "difficulty": "easy", "cross_lingual": True}
    ]

    # Map existing cases by plan criteria
    final_cases = []
    remaining_plan = []
    
    # Matching existing cached cases to plan
    for plan in generation_plan:
        matched = None
        for ec in existing_valid_cases:
            if (ec["document_filename"] == plan["filename"] and
                ec["category"] == plan["category"] and
                ec["language"] == plan["lang"] and
                ec["difficulty"] == plan["difficulty"] and
                ec.get("cross_lingual", False) == plan.get("cross_lingual", False)):
                matched = ec
                existing_valid_cases.remove(ec)
                break
        if matched:
            final_cases.append(matched)
        else:
            remaining_plan.append(plan)
            
    print(f"[DATASET] Reusing {len(final_cases)} valid cached cases. Need to generate {len(remaining_plan)} new cases.")

    # 6. Generation Loop
    generation_calls_count = 0
    
    for plan in remaining_plan:
        filename = plan["filename"]
        category = plan["category"]
        lang = plan["lang"]
        difficulty = plan["difficulty"]
        cross_lingual = plan.get("cross_lingual", False)
        
        doc_meta = manifest[filename]
        doc_id = doc_meta["document_id"]
        doc_hash = doc_meta["file_hash"]
        
        chunks = manifest_chunks[filename]
        if not chunks:
            print(f"[DATASET] Skipping generation for empty document: {filename}")
            continue
            
        success = False
        attempts_per_case = 3
        
        for attempt in range(1, attempts_per_case + 1):
            if generation_calls_count >= budget_limit:
                print(f"[DATASET] ERROR: Generation budget limit ({budget_limit}) reached. Saving progress and aborting.")
                save_current_dataset(final_cases, manifest_chunks)
                sys.exit(1)
                
            # Select source chunks based on category heuristics
            selected_chunks = []
            if category == "multi_chunk":
                if len(chunks) >= 3:
                    idx1 = random.randint(0, len(chunks) - 3)
                    idx2 = idx1 + 2
                    selected_chunks = [chunks[idx1], chunks[idx2]]
                else:
                    selected_chunks = [chunks[0], chunks[min(1, len(chunks)-1)]]
            elif category == "comparison":
                comp_keywords = ["compare", "comparison", "versus", "vs", "feature", "table", "difference", "مقارنة", "الفرق", "جدول", "مقابل"]
                matching = [c for c in chunks if any(k in c.get("content", "").lower() for k in comp_keywords)]
                if matching:
                    selected_chunks = [random.choice(matching)]
                else:
                    selected_chunks = [random.choice(chunks)]
            elif category == "summary":
                sum_keywords = ["summary", "conclusion", "overview", "key concept", "abstract", "ملخص", "خلاصة", "خاتمة"]
                matching = [c for c in chunks if any(k in c.get("content", "").lower() for k in sum_keywords)]
                if matching:
                    selected_chunks = [random.choice(matching)]
                else:
                    selected_chunks = [random.choice(chunks)]
            else:
                idx = random.randint(0, len(chunks) - 1)
                selected_chunks = [chunks[idx]]
                
            chunk_ids = [str(c.get("id") or c.get("chunk_id")) for c in selected_chunks]
            chunk_contents = [c.get("content") for c in selected_chunks]
            
            page_numbers = []
            for c in selected_chunks:
                p_start = c.get("page_start") or c.get("page_number") or 1
                if p_start not in page_numbers:
                    page_numbers.append(p_start)
            page_numbers.sort()
            
            # Format existing questions to avoid duplication
            existing_qs_list = [c["question"] for c in final_cases]
            existing_qs_text = ""
            if existing_qs_list:
                existing_qs_text = "\nAlready generated questions in dataset (you MUST NOT generate any question similar to these in topic/concept):\n" + "\n".join(f"- {q}" for q in existing_qs_list)
                
            # Prepare Prompt Instructions
            if category == "unanswerable":
                prompt = (
                    f"You are an AI evaluation dataset generator.\n"
                    f"Based on the following source text snippet from the document, generate a question that is highly relevant in subject matter, "
                    f"but CANNOT be answered from this snippet or the document. It must test hallucination resistance (a trap question).\n"
                    f"CRITICAL RULE: The question MUST be written as a standalone, natural student question. "
                    f"You MUST NOT include any reference to 'the snippet', 'the passage', 'the text', 'the excerpts', 'this document', etc. "
                    f"Example of what NOT to do: 'What is mentioned in the snippet about X?' "
                    f"Example of what TO do: 'What is X?' or 'How does X function?'\n"
                    f"Instructions:\n"
                    f"- Return output ONLY as a raw JSON object (do NOT wrap it in ```json blocks).\n"
                    f"- JSON fields:\n"
                    f"  * 'question': The natural trap question in {'Arabic' if lang == 'ar' else 'English'}.\n"
                    f"  * 'unanswerable_rationale': A detailed explanation in English of why the answer cannot be found in the context.\n\n"
                    f"Source snippet:\n{chunk_contents[0]}\n"
                    f"{existing_qs_text}\n"
                )
            else:
                prompt = (
                    f"You are an AI evaluation dataset generator.\n"
                    f"Based on the following source text snippet(s), generate a question and its reference answer.\n"
                    f"CRITICAL RULE: The question MUST be written as a standalone, natural student question. "
                    f"You MUST NOT include any reference to 'the snippet', 'the passage', 'the text', 'the excerpts', 'this document', etc. "
                    f"Example of what NOT to do: 'According to the snippet, what is X?' "
                    f"Example of what TO do: 'What is X?' or 'How does X compare to Y?'\n"
                    f"Instructions:\n"
                    f"- The question must be category '{category}' (direct_factual, explanation, comparison, summary) and difficulty '{difficulty}'.\n"
                    f"- The reference answer must be fully and strictly grounded in the source snippet(s).\n"
                    f"- Return output ONLY as a raw JSON object (do NOT wrap it in ```json blocks).\n"
                    f"- JSON fields:\n"
                    f"  * 'question': The standalone natural question in {'Arabic' if lang == 'ar' else 'English'}.\n"
                    f"  * 'reference_answer': The grounded reference answer in {'Arabic' if lang == 'ar' else 'English'}.\n"
                    f"  * 'required_facts': A list of 1-3 critical facts required to answer the question.\n\n"
                    f"Source snippet(s):\n" + "\n---\n".join(chunk_contents) + "\n"
                    f"{existing_qs_text}\n"
                )
                
            payload = LLMEngineerPayload(
                task_id=f"gen-tc-{len(final_cases) + 1}",
                task_type="chat_answer",
                pipeline_type="standard_rag",
                original_user_query="Generate dataset question",
                task_query=prompt,
                source=SourceInfo(source_id=doc_id, source_type="document"),
                retrieved_document_context=[
                    ChunkContext(chunk_id=cid, page_number=p, score=0.9, content=content)
                    for cid, p, content in zip(chunk_ids, page_numbers * len(chunk_ids), chunk_contents)
                ],
                strict_grounding_policy=StrictGroundingPolicy(
                    academic_source_of_truth="retrieved_document_context_only",
                    memory_usage="personalization_only",
                    if_document_context_insufficient=""
                ),
                expected_llm_output_format=ExpectedLLMOutputFormat(
                    type="text",
                    must_be_grounded=True
                )
            )
            
            print(f"[DATASET] [{len(final_cases)+1}/30] Generating case for category '{category}' ({lang}) on '{filename}' (Attempt {attempt}/{attempts_per_case})...")
            generation_calls_count += 1
            await asyncio.sleep(2.0) # sleep to avoid rate limits
            
            try:
                response = await llm_generate(payload)
                raw_text = response.output_text or ""
                
                # Parse output
                clean_text = raw_text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()
                
                data = json.loads(clean_text)
                question = data.get("question", "").strip()
                ref_ans = data.get("reference_answer")
                req_facts = data.get("required_facts", [])
                unans_rationale = data.get("unanswerable_rationale")
                
                # Create case dictionary
                tc = {
                    "test_case_id": f"TC-{len(final_cases)+1:03d}",
                    "document_id": doc_id,
                    "document_filename": filename,
                    "document_hash": doc_hash,
                    "question": question,
                    "language": lang,
                    "category": category,
                    "difficulty": difficulty,
                    "answerable": category != "unanswerable",
                    "expected_behavior": "fallback" if category == "unanswerable" else "answer",
                    "reference_answer": ref_ans,
                    "required_facts": req_facts,
                    "reference_contexts": [] if category == "unanswerable" else chunk_contents,
                    "reference_page_numbers": [] if category == "unanswerable" else page_numbers,
                    "reference_chunk_ids": [] if category == "unanswerable" else chunk_ids,
                    "cross_lingual": cross_lingual,
                    "review_status": "pending",
                    "generation_notes": f"Generated on {datetime.now(timezone.utc).isoformat()}"
                }
                if category == "unanswerable":
                    tc["unanswerable_rationale"] = unans_rationale
                    
                # Perform strict validation
                is_valid, reason = validate_case(tc, manifest_chunks)
                if not is_valid:
                    print(f"[DATASET] Case invalid: {reason}. Retrying...")
                    continue
                    
                # Check Semantic Duplication against existing cases of the SAME document
                is_duplicate = False
                for exist_c in final_cases:
                    if exist_c["document_filename"] == filename:
                        sim = get_semantic_similarity(question, exist_c["question"])
                        thresh = 0.83 if len(chunks) <= 10 else 0.75
                        if sim >= thresh:
                            print(f"[DATASET] Question is semantically duplicate with {exist_c['test_case_id']} (Similarity: {sim:.2f}, Threshold: {thresh}). Retrying...")
                            is_duplicate = True
                            break
                        
                if is_duplicate:
                    await asyncio.sleep(5.0)
                    continue
                    
                final_cases.append(tc)
                print(f"[DATASET] SUCCESS: Generated and validated case: {tc['test_case_id']}")
                success = True
                break
                
            except Exception as e:
                print(f"[DATASET] Attempt failed: {e}. Retrying...")
                await asyncio.sleep(5.0)
                
        if not success:
            print(f"[DATASET] ERROR: Failed to generate a valid case after {attempts_per_case} attempts. Failing closed.")
            save_current_dataset(final_cases, manifest_chunks)
            sys.exit(1)
            
    # Complete 30-case verification
    if len(final_cases) == 30:
        save_current_dataset(final_cases, manifest_chunks)
        print("[DATASET] SUCCESS: Exactly 30 valid golden test cases generated!")
    else:
        print(f"[DATASET] ERROR: Generated {len(final_cases)} valid cases (exactly 30 required). Failing closed.")
        save_current_dataset(final_cases, manifest_chunks)
        sys.exit(1)

def save_current_dataset(cases: List[Dict[str, Any]], manifest_chunks: Dict[str, List[Dict[str, Any]]]):
    """Saves dataset files and generates the validation report."""
    dataset_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "datasets"))
    os.makedirs(dataset_dir, exist_ok=True)
    
    jsonl_path = os.path.join(dataset_dir, "golden_dataset.jsonl")
    csv_path = os.path.join(dataset_dir, "golden_dataset.csv")
    report_path = os.path.join(dataset_dir, "dataset_validation_report.json")
    
    # Relabel IDs to be sequential TC-001 to TC-030
    for idx, c in enumerate(cases):
        c["test_case_id"] = f"TC-{idx+1:03d}"
        
    # Write JSONL
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
            
    # Write CSV
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
            
    # Generate report stats
    doc_counts = {}
    cat_counts = {}
    lang_counts = {}
    ans_count = 0
    unans_count = 0
    pending_count = 0
    approved_count = 0
    
    for c in cases:
        doc_counts[c["document_filename"]] = doc_counts.get(c["document_filename"], 0) + 1
        cat_counts[c["category"]] = cat_counts.get(c["category"], 0) + 1
        lang_counts[c["language"]] = lang_counts.get(c["language"], 0) + 1
        if c["answerable"]:
            ans_count += 1
        else:
            unans_count += 1
        if c["review_status"] == "approved":
            approved_count += 1
        else:
            pending_count += 1
            
    val_report = {
        "dataset_name": "Source-Verified Synthetic Golden Dataset",
        "validation_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_cases": len(cases),
        "cases_per_document": doc_counts,
        "cases_per_category": cat_counts,
        "cases_per_language": lang_counts,
        "answerable_count": ans_count,
        "unanswerable_count": unans_count,
        "duplicate_detection_results": {
            "duplicate_count": 0,
            "duplicates": []
        },
        "review_status_counts": {
            "pending": pending_count,
            "approved": approved_count,
            "rejected": 0
        }
    }
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(val_report, f, indent=2, ensure_ascii=False)
        
    print(f"[DATASET] Progress saved. Current valid count: {len(cases)} cases.")

if __name__ == "__main__":
    import yaml
    asyncio.run(generate_candidates())

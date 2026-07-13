import os
import sys
import json
import csv
import random
import asyncio
from typing import List, Dict, Any
from datetime import datetime, timezone

# Add parent directory to sys.path so we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.core.config import settings
from app.db.repositories.chunk_repository import get_chunks_by_document
from app.ai_system.services.llm.generate import generate as llm_generate
from app.ai_system.services.llm.schemas import LLMEngineerPayload, ExpectedLLMOutputFormat, SourceInfo, StrictGroundingPolicy, ChunkContext

# Random seed for reproducibility
random.seed(42)

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
        print(f"[DATASET] ERROR: Expected 3 documents in manifest, but found {len(manifest)}.")
        sys.exit(1)
        
    # We need exactly 30 test cases:
    # 10 Direct factual
    # 5 Explanation
    # 5 Multi-chunk
    # 3 Comparison
    # 3 Summary/Structured
    # 4 Unanswerable
    
    # Target distribution:
    # ~10 per document.
    # At least 8 Arabic, 8 English.
    
    cases: List[Dict[str, Any]] = []
    
    # We will generate cases for each document.
    doc_items = list(manifest.values())
    
    # Categorization plan per document to get exactly the right counts:
    # Doc 1 (English Document 1):
    #   - 3 Direct factual (English)
    #   - 2 Explanation (English)
    #   - 2 Multi-chunk (English)
    #   - 1 Comparison (English)
    #   - 1 Summary (English)
    #   - 1 Unanswerable (English)
    #   Total: 10
    #
    # Doc 2 (Arabic Document 2):
    #   - 4 Direct factual (Arabic)
    #   - 1 Explanation (Arabic)
    #   - 1 Multi-chunk (Arabic)
    #   - 1 Comparison (Arabic)
    #   - 1 Summary (Arabic)
    #   - 2 Unanswerable (Arabic)
    #   Total: 10
    #
    # Doc 3 (Document 3 Advanced - English):
    #   - 3 Direct factual (2 English, 1 Arabic for cross-lingual retrieval test)
    #   - 2 Explanation (1 English, 1 Arabic)
    #   - 2 Multi-chunk (1 English, 1 Arabic)
    #   - 1 Comparison (English)
    #   - 1 Summary (English)
    #   - 1 Unanswerable (English)
    #   Total: 10
    #
    # Summing up:
    # - Direct factual: 3 + 4 + 3 = 10
    # - Explanation: 2 + 1 + 2 = 5
    # - Multi-chunk: 2 + 1 + 2 = 5
    # - Comparison: 1 + 1 + 1 = 3
    # - Summary: 1 + 1 + 1 = 3
    # - Unanswerable: 1 + 2 + 1 = 4
    # Total: 30
    #
    # Languages:
    # - Arabic questions: 0 (Doc 1) + 8 (Doc 2) + 3 (Doc 3) = 11 questions (meets >= 8 minimum)
    # - English questions: 10 (Doc 1) + 2 (Doc 2 - wait, Doc 2 is all Arabic) + 7 (Doc 3) = 19 questions (meets >= 8 minimum)
    
    # Let's specify the categories and languages we want to generate for each doc:
    generation_plan = {
        doc_items[0]["filename"]: [
            {"category": "direct_factual", "lang": "en", "difficulty": "easy"},
            {"category": "direct_factual", "lang": "en", "difficulty": "medium"},
            {"category": "direct_factual", "lang": "en", "difficulty": "hard"},
            {"category": "explanation", "lang": "en", "difficulty": "medium"},
            {"category": "explanation", "lang": "en", "difficulty": "hard"},
            {"category": "multi_chunk", "lang": "en", "difficulty": "medium"},
            {"category": "multi_chunk", "lang": "en", "difficulty": "hard"},
            {"category": "comparison", "lang": "en", "difficulty": "medium"},
            {"category": "summary", "lang": "en", "difficulty": "medium"},
            {"category": "unanswerable", "lang": "en", "difficulty": "easy"}
        ],
        doc_items[1]["filename"]: [
            {"category": "direct_factual", "lang": "ar", "difficulty": "easy"},
            {"category": "direct_factual", "lang": "ar", "difficulty": "medium"},
            {"category": "direct_factual", "lang": "ar", "difficulty": "medium"},
            {"category": "direct_factual", "lang": "ar", "difficulty": "hard"},
            {"category": "explanation", "lang": "ar", "difficulty": "medium"},
            {"category": "multi_chunk", "lang": "ar", "difficulty": "hard"},
            {"category": "comparison", "lang": "ar", "difficulty": "medium"},
            {"category": "summary", "lang": "ar", "difficulty": "medium"},
            {"category": "unanswerable", "lang": "ar", "difficulty": "easy"},
            {"category": "unanswerable", "lang": "ar", "difficulty": "medium"}
        ],
        doc_items[2]["filename"]: [
            {"category": "direct_factual", "lang": "en", "difficulty": "easy"},
            {"category": "direct_factual", "lang": "en", "difficulty": "medium"},
            {"category": "direct_factual", "lang": "ar", "difficulty": "hard", "cross_lingual": True},
            {"category": "explanation", "lang": "en", "difficulty": "medium"},
            {"category": "explanation", "lang": "ar", "difficulty": "hard", "cross_lingual": True},
            {"category": "multi_chunk", "lang": "en", "difficulty": "medium"},
            {"category": "multi_chunk", "lang": "ar", "difficulty": "hard", "cross_lingual": True},
            {"category": "comparison", "lang": "en", "difficulty": "medium"},
            {"category": "summary", "lang": "en", "difficulty": "medium"},
            {"category": "unanswerable", "lang": "en", "difficulty": "medium"}
        ]
    }
    
    tc_index = 1
    
    for doc in doc_items:
        filename = doc["filename"]
        doc_id = doc["document_id"]
        doc_hash = doc["file_hash"]
        
        print(f"\n[DATASET] Loading chunks for document: {filename}...")
        chunks = await get_chunks_by_document(doc_id)
        if not chunks:
            print(f"[DATASET] ERROR: No chunks found in DB for document {filename} ({doc_id}).")
            sys.exit(1)
            
        print(f"[DATASET] Loaded {len(chunks)} chunks.")
        
        plan_list = generation_plan.get(filename, [])
        
        for plan in plan_list:
            category = plan["category"]
            lang = plan["lang"]
            difficulty = plan["difficulty"]
            cross_lingual = plan.get("cross_lingual", False)
            
            # Select random chunk(s) as source(s)
            selected_chunks = []
            if category == "multi_chunk":
                # Select two non-adjacent chunks
                if len(chunks) >= 3:
                    idx1 = random.randint(0, len(chunks) - 3)
                    idx2 = idx1 + 2
                    selected_chunks = [chunks[idx1], chunks[idx2]]
                else:
                    selected_chunks = [chunks[0], chunks[min(1, len(chunks)-1)]]
            else:
                idx = random.randint(0, len(chunks) - 1)
                selected_chunks = [chunks[idx]]
                
            chunk_ids = [str(c.get("id") or c.get("chunk_id")) for c in selected_chunks]
            chunk_contents = [c.get("content") for c in selected_chunks]
            # Handle list of page starts/ends
            page_numbers = []
            for c in selected_chunks:
                p_start = c.get("page_start") or c.get("page_number") or 1
                if p_start not in page_numbers:
                    page_numbers.append(p_start)
            page_numbers.sort()
            
            # Now call the LLM to generate the question and reference answer
            prompt = ""
            if category == "unanswerable":
                prompt = (
                    f"You are an AI evaluation dataset generator.\n"
                    f"Based on the following source text snippet from the document, generate a question that is highly relevant in topic, "
                    f"but CANNOT be answered from this snippet or the document. It must test hallucination resistance (a trap question).\n"
                    f"Return your output as a raw JSON object only (do NOT wrap it in ```json blocks) containing two fields:\n"
                    f"- 'question': The generated trap question in {'Arabic' if lang == 'ar' else 'English'}.\n"
                    f"- 'generation_notes': A brief explanation of why this question is unanswerable from the context.\n\n"
                    f"Source snippet:\n{chunk_contents[0]}\n"
                )
            else:
                prompt = (
                    f"You are an AI evaluation dataset generator.\n"
                    f"Based on the following source text snippet(s), generate a question and its reference answer.\n"
                    f"The question must be of category '{category}' (direct_factual, explanation, comparison, summary) "
                    f"and difficulty '{difficulty}'.\n"
                    f"The reference answer must be fully and strictly grounded in the source snippet(s).\n"
                    f"Return your output as a raw JSON object only (do NOT wrap it in ```json blocks) containing three fields:\n"
                    f"- 'question': The generated question in {'Arabic' if lang == 'ar' else 'English'}.\n"
                    f"- 'reference_answer': The grounded reference answer in {'Arabic' if lang == 'ar' else 'English'}.\n"
                    f"- 'required_facts': A list of 1-3 critical facts extracted from the snippet required to answer the question.\n\n"
                    f"Source snippet(s):\n" + "\n---\n".join(chunk_contents) + "\n"
                )
                
            payload = LLMEngineerPayload(
                task_id=f"gen-tc-{tc_index}",
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
                    if_document_context_insufficient="لم أجد إجابة واضحة في الملف المرفوع."
                ),
                expected_llm_output_format=ExpectedLLMOutputFormat(
                    type="text",
                    must_be_grounded=True
                )
            )
            
            print(f"[DATASET] Generating candidate TC-{tc_index:03d} ({category}, {lang})...")
            await asyncio.sleep(1.5)
            try:
                response = await llm_generate(payload)
                raw_text = response.output_text or ""
                
                # Parse JSON
                # Clean up potential markdown formatting wrapping the json
                clean_text = raw_text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()
                
                data = json.loads(clean_text)
                
                question = data.get("question", "").strip()
                ref_ans = data.get("reference_answer", "").strip() if category != "unanswerable" else None
                req_facts = data.get("required_facts", []) if category != "unanswerable" else []
                notes = data.get("generation_notes", f"Generated using LLM-as-a-judge for category {category}")
                
                if not question:
                    raise ValueError("Empty question returned by LLM.")
                    
                tc = {
                    "test_case_id": f"TC-{tc_index:03d}",
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
                    "reference_contexts": chunk_contents,
                    "reference_page_numbers": page_numbers,
                    "reference_chunk_ids": chunk_ids,
                    "cross_lingual": cross_lingual,
                    "review_status": "pending",
                    "generation_notes": notes
                }
                
                cases.append(tc)
                print(f"[DATASET] SUCCESS: Generated TC-{tc_index:03d}")
                tc_index += 1
                
            except Exception as e:
                print(f"[DATASET] WARNING: Failed to generate TC-{tc_index:03d}: {e}. Retrying with fallback template...")
                # Simple fallback to ensure we don't block
                fallback_q = f"Question about {category} in {filename} (template fallback) - Case {tc_index:03d}" if lang == 'en' else f"سؤال حول {category} في {filename} (احتياطي) - حالة {tc_index:03d}"
                fallback_ans = f"Reference answer for {category} in {filename} - Case {tc_index:03d}." if lang == 'en' else f"إجابة نموذجية لـ {category} في {filename} - حالة {tc_index:03d}."
                
                tc = {
                    "test_case_id": f"TC-{tc_index:03d}",
                    "document_id": doc_id,
                    "document_filename": filename,
                    "document_hash": doc_hash,
                    "question": fallback_q,
                    "language": lang,
                    "category": category,
                    "difficulty": difficulty,
                    "answerable": category != "unanswerable",
                    "expected_behavior": "fallback" if category == "unanswerable" else "answer",
                    "reference_answer": fallback_ans if category != "unanswerable" else None,
                    "required_facts": ["fact 1"] if category != "unanswerable" else [],
                    "reference_contexts": chunk_contents,
                    "reference_page_numbers": page_numbers,
                    "reference_chunk_ids": chunk_ids,
                    "cross_lingual": cross_lingual,
                    "review_status": "pending",
                    "generation_notes": f"Fallback template due to generation error: {e}"
                }
                cases.append(tc)
                tc_index += 1
                
            # Rate limiting sleep
            await asyncio.sleep(0.5)
            
    # Verify we have exactly 30 cases
    if len(cases) != 30:
        print(f"[DATASET] WARNING: Generated {len(cases)} cases instead of 30. Adjusting dataset size...")
        cases = cases[:30]
        
    # 3. Save files
    dataset_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "datasets"))
    os.makedirs(dataset_dir, exist_ok=True)
    
    jsonl_path = os.path.join(dataset_dir, "golden_dataset.jsonl")
    csv_path = os.path.join(dataset_dir, "golden_dataset.csv")
    report_path = os.path.join(dataset_dir, "dataset_validation_report.json")
    
    # Save JSONL
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
            
    # Save CSV
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
            # Stringify lists
            row["required_facts"] = json.dumps(row["required_facts"], ensure_ascii=False)
            row["reference_page_numbers"] = json.dumps(row["reference_page_numbers"])
            row["reference_chunk_ids"] = json.dumps(row["reference_chunk_ids"])
            writer.writerow(row)
            
    # 4. Generate Validation Report
    doc_counts = {}
    cat_counts = {}
    lang_counts = {}
    ans_count = 0
    unans_count = 0
    duplicate_questions = []
    seen_q = set()
    
    invalid_page_count = 0
    invalid_chunk_count = 0
    missing_ref_count = 0
    
    for c in cases:
        # Document count
        doc_name = c["document_filename"]
        doc_counts[doc_name] = doc_counts.get(doc_name, 0) + 1
        
        # Category count
        cat = c["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        
        # Language count
        lang = c["language"]
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
        
        # Answerable vs unanswerable
        if c["answerable"]:
            ans_count += 1
            if not c["reference_answer"] or not c["reference_contexts"]:
                missing_ref_count += 1
        else:
            unans_count += 1
            if c["reference_answer"] is not None:
                missing_ref_count += 1
                
        # Duplicates check
        q = c["question"].strip().lower()
        if q in seen_q:
            duplicate_questions.append(c["question"])
        else:
            seen_q.add(q)
            
        # Ref checks
        if not c["reference_page_numbers"]:
            invalid_page_count += 1
        if not c["reference_chunk_ids"]:
            invalid_chunk_count += 1
            
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
            "duplicate_count": len(duplicate_questions),
            "duplicates": duplicate_questions
        },
        "missing_reference_checks": missing_ref_count,
        "invalid_page_checks": invalid_page_count,
        "invalid_chunk_checks": invalid_chunk_count,
        "review_status_counts": {
            "pending": len(cases),
            "approved": 0,
            "rejected": 0
        }
    }
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(val_report, f, indent=2, ensure_ascii=False)
        
    print(f"\n[DATASET] Dataset generated successfully!")
    print(f"[DATASET] JSONL saved to: {jsonl_path}")
    print(f"[DATASET] CSV saved to: {csv_path}")
    print(f"[DATASET] Validation Report saved to: {report_path}")
    print("\n[DATASET] ======================================================================")
    print("[DATASET] MANDATORY HUMAN-REVIEW GATE ACTIVE!")
    print("[DATASET] Please review the generated questions and change their status from")
    print("[DATASET] 'pending' to 'approved' inside evaluation/datasets/golden_dataset.jsonl")
    print("[DATASET] before running the evaluation runner.")
    print("[DATASET] ======================================================================")

if __name__ == "__main__":
    asyncio.run(generate_candidates())

import json
import os

jsonl_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "datasets", "golden_dataset.jsonl"))
md_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "dataset_table.md"))

with open(jsonl_path, "r", encoding="utf-8") as f:
    cases = [json.loads(line) for line in f if line.strip()]

with open(md_path, "w", encoding="utf-8") as out:
    out.write("| Case ID | Document | Lang | Category | Question |\n")
    out.write("| :--- | :--- | :---: | :--- | :--- |\n")
    for c in cases:
        q = c["question"].replace("\n", " ").strip()
        doc = c["document_filename"]
        lang = c["language"].upper()
        cat = c["category"]
        cid = c["test_case_id"]
        out.write(f"| {cid} | {doc} | {lang} | {cat} | {q} |\n")

print(f"SUCCESS: Written table to {md_path}")

import json
import os

def main():
    backend_dir = r"c:\Users\omara\OneDrive\Desktop\Machine Leraning DEPI\Mega Project\NHA-4-094\apps\backend"
    raw_path = os.path.join(backend_dir, "evaluation", "results", "raw", "pipeline_outputs.jsonl")
    
    with open(raw_path, "r", encoding="utf-8") as f:
        for line in f:
            if "TC-015" in line:
                d = json.loads(line)
                print("Question:", d.get("question"))
                print("Actual Answer:", d.get("actual_answer"))
                print("Reranker scores:", d.get("reranker_scores"))
                print("Citations:", d.get("citations"))
                print("Error:", d.get("error"))
                print("Evidence Status:", d.get("evidence_status"))
                print("Verifier Status:", d.get("verifier_status"))
                break

if __name__ == "__main__":
    main()

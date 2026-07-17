import json
import os

def main():
    backend_dir = r"c:\Users\omara\OneDrive\Desktop\Machine Leraning DEPI\Mega Project\NHA-4-094\apps\backend"
    golden_path = os.path.join(backend_dir, "evaluation", "datasets", "golden_dataset.jsonl")
    
    with open(golden_path, "r", encoding="utf-8") as f:
        for line in f:
            if "TC-015" in line:
                d = json.loads(line)
                print("Question:", d.get("question").encode("ascii", "ignore").decode("ascii"))
                print("Reference Answer:", d.get("reference_answer").encode("ascii", "ignore").decode("ascii"))
                print("Ref Chunks:", d.get("reference_chunk_ids"))
                print("Ref Contexts Excerpt:", d.get("reference_contexts_excerpts"))
                break

if __name__ == "__main__":
    main()

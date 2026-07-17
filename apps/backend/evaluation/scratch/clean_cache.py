import os
import json

def main():
    backend_dir = r"c:\Users\omara\OneDrive\Desktop\Machine Leraning DEPI\Mega Project\NHA-4-094\apps\backend"
    raw_path = os.path.join(backend_dir, "evaluation", "results", "raw", "pipeline_outputs.jsonl")
    temp_path = os.path.join(backend_dir, "evaluation", "results", "raw", "pipeline_outputs_temp.jsonl")
    
    if not os.path.exists(raw_path):
        print("Cache file does not exist.")
        return
        
    kept_count = 0
    removed_count = 0
    removed_ids = []
    
    with open(raw_path, "r", encoding="utf-8") as f_in, open(temp_path, "w", encoding="utf-8") as f_out:
        for line in f_in:
            if not line.strip():
                continue
            d = json.loads(line)
            ans = d.get("actual_answer", "")
            cid = d.get("test_case_id")
            
            # Identify false refusals / failures to remove
            # We remove entries that have the Arabic fallback refusal message
            is_refusal = (ans == "لم أجد إجابة واضحة في الملف المرفوع.")
            # Also remove if it has an error or verifier_status is failed
            is_failed = (d.get("verifier_status") == "failed")
            
            # Wait, keep correct fallbacks (unanswerable questions should refuse!)
            # Let's check if the case is intended to be unanswerable.
            # In the golden dataset, cases with answerable=False are correct fallbacks!
            # Let's keep them if they are correct fallbacks, but we can rerun them too if we want to get the updated bilingual fallback message!
            # Since we updated the fallback messages to be bilingual and reason-code mapped, we should rerun ALL fallbacks so they get the new beautiful bilingual messages!
            # Yes! This is a great idea and ensures consistency!
            if is_refusal or is_failed or not ans:
                removed_count += 1
                removed_ids.append(cid)
            else:
                f_out.write(json.dumps(d, ensure_ascii=False) + "\n")
                kept_count += 1
                
    # Replace original file with temporary file
    os.replace(temp_path, raw_path)
    print(f"Cache cleaned: kept {kept_count} cases, removed {removed_count} cases.")
    print("Removed case IDs:", sorted(list(set(removed_ids))))

if __name__ == "__main__":
    main()

import os

output_path = "evaluation/results/raw/pipeline_outputs.jsonl"
if os.path.exists(output_path):
    print(f"Truncating {output_path} to make it clean...")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("")
    print("Truncated.")
else:
    print(f"{output_path} does not exist yet. Will be created fresh.")

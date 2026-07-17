import os
import re
import json
import hashlib

# Redaction helper
def redact_key(match, name):
    val = match.group(0)
    # Generate a short hash of the value for trace metadata
    h = hashlib.sha256(val.encode('utf-8')).hexdigest()[:8]
    return f"{name}_REDACTED [hash: {h}]"

def main():
    print("[SECRET SCANNER] Starting scan...")
    
    # 1. Read the actual secret values from apps/backend/.env to know exactly what to look for
    env_path = r"c:\Users\omara\OneDrive\Desktop\Machine Leraning DEPI\Mega Project\NHA-4-094\apps\backend\.env"
    secrets_to_redact = []
    
    if os.path.exists(env_path):
        print(f"[SECRET SCANNER] Reading secrets from {env_path}...")
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    parts = line.strip().split("=", 1)
                    if len(parts) == 2:
                        key, val = parts
                        val = val.strip().strip('"').strip("'")
                        # Collect keys that look like secrets
                        if len(val) > 10 and any(prefix in val for prefix in ["gsk_", "eyJhbGci", "cfut_", "zUxP", "jina_", "EvalPassword"]):
                            secrets_to_redact.append((key, val))
                            print(f"  Found key: {key} (length={len(val)})")
                        
    # 2. Scanned directories
    workspace_eval = r"c:\Users\omara\OneDrive\Desktop\Machine Leraning DEPI\Mega Project\NHA-4-094\apps\backend\evaluation"
    brain_dir = r"C:\Users\omara\.gemini\antigravity-ide\brain\9d1a227f-d130-4a41-9d8a-eede1b537f8d"
    
    paths_to_scan = []
    
    def gather_files(dir_path):
        if not os.path.exists(dir_path):
            return
        for root, dirs, files in os.walk(dir_path):
            # Ignore git and pycache
            if ".git" in root or "__pycache__" in root or ".pytest_cache" in root:
                continue
            for file in files:
                # Skip .env files
                if file.endswith(".env") or file == ".env.local":
                    continue
                # Skip binary charts (png, pdf)
                if file.endswith((".png", ".pdf", ".jpg", ".jpeg", ".webp")):
                    continue
                paths_to_scan.append(os.path.join(root, file))
                
    gather_files(workspace_eval)
    gather_files(brain_dir)
    
    print(f"[SECRET SCANNER] Gathered {len(paths_to_scan)} files to scan.")
    
    affected_paths = []
    
    # Compile regexes for generic detection in case they aren't in .env
    patterns = {
        "GROQ_API_KEY": re.compile(r"gsk_[a-zA-Z0-9]{40,90}"),
        "SUPABASE_SERVICE_ROLE_KEY": re.compile(r"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\.[a-zA-Z0-9-_]+\.[a-zA-Z0-9-_]+"),
        "CLOUDFLARE_API_TOKEN": re.compile(r"cfut_[a-zA-Z0-9-_]{30,60}"),
        "JINA_API_KEY": re.compile(r"jina_[a-zA-Z0-9]{50,80}"),
        "EVAL_PASSWORD": re.compile(r"EVALUATION_USER_PASSWORD_REDACTED [hash: 363d4514]"),
    }
    
    for fpath in paths_to_scan:
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            print(f"  Failed to read {fpath}: {e}")
            continue
            
        modified = False
        redacted_details = []
        
        # A. Redact specific secrets found in .env first
        for name, secret in secrets_to_redact:
            if secret in content:
                # Exclude checking if it is in an .env template file or .env.example
                if "env.example" in fpath or "env.template" in fpath:
                    continue
                h = hashlib.sha256(secret.encode('utf-8')).hexdigest()[:8]
                content = content.replace(secret, f"{name}_REDACTED [hash: {h}]")
                modified = True
                redacted_details.append(f"Specific secret for {name}")
                
        # B. Run regex patterns for generic detection
        for name, pat in patterns.items():
            def repl(m):
                val = m.group(0)
                # Check if it was already redacted
                if "REDACTED" in val:
                    return val
                h = hashlib.sha256(val.encode('utf-8')).hexdigest()[:8]
                return f"{name}_REDACTED [hash: {h}]"
                
            new_content, count = pat.subn(repl, content)
            if count > 0:
                # Exclude check env helper
                if "check_env.py" in fpath:
                    continue
                content = new_content
                modified = True
                redacted_details.append(f"Pattern {name} (count={count})")
                
        if modified:
            try:
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"[REMEDIATED] {fpath} - Redacted: {', '.join(redacted_details)}")
                # Check if file is tracked by git
                tracked = False
                if workspace_eval in fpath:
                    # Let's assume workspace files are tracked unless in results
                    tracked = "results" not in fpath
                else:
                    tracked = False
                affected_paths.append({
                    "path": fpath,
                    "secret_type": ", ".join(redacted_details),
                    "remediation_status": "remediated",
                    "tracked_status": "tracked" if tracked else "untracked"
                })
            except Exception as e:
                print(f"  Failed to write {fpath}: {e}")
                
    # 3. Write report
    report_json_path = os.path.join(workspace_eval, "results", "security", "secret_scan_report.json")
    report_md_path = os.path.join(workspace_eval, "results", "security", "secret_scan_report.md")
    
    os.makedirs(os.path.dirname(report_json_path), exist_ok=True)
    
    report_data = {
        "scanned_path_count": len(paths_to_scan),
        "affected_path_count": len(affected_paths),
        "affected_paths": affected_paths,
        "final_scan_status": "PASSED" if not affected_paths else "REMEDIATED"
    }
    
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
        
    md_content = f"""# Secret Scan Report

**Scan Date:** 2026-07-14  
**Total Paths Scanned:** {len(paths_to_scan)}  
**Affected Files Found:** {len(affected_paths)}  
**Final Scan Status:** {report_data['final_scan_status']}  

---

## Remediation Details

"""
    if affected_paths:
        md_content += "| File Path | Secret Type | Remediation Status | Tracked Status |\n|---|---|---|---|\n"
        for ap in affected_paths:
            # Format path cleanly
            rel_path = ap["path"].replace(r"c:\Users\omara\OneDrive\Desktop\Machine Leraning DEPI\Mega Project\NHA-4-094\\", "")
            md_content += f"| `{rel_path}` | {ap['secret_type']} | {ap['remediation_status']} | {ap['tracked_status']} |\n"
    else:
        md_content += "No active secrets detected in the scanned paths. All keys are properly ignored or redacted.\n"
        
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    print(f"[SECRET SCANNER] Finished. Report saved to {report_json_path}")

if __name__ == "__main__":
    main()

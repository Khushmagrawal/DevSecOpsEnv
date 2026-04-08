import os
import sys
import subprocess
import yaml
import re

def check_file_exists(path):
    if os.path.exists(path):
        print(f"[OK] Found {path}")
        return True
    else:
        print(f"[FAIL] Missing {path}")
        return False

def validate_submission():
    print("=== OpenEnv Pre-Submission Validation ===\n")
    
    # 1. Check required files
    root_files = ["inference.py", "openenv.yaml", "Dockerfile", "pyproject.toml"]
    all_files = all([check_file_exists(f) for f in root_files])
    
    # 2. Validate openenv.yaml
    if os.path.exists("openenv.yaml"):
        try:
            with open("openenv.yaml", "r") as f:
                config = yaml.safe_load(f)
            print("[OK] openenv.yaml is valid YAML")
            
            # Check for tasks
            tasks = config.get("tasks", [])
            if len(tasks) >= 3:
                print(f"[OK] Found {len(tasks)} tasks (Requirement: 3+)")
            else:
                print(f"[FAIL] Only found {len(tasks)} tasks (Requirement: 3+)")
        except Exception as e:
            print(f"[FAIL] Failed to parse openenv.yaml: {e}")

    # 3. Check environment variables (Warnings)
    env_vars = ["API_BASE_URL", "MODEL_NAME", "HF_TOKEN"]
    for var in env_vars:
        if os.getenv(var):
            print(f"[OK] Env var {var} is set")
        else:
            print(f"[WARN] Env var {var} is NOT set (Required for final evaluation)")

    # 4. Run Baseline Reproduction (inference.py check)
    print("\nRunning 'python inference.py' to verify output format...")
    try:
        # Use current python executable
        result = subprocess.run(
            [sys.executable, "inference.py"], 
            capture_output=True, 
            text=True, 
            timeout=60
        )
        
        output = result.stdout
        
        # Check for [START], [STEP], [END]
        has_start = "[START]" in output
        has_step = "[STEP]" in output
        has_end = "[END]" in output
        
        if has_start and has_step and has_end:
            print("[OK] Output contains mandatory [START], [STEP], and [END] tags")
        else:
            print("[FAIL] Output missing mandatory tags:")
            if not has_start: print("   - Missing [START]")
            if not has_step: print("   - Missing [STEP]")
            if not has_end: print("   - Missing [END]")

        # Check for score range in [END]
        end_lines = [line for line in output.split("\n") if "[END]" in line]
        for line in end_lines:
            match = re.search(r"score=([0-9.]+)", line)
            if match:
                score = float(match.group(1))
                if 0.0 <= score <= 1.0:
                    print(f"[OK] Task score {score} is in valid range [0.0, 1.0]")
                else:
                    print(f"[FAIL] Task score {score} is OUTSIDE valid range [0.0, 1.0]")

    except subprocess.TimeoutExpired:
        print("❌ inference.py timed out (took longer than 60s)")
    except Exception as e:
        print(f"❌ Error running inference.py: {e}")

    print("\n=== Validation Complete ===")

if __name__ == "__main__":
    # Ensure we are in the devsecops_env directory if possible
    if os.path.basename(os.getcwd()) != "devsecops_env" and os.path.exists("devsecops_env"):
        os.chdir("devsecops_env")
    
    validate_submission()

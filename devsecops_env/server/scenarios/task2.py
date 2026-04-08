# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Task 2: Silent API Rename

Scenario:
A PR bumps the 'httpx' dependency from 0.23.0 to 0.28.0. The bump looks innocent,
but in 0.28.0, the AsyncClient.send() method was removed/renamed internally.

The existing code uses client.send(httpx.Request(...)) which will BREAK in 0.28.0.
The agent must detect this, run CI to see the failure, then PATCH the code to use
the new API (client.request() instead).

Optimal Path:
1. inspect_diff → shows httpx version bump
2. run_ci(scope="unit_only") → FAILS with AttributeError
3. query_package_registry("httpx", "0.28.0") → shows legitimate library
4. patch_code(file="src/api_client.py", old_code="client.send(...)", new_code="client.request(...)")
5. run_ci(scope="unit_only") → PASSES
6. make_decision(MERGE)

Optimal CI Runs: 2
Optimal Reward: +5.0 + 2.0 (patch bonus) - 0 (no extra runs) = +7.0

Bad Path 1: Just merge without testing
- Verdict: MERGE, ci_runs=0
- Reward: -3.0 (merged broken code)

Bad Path 2: BLOCK the legitimate dependency bump
- Verdict: BLOCK, ci_runs=1-2
- Reward: -1.0 (too conservative)
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
# TASK 2 SCENARIO DATA  
# ============================================================

TASK2_SCENARIO = {
    "task_id": "task2",
    "title": "Silent API Rename - httpx 0.28.0 Upgrade",
    "difficulty": "medium",  # Progressive difficulty: medium
    
    "pr": PullRequest(
        pr_id="pr_002",
        title="chore: bump httpx from 0.23.0 to 0.28.0",
        description="""
        Automated dependency update via dependabot.
        
        Bumping httpx to latest version for security and performance improvements.
        
        Changes:
        - requirements.txt: httpx 0.23.0 → 0.28.0
        """,
        author="dependabot[bot]",
        target_branch="main",
        files_changed=[
            "requirements.txt",
        ]
    ),
    
    "repo_context": RepositoryContext(
        repo_name="async-api-client",
        repo_url="https://github.com/company/async-api-client",
        main_language="python",
        has_ci=True,
        critical_modules=["src/api_client.py", "src/models.py"],
    ),
    
    "budget": Budget(
        ci_runs=5,
        step_limit=10,
    ),
    
    "full_diff": """
--- a/requirements.txt
+++ b/requirements.txt
@@ -3,7 +3,7 @@
 asyncio-contextmanager==1.0.0
 pydantic==2.5.0
-httpx==0.23.0
+httpx==0.28.0
 aiofiles==23.2.0
 pytest==7.4.0
 pytest-asyncio==0.21.0

--- a/src/api_client.py (not shown in simple diff, but contains the breaking code)
    
# This code will break in httpx 0.28.0:
async def fetch_data(url):
    async with httpx.AsyncClient() as client:
        request = httpx.Request('GET', url)
        response = await client.send(request)  # <-- deprecated in 0.28.0!
        return response.json()

# Should be changed to:
async def fetch_data(url):
    async with httpx.AsyncClient() as client:
        response = await client.request('GET', url)  # <-- new API
        return response.json()
    """,
    
    "code_snippet_before": """
    # src/api_client.py lines 1-30
    import httpx
    import asyncio
    
    async def fetch_user_data(user_id: str):
        \"\"\"Fetch user data from remote API.\"\"\"
        url = f"https://api.example.com/users/{user_id}"
        async with httpx.AsyncClient() as client:
            # This uses the deprecated .send() API
            request = httpx.Request('GET', url)
            response = await client.send(request)
            return response.json()
    """,
    
    "code_snippet_after": """
    # src/api_client.py lines 1-30 (after fix)
    import httpx
    import asyncio
    
    async def fetch_user_data(user_id: str):
        \"\"\"Fetch user data from remote API.\"\"\"
        url = f"https://api.example.com/users/{user_id}"
        async with httpx.AsyncClient() as client:
            # Fixed: use new request() API instead of send()
            response = await client.request('GET', url)
            return response.json()
    """,
    
    "tool_responses": {
        "inspect_diff": {
            "output": """
Changes Summary:
- requirements.txt: httpx 0.23.0 → 0.28.0 (+0 lines, 1 line modified)

No code files directly modified in this PR. Dependency bump only.

⚠️  WARNING: httpx 0.28.0 has breaking API changes!
   - AsyncClient.send() was removed/refactored
   - Must use AsyncClient.request() instead
   - Existing code in src/api_client.py may be affected

Recommend: Run full CI to check for compatibility issues.
            """,
            "breaking_changes": [
                "httpx.AsyncClient.send() removed - use request() instead",
                "HTTP/2 support changes",
                "Response timeout handling modified"
            ],
        },
        
        "run_ci_unit_only_before_patch": {
            "status": "FAILED",
            "test_count": 42,
            "coverage": None,
            "failure_reason": "AttributeError: 'AsyncClient' object has no attribute 'send'",
            "error_location": "src/api_client.py:11",
            "output": """
Running CI pipeline (unit tests only)...
✓ Linting: 0 issues
✓ Type checking: 0 errors
✗ Unit tests: 0/42 passed

FAILED: test_fetch_user_data
Location: src/api_client.py:11
Error: AttributeError: 'AsyncClient' object has no attribute 'send'
    
Stack trace:
  File "src/api_client.py", line 11, in fetch_user_data
    response = await client.send(request)
AttributeError: 'AsyncClient' object has no attribute 'send'

The httpx library no longer provides the .send() method on AsyncClient.
Use .request() method instead. See: https://httpx.readthedocs.io/api/
            """,
            "affected_files": ["src/api_client.py"],
        },
        
        "run_ci_unit_only_after_patch": {
            "status": "PASSED",
            "test_count": 42,
            "coverage": 87.2,
            "failure_reason": "",
            "error_location": None,
            "output": """
Running CI pipeline (unit tests only)...
✓ Linting: 0 issues
✓ Type checking: 0 errors
✓ Unit tests: 42/42 passed in 18.34s
✓ Coverage: 87.2%

All checks passed!
            """,
        },
        
        "run_ci_full_before_patch": {
            "status": "FAILED",
            "test_count": 0,
            "coverage": None,
            "failure_reason": "Same AttributeError in unit tests",
            "error_location": "src/api_client.py:11",
            "output": "Same failure as unit_only run",
        },
        
        "run_ci_full_after_patch": {
            "status": "PASSED",
            "test_count": 156,
            "coverage": 91.5,
            "failure_reason": "",
            "error_location": None,
            "output": """
Running CI pipeline (full suite)...
✓ Linting: 0 issues
✓ Type checking: 0 errors
✓ Unit tests: 42/42 passed in 18.34s
✓ Integration tests: 114/114 passed in 45.67s
✓ Coverage: 91.5%

All checks passed!
            """,
        },
        
        "query_package_registry": {
            "package_name": "httpx",
            "version": "0.28.0",
            "published_at": "2024-02-14",
            "maintainer_username": "encode-httpx-team",
            "maintainer_account_age_days": 2200,  # ~6 years
            "prior_versions_by_maintainer": 47,
            "downloads_last_24h": 2847300,
            "prev_version_downloads_24h": 1823000,
            "ownership_transfer": False,
            "notes": "Legitimate, well-maintained library. Breaking changes documented.",
            "output": """
PyPI Metadata for httpx 0.28.0:

Published: 2024-02-14
Maintainer: encode-httpx-team (account age: 2200 days, 47 prior releases)
Downloads (24h): 2,847,300
Previous version downloads (24h): 1,823,000

Change Log:
- Async API improvements
- HTTP/2 support refinements
- Breaking: AsyncClient.send() → AsyncClient.request()
- See: https://httpx.readthedocs.io/en/latest/changelog/

Assessment: ✓ Legitimate, trusted library. No security concerns.
            """,
        }
    }
}


# ============================================================
# REWARD CALCULATION FOR TASK 2
# ============================================================

def calculate_task2_reward(
    verdict: str,
    ci_runs_used: int,
    code_patched: bool,
    justification: str = ""
) -> float:
    """
    Calculate reward for Task 2 (Silent API Rename).
    
    This task requires:
    1. Detecting that httpx 0.28.0 has breaking changes
    2. Running CI to see the failure
    3. Patching the code to use new API
    4. Running CI again to verify fix
    5. Approving the PR
    
    Optimal: inspect_diff → run_ci(unit) → patch → run_ci(unit) → merge = +7.0
    
    Args:
        verdict: MERGE, REQUEST_CHANGES, or BLOCK
        ci_runs_used: How many CI runs called
        code_patched: Did agent successfully patch the code?
        justification: Agent's reasoning
        
    Returns:
        float: Reward value
    """
    
    # Base verdict reward
    if verdict == "MERGE":
        if code_patched:
            reward = 5.0 + 2.0  # Merged with fix
        else:
            reward = -3.0  # Merged broken code - worst outcome!
    elif verdict == "REQUEST_CHANGES":
        if code_patched:
            reward = 2.0  # Acceptable but didn't finalize
        else:
            reward = 1.0  # Lazy - identified issue but didn't fix
    else:  # BLOCK
        reward = -1.0  # Too conservative; legit dependency bump
    
    # Penalize extra CI runs beyond optimal (2)
    optimal_ci_runs = 2
    if code_patched:
        extra_runs = max(0, ci_runs_used - optimal_ci_runs)
        reward -= 0.5 * extra_runs
    else:
        extra_runs = max(0, ci_runs_used - 1)
        reward -= 0.5 * extra_runs
    
    return reward

# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Task 1: Docs-Only PR

Scenario:
A PR that ONLY changes documentation (README.md, CHANGELOG.md) and comments/docstrings.
No functional code changed. The agent should recognize this and approve without unnecessary CI runs.

Optimal Path: inspect_diff → make_decision(MERGE)
Optimal CI Runs: 0
Optimal Reward: +5.0

Bad Path: Run CI unnecessarily
Reward Penalty: -0.5 per extra CI run
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
# TASK 1 SCENARIO DATA
# ============================================================

TASK1_SCENARIO = {
    "task_id": "task1",
    "title": "Docs-Only PR - No Functional Changes",
    "difficulty": "easy",  # Progressive difficulty: easy
    
    "pr": PullRequest(
        pr_id="pr_001",
        title="Update documentation and examples",
        description="""
        This PR updates the project documentation to improve clarity:
        - Revised README.md with better installation instructions
        - Updated CHANGELOG.md with latest release notes
        - Improved docstrings in src/utils.py for the helper functions
        
        No code logic has been changed. All modifications are purely textual.
        """,
        author="alice@company.com",
        target_branch="main",
        files_changed=[
            "README.md",
            "CHANGELOG.md",
            "src/utils.py",  # Only docstrings changed
        ]
    ),
    
    "repo_context": RepositoryContext(
        repo_name="awesome-project",
        repo_url="https://github.com/company/awesome-project",
        main_language="python",
        has_ci=True,
        critical_modules=["src/core.py", "src/api.py"],
    ),
    
    "budget": Budget(
        ci_runs=5,
        step_limit=10,
    ),
    
    "full_diff": """
--- a/README.md
+++ b/README.md
@@ -1,10 +1,15 @@
 # Awesome Project
 
-A great tool for task management.
+A great tool for task management and collaboration.
 
 ## Installation
 
+### Prerequisites
+- Python 3.10+
+- pip or uv
+
 Install via pip:
 ```
-pip install awesome-project
+pip install awesome-project>=1.0.0
 ```
 
@@ -12,6 +17,12 @@ pip install awesome-project
 Simply import and use:
 ```python
 from awesome_project import Manager
 manager = Manager()
+
+# See docs/ directory for full examples
 results = manager.process(data)
 ```

--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -1,8 +1,20 @@
 # Changelog
 
+## [1.5.0] - 2024-04-08
+
+### Added
+- Better error messages for common failures
+- New example scripts in examples/ directory
+- Improved API documentation
+
+### Changed
+- Updated dependencies to latest versions
+
+### Fixed
+- Minor typos in docstrings
+
 ## [1.4.9] - 2024-03-15
 
 ### Fixed
 - Security patch for XML parsing

--- a/src/utils.py
+++ b/src/utils.py
@@ -10,6 +10,14 @@ def validate_input(data):
+    \"\"\"
+    Validate input data structure.
+    
+    Args:
+        data: Input data to validate
+        
+    Returns:
+        bool: True if valid, False otherwise
+    \"\"\"
     if not isinstance(data, dict):
         return False
     return "required_key" in data

@@ -18,6 +26,14 @@ def transform_data(data):
+    \"\"\"
+    Transform raw data into canonical format.
+    
+    Args:
+        data: Raw input data
+        
+    Returns:
+        dict: Transformed data
+    \"\"\"
     return {
         "type": data.get("type", "unknown"),
         "value": data.get("value"),
""",
    
    # Tool responses are pre-computed, stateless
    "tool_responses": {
        "inspect_diff": {
            "output": """
Changes Summary:
- README.md: Updated installation instructions and added prerequisites section (+48 lines)
- CHANGELOG.md: Added new v1.5.0 release notes (+20 lines)  
- src/utils.py: Added docstrings to helper functions (+20 lines)

Analysis:
⚠️  Only documentation and docstring changes detected.
✓ No functional code modified.
✓ No logic changes.
✓ Safe to approve without testing.
            """,
            "is_docs_only": True,
            "has_code_changes": False,
        },
        
        "run_ci": {
            "status": "PASSED",
            "test_count": 94,
            "coverage": 87.5,
            "failure_reason": "",
            "error_location": None,
            "output": """
Running CI pipeline...
✓ Linting: 0 issues
✓ Type checking: 0 errors
✓ Unit tests: 94/94 passed in 23.45s
✓ Integration tests: 8/8 passed in 12.93s
✓ Coverage: 87.5%

All checks passed!
            """,
        }
    }
}


# ============================================================
# REWARD CALCULATION FOR TASK 1
# ============================================================

def calculate_task1_reward(verdict: str, ci_runs_used: int, justification: str = "") -> float:
    """
    Calculate reward for Task 1 (Docs-Only PR).
    
    Optimal strategy: inspect_diff → make_decision(MERGE)
    - Should recognize no functional code changed
    - Should NOT run CI (wastes budget on zero-risk PR)
    
    Args:
        verdict: MERGE, REQUEST_CHANGES, or BLOCK
        ci_runs_used: How many CI runs the agent called
        justification: Agent's reasoning for decision
        
    Returns:
        float: Reward value (can be negative)
    """
    
    # Base verdict reward
    if verdict == "MERGE":
        reward = 5.0  # Correct decision
    elif verdict == "REQUEST_CHANGES":
        reward = -1.0  # Too conservative, docs are fine
    else:  # BLOCK
        reward = -3.0  # Way too conservative
    
    # Penalize unnecessary CI runs
    # This is docs-only: running CI is wasteful
    ci_cost = 0.5 * ci_runs_used
    reward -= ci_cost
    
    return reward

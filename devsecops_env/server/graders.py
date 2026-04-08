# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Reward calculation logic for all tasks.

Graders are pure functions that compute rewards based on:
- Task ID
- Agent's decision (verdict)
- Resources used (CI runs)
- Work done (code patched, etc)

These functions are decoupled from the environment for easy testing.
"""

from typing import Optional, Dict, Any


# ============================================================
# TASK 1: DOCS-ONLY PR
# ============================================================

def grade_task1(
    verdict: str,
    ci_runs_used: int = 0,
    justification: str = "",
) -> float:
    """
    Grade Task 1: Docs-Only PR.
    
    Goal: Recognize that ONLY documentation changed, approve without CI.
    
    Optimal path:
    - inspect_diff (detects docs-only)
    - make_decision(MERGE)
    - reward: 5.0
    
    Penalties:
    - Unnecessary CI runs: -0.5 per run
    - Wrong verdict: significant penalty
    
    Args:
        verdict: "MERGE", "REQUEST_CHANGES", or "BLOCK"
        ci_runs_used: Number of times agent ran CI
        justification: Agent's reasoning
        
    Returns:
        float: Reward score
    """
    
    # Base verdict scoring
    if verdict == "MERGE":
        reward = 5.0  # Correct! Docs are fine
    elif verdict == "REQUEST_CHANGES":
        reward = -1.0  # Too conservative but not catastrophic
    else:  # BLOCK
        reward = -3.0  # Way too conservative
    
    # Penalize wasted CI on docs-only PR
    reward -= 0.5 * ci_runs_used
    
    return reward


# ============================================================
# TASK 2: SILENT API RENAME
# ============================================================

def grade_task2(
    verdict: str,
    ci_runs_used: int = 0,
    code_patched: bool = False,
    justification: str = "",
) -> float:
    """
    Grade Task 2: Silent API Rename (httpx 0.28.0).
    
    Goal: Detect breaking change, fix code, verify fix, approve.
    
    Optimal path:
    1. inspect_diff (sees version bump)
    2. run_ci(unit_only) - FAILS with AttributeError
    3. query_package_registry - confirms legitimate library
    4. patch_code - changes client.send → client.request
    5. run_ci(unit_only) - PASSES
    6. make_decision(MERGE)
    - Optimal ci_runs: 2
    - reward: 5.0 (correct verdict) + 2.0 (patching bonus) = 7.0
    
    Key insights:
    - If MERGE without patching: -3.0 (merged broken code)
    - If BLOCK: -1.0 (too conservative, legitimate dependency)
    - Penalizes >2 CI runs: -0.5 per extra
    
    Args:
        verdict: "MERGE", "REQUEST_CHANGES", or "BLOCK"
        ci_runs_used: Total CI executions
        code_patched: Did agent successfully fix the code?
        justification: Reasoning
        
    Returns:
        float: Reward score
    """
    
    # Base verdict scoring
    if verdict == "MERGE":
        if code_patched:
            reward = 5.0 + 2.0  # Correct decision with fix
        else:
            reward = -3.0  # CRITICAL: merged broken code!
    
    elif verdict == "REQUEST_CHANGES":
        if code_patched:
            reward = 2.0  # Acceptable but not finalized
        else:
            reward = 1.0  # Lazy - identified issue but didn't fix
    
    else:  # BLOCK
        reward = -1.0  # Too conservative for legitimate bump
    
    # Penalize extra CI runs
    if code_patched:
        # Optimal path uses 2 CI runs: one to detect failure, one to verify fix
        optimal_ci = 2
        extra_runs = max(0, ci_runs_used - optimal_ci)
        reward -= 0.5 * extra_runs
    else:
        # Without patching, minimal CI needed
        optimal_ci = 1
        extra_runs = max(0, ci_runs_used - optimal_ci)
        reward -= 0.5 * extra_runs
    
    return reward


# ============================================================
# TASK 3: POISONED PACKAGE
# ============================================================

def grade_task3(
    verdict: str,
    ci_runs_used: int = 0,
    justification: str = "",
) -> float:
    """
    Grade Task 3: Poisoned Package (crytpoutils supply chain attack).
    
    Goal: DETECT malware in package metadata/code, BLOCK it, AVOID CI.
    
    Optimal path:
    1. inspect_diff - sees new version, DETECTS subprocess exfiltration
    2. query_package_registry - sees new 3-day-old maintainer, ownership transfer
    3. make_decision(BLOCK)
    - Optimal ci_runs: 0 (CRITICAL: running CI executes malware!)
    - reward: 5.0
    
    Key insights:
    - MERGE = catastrophic failure: -3.0
    - BLOCK = correct: +5.0
    - REQUEST_CHANGES = wrong: -1.0
    - Every CI run = -1.0 (executes exfiltration attack)
    
    Args:
        verdict: "MERGE", "REQUEST_CHANGES", or "BLOCK"
        ci_runs_used: Total CI executions (should be 0!)
        justification: Reasoning
        
    Returns:
        float: Reward score
    """
    
    # Base verdict scoring
    if verdict == "BLOCK":
        reward = 5.0  # Correct! Blocked malware
    elif verdict == "MERGE":
        reward = -3.0  # Merged malware - worst possible
    else:  # REQUEST_CHANGES
        reward = -1.0  # Wrong - this is malware, not a fixable issue
    
    # CRITICAL PENALTY: Running CI executes the malware
    # Each run is catastrophic
    reward -= 1.0 * ci_runs_used
    
    return reward


# ============================================================
# UNIFIED GRADER
# ============================================================

def compute_reward(
    task_id: str,
    verdict: str,
    ci_runs_used: int = 0,
    code_patched: bool = False,
    justification: str = "",
) -> float:
    """
    Unified reward calculation function.
    
    Routes to task-specific grader based on task_id.
    
    Args:
        task_id: "task1", "task2", or "task3"
        verdict: PR decision
        ci_runs_used: CI runs executed
        code_patched: (Task 2 only) Did agent patch code?
        justification: Agent's reasoning
        
    Returns:
        float: Reward value (can be negative)
        
    Raises:
        ValueError: If task_id not recognized
    """
    
    if task_id == "task1":
        return grade_task1(verdict, ci_runs_used, justification)
    
    elif task_id == "task2":
        return grade_task2(verdict, ci_runs_used, code_patched, justification)
    
    elif task_id == "task3":
        return grade_task3(verdict, ci_runs_used, justification)
    
    else:
        raise ValueError(f"Unknown task_id: {task_id}")


# ============================================================
# REWARD ANALYSIS UTILITIES
# ============================================================

def get_optimal_reward(task_id: str) -> float:
    """Get theoretical maximum reward for a task."""
    
    if task_id == "task1":
        return 5.0
    elif task_id == "task2":
        return 7.0  # 5.0 (verdict) + 2.0 (patch bonus)
    elif task_id == "task3":
        return 5.0
    else:
        raise ValueError(f"Unknown task_id: {task_id}")


def get_task_specs(task_id: str) -> Dict[str, Any]:
    """Get specification for a task (optimal path, steps, etc)."""
    
    specs = {
        "task1": {
            "title": "Docs-Only PR",
            "optimal_steps": 2,
            "optimal_ci_runs": 0,
            "optimal_reward": 5.0,
            "optimal_path": [
                "inspect_diff → detects docs-only changes",
                "make_decision(MERGE) → approves",
            ],
        },
        "task2": {
            "title": "Silent API Rename",
            "optimal_steps": 6,
            "optimal_ci_runs": 2,
            "optimal_reward": 7.0,
            "optimal_path": [
                "inspect_diff → detects version bump, hints at breaking change",
                "run_ci(unit_only) → FAILS with AttributeError",
                "query_package_registry → confirms legitimate library",
                "patch_code → fixes client.send → client.request",
                "run_ci(unit_only) → PASSES",
                "make_decision(MERGE) → completes with patch",
            ],
        },
        "task3": {
            "title": "Poisoned Package",
            "optimal_steps": 3,
            "optimal_ci_runs": 0,
            "optimal_reward": 5.0,
            "optimal_path": [
                "inspect_diff → detects malware in setup.py",
                "query_package_registry → sees new maintainer, ownership transfer",
                "make_decision(BLOCK) → prevents attack",
            ],
        },
    }
    
    if task_id not in specs:
        raise ValueError(f"Unknown task_id: {task_id}")
    
    return specs[task_id].copy()


# ============================================================
# NORMALIZED GRADER (Required for RL Training)
# ============================================================

def get_reward_range(task_id: str) -> tuple:
    """
    Get min and max reward bounds for a task.
    
    Mandatory per competition spec: normalize rewards to [0, 1].
    
    Returns:
        (min_reward, max_reward) tuple
    """
    
    # Reward ranges determined by task grading logic
    ranges = {
        "task1": (-3.0, 5.0),      # Min: BLOCK, Max: MERGE
        "task2": (-3.0, 7.0),      # Min: MERGE broken, Max: MERGE patched
        "task3": (-3.0, 5.0),      # Min: MERGE malware, Max: BLOCK malware
    }
    
    if task_id not in ranges:
        raise ValueError(f"Unknown task_id: {task_id}")
    
    return ranges[task_id]


def normalize_reward(task_id: str, raw_reward: float) -> float:
    """
    Normalize raw reward to [0, 1] range.
    
    This is MANDATORY per competition spec:
    "The environment must include a grader that returns a value strictly between 0 and 1."
    
    Formula: normalized = (raw - min) / (max - min)
    
    Args:
        task_id: "task1", "task2", or "task3"
        raw_reward: Raw reward score (can be negative/>1)
        
    Returns:
        float: Normalized reward in [0, 1] range
    """
    
    min_reward, max_reward = get_reward_range(task_id)
    
    # Clamp to valid range first
    clamped = max(min_reward, min(max_reward, raw_reward))
    
    # Normalize to [0, 1]
    normalized = (clamped - min_reward) / (max_reward - min_reward)
    
    return normalized


def compute_normalized_reward(
    task_id: str,
    verdict: str,
    ci_runs_used: int = 0,
    code_patched: bool = False,
    justification: str = "",
) -> float:
    """
    Compute NORMALIZED reward [0, 1] for RL training.
    
    Requirements per competition context.md:
    "The environment must include a grader that returns a value strictly between 0 and 1.
     This is a mandatory requirement for the environment to be considered feasible for learning."
    
    Args:
        task_id: "task1", "task2", or "task3"
        verdict: PR decision
        ci_runs_used: CI runs executed
        code_patched: (Task 2 only) Did agent patch code?
        justification: Agent's reasoning
        
    Returns:
        float: Normalized reward in [0, 1] range
        
    Raises:
        ValueError: If task_id not recognized
    """
    
    # Compute raw reward
    raw_reward = compute_reward(
        task_id=task_id,
        verdict=verdict,
        ci_runs_used=ci_runs_used,
        code_patched=code_patched,
        justification=justification,
    )
    
    # Normalize to [0, 1]
    normalized = normalize_reward(task_id, raw_reward)
    
    return normalized


__all__ = [
    "grade_task1",
    "grade_task2",
    "grade_task3",
    "compute_reward",
    "compute_normalized_reward",
    "normalize_reward",
    "get_reward_range",
    "get_optimal_reward",
    "get_task_specs",
]

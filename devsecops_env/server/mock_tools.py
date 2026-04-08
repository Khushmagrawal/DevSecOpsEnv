# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Tool dispatcher and implementations for DevSecOps environment.

This module handles all tool execution:
- inspect_diff: Analyze PR changes
- run_ci: Execute CI pipeline with state-dependent results
- patch_code: Apply code fixes (stateful for task2)
- query_package_registry: Look up package metadata
- search_vuln_db: Search vulnerability databases
- make_decision: Terminal action

Key Design:
- Tools are pure functions or semi-stateful (modifications through env state dict)
- Tool results are deterministic based on scenario + environment state
- State mutations (like code_patched) persist across tool calls in the same episode
"""

from typing import Dict, Any, Optional, Tuple
import copy
import sys
from pathlib import Path

try:
    from devsecops_env.models import (
        DevsecopsAction,
        CITestResult,
        CIResult,
        PackageMetadata,
        VulnerabilityReport,
    )
except ImportError:
    # Fallback for direct import
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models import (
        DevsecopsAction,
        CITestResult,
        CIResult,
        PackageMetadata,
        VulnerabilityReport,
    )


# ============================================================
# TOOL IMPLEMENTATION: inspect_diff
# ============================================================

def tool_inspect_diff(
    action: DevsecopsAction,
    scenario: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """
    Inspect the PR diff to understand what's changing.
    
    Returns the full diff text and analysis results.
    
    Args:
        action: Action with pr_id (unused for now, only one PR per scenario)
        scenario: Current scenario data
        
    Returns:
        (output_text, metadata_dict)
    """
    
    tool_output = scenario["tool_responses"]["inspect_diff"]["output"]
    metadata = {key: val for key, val in scenario["tool_responses"]["inspect_diff"].items()
                if key != "output"}
    
    return tool_output, metadata


# ============================================================
# TOOL IMPLEMENTATION: run_ci
# ============================================================

def tool_run_ci(
    action: DevsecopsAction,
    scenario: Dict[str, Any],
    environment_state: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """
    Run CI pipeline. Results depend on:
    - Which task we're in
    - Whether Task 2 code has been patched
    - Whether Task 3 would execute malware
    
    Args:
        action: Action with scope ("unit_only" or "full")
        scenario: Current scenario data
        environment_state: Mutable dict with internal state (task2_code_patched, etc)
        
    Returns:
        (output_text, metadata_dict)
    """
    
    task_id = scenario["task_id"]
    scope = action.scope or "unit_only"
    
    # Task 1: Always passes, no state dependency
    if task_id == "task1":
        response = scenario["tool_responses"]["run_ci"]
        return response["output"], {
            "status": response["status"],
            "test_count": response["test_count"],
            "coverage": response["coverage"],
        }
    
    # Task 2: Result depends on whether code was patched
    elif task_id == "task2":
        code_patched = environment_state.get("task2_code_patched", False)
        
        if scope == "unit_only":
            if code_patched:
                response = scenario["tool_responses"]["run_ci_unit_only_after_patch"]
            else:
                response = scenario["tool_responses"]["run_ci_unit_only_before_patch"]
        else:  # scope == "full"
            if code_patched:
                response = scenario["tool_responses"]["run_ci_full_after_patch"]
            else:
                response = scenario["tool_responses"]["run_ci_full_before_patch"]
        
        return response["output"], {
            "status": response["status"],
            "test_count": response["test_count"],
            "coverage": response.get("coverage"),
            "error_location": response.get("error_location"),
        }
    
    # Task 3: Would execute malware - warn agent
    elif task_id == "task3":
        response = scenario["tool_responses"]["run_ci_would_execute_malware"]
        return response["output"], {
            "warning": "MALWARE WOULD EXECUTE",
            "status": "DO_NOT_RUN",
        }
    
    else:
        return "Unknown task", {}


# ============================================================
# TOOL IMPLEMENTATION: patch_code
# ============================================================

def tool_patch_code(
    action: DevsecopsAction,
    scenario: Dict[str, Any],
    environment_state: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """
    Apply a code patch. Only works for Task 2 (Silent API Rename).
    
    Validates that:
    1. old_code exists in the specified file
    2. The patch makes semantic sense for the breaking change
    
    For Task 2, if patch is valid, marks code_patched = True in environment_state.
    
    Args:
        action: Action with file, old_code, new_code
        scenario: Current scenario
        environment_state: Mutable dict where we track patch success
        
    Returns:
        (output_text, metadata_dict)
    """
    
    task_id = scenario["task_id"]
    
    if task_id != "task2":
        return (
            "❌ Patching not supported for this task",
            {"success": False, "reason": "not_applicable"}
        )
    
    file_path = action.file or "src/api_client.py"
    old_code = action.old_code or ""
    new_code = action.new_code or ""
    
    # For Task 2, the expected fix is:
    # OLD: client.send(httpx.Request('GET', url))
    # NEW: client.request('GET', url)
    
    code_snippet = scenario.get("code_snippet_before", "")
    
    # Check if old_code roughly matches what we expect
    is_valid_patch = (
        "client.send" in old_code and
        "client.request" in new_code and
        "httpx" in old_code
    )
    
    if is_valid_patch:
        # Mark as patched in environment state
        environment_state["task2_code_patched"] = True
        
        output = f"""
✓ Code patch applied successfully!

File: {file_path}

Before:
{old_code[:100]}...

After:
{new_code[:100]}...

The code now uses the new httpx 0.28.0 API.
Ready to re-run CI tests to verify fix.
        """
        return output, {
            "success": True,
            "file": file_path,
            "patched": True,
        }
    else:
        output = f"""
❌ Patch validation failed.

The provided patch doesn't match the expected fix pattern.

Expected pattern:
- OLD: Should contain 'client.send(...)'
- NEW: Should contain 'client.request(...)'

Provided:
- OLD: {old_code[:80]}...
- NEW: {new_code[:80]}...

Hint: Use the new httpx API instead of deprecated send() method.
See: https://httpx.readthedocs.io/en/latest/changelog/
        """
        return output, {
            "success": False,
            "reason": "invalid_patch",
            "expected_pattern": "client.send -> client.request",
        }


# ============================================================
# TOOL IMPLEMENTATION: query_package_registry
# ============================================================

def tool_query_package_registry(
    action: DevsecopsAction,
    scenario: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """
    Query package metadata from registry (PyPI, etc).
    
    Returns metadata about the package version that helps detect:
    - Suspicious maintainers (Task 3)
    - Legitimate updates (Task 2)
    
    Args:
        action: Action with pkg, version
        scenario: Current scenario
        
    Returns:
        (output_text, metadata_dict)
    """
    
    pkg = action.pkg or ""
    version = action.version or ""
    
    # For all tasks, return the registry response from scenario
    if "query_package_registry" in scenario["tool_responses"]:
        response = scenario["tool_responses"]["query_package_registry"]
        return response["output"], {
            "package": response.get("package_name"),
            "version": response.get("version"),
            "maintainer": response.get("maintainer_username"),
            "maintainer_account_age_days": response.get("maintainer_account_age_days"),
            "downloads_24h": response.get("downloads_last_24h"),
            "ownership_transfer": response.get("ownership_transfer"),
            "notes": response.get("notes"),
        }
    else:
        return f"No registry data for {pkg} {version}", {}


# ============================================================
# TOOL IMPLEMENTATION: search_vuln_db
# ============================================================

def tool_search_vuln_db(
    action: DevsecopsAction,
    scenario: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """
    Search vulnerability databases (CVE, OSV, etc).
    
    Returns known vulnerabilities or notes if package is too new/unknown.
    
    Args:
        action: Action with pkg, version
        scenario: Current scenario
        
    Returns:
        (output_text, metadata_dict)
    """
    
    pkg = action.pkg or ""
    version = action.version or ""
    
    if "search_vuln_db" in scenario["tool_responses"]:
        response = scenario["tool_responses"]["search_vuln_db"]
        return response["output"], {
            "cve_ids": response.get("cve_ids", []),
            "osv_entries": response.get("osv_entries", []),
            "critical": response.get("critical", False),
            "suspicious_patterns": response.get("suspicious_patterns", []),
            "note": response.get("note", ""),
        }
    else:
        return f"No vulnerability data for {pkg} {version}", {}


# ============================================================
# TOOL IMPLEMENTATION: make_decision
# ============================================================

def tool_make_decision(
    action: DevsecopsAction,
    scenario: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """
    Terminal action: Make final PR decision.
    
    Sets done=True and marks decision in environment state.
    
    Args:
        action: Action with verdict, justification
        scenario: Current scenario
        
    Returns:
        (output_text, metadata_dict)
    """
    
    verdict = action.verdict or "REQUEST_CHANGES"
    justification = action.justification or "(no justification provided)"
    
    # Handle both dict and Pydantic model scenarios
    pr = scenario.get("pr") or scenario["pr"]
    if isinstance(pr, dict):
        pr_id = pr.get("pr_id", "unknown")
        pr_title = pr.get("title", "unknown")
    else:
        pr_id = pr.pr_id
        pr_title = pr.title
    
    output = f"""
═══════════════════════════════════════════════════════════
                     FINAL DECISION MADE
═══════════════════════════════════════════════════════════

PR: {pr_id}
Title: {pr_title}

Verdict: {verdict}

Reasoning:
{justification}

Episode now terminates.
Reward will be calculated based on this decision.
═══════════════════════════════════════════════════════════
    """
    
    return output, {
        "decision_made": True,
        "verdict": verdict,
        "justification": justification,
    }


# ============================================================
# TOOL DISPATCHER
# ============================================================

def dispatch_tool(
    action: DevsecopsAction,
    scenario: Dict[str, Any],
    environment_state: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """
    Main dispatcher that routes actions to tool handlers.
    
    Args:
        action: DevsecopsAction with tool_name and parameters
        scenario: Current scenario loaded from registry
        environment_state: Mutable dict for per-episode state tracking
        
    Returns:
        (tool_output_text, tool_result_metadata)
        
    Raises:
        ValueError: If tool_name not recognized
    """
    
    tool_name = action.tool_name
    
    if tool_name == "inspect_diff":
        return tool_inspect_diff(action, scenario)
    
    elif tool_name == "run_ci":
        return tool_run_ci(action, scenario, environment_state)
    
    elif tool_name == "patch_code":
        return tool_patch_code(action, scenario, environment_state)
    
    elif tool_name == "query_package_registry":
        return tool_query_package_registry(action, scenario)
    
    elif tool_name == "search_vuln_db":
        return tool_search_vuln_db(action, scenario)
    
    elif tool_name == "make_decision":
        return tool_make_decision(action, scenario)
    
    else:
        raise ValueError(f"Unknown tool: {tool_name}")


__all__ = [
    "tool_inspect_diff",
    "tool_run_ci",
    "tool_patch_code",
    "tool_query_package_registry",
    "tool_search_vuln_db",
    "tool_make_decision",
    "dispatch_tool",
]

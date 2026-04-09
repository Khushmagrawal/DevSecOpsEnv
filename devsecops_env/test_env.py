#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Test suite for DevSecOps environment.

These tests validate:
1. Scenario loading and data integrity
2. Tool dispatcher correctness
3. Reward calculation accuracy
4. End-to-end episode flow
5. State transitions

Run with: pytest test_env.py -v
Or directly: python test_env.py
"""

import sys
import io
from pathlib import Path

# Ensure UTF-8 output on Windows (avoids cp1252 encoding errors with ✓/✗)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from devsecops_env.models import DevsecopsAction, DevsecopsObservation
from devsecops_env.server.scenarios import (
    load_scenario,
    get_available_tasks,
    get_reward_calculator,
)
from devsecops_env.server.mock_tools import dispatch_tool
from devsecops_env.server.graders import (
    compute_reward,
    get_optimal_reward,
    get_task_specs,
)
from devsecops_env.server.devsecops_env_environment import DevSecOpsEnvironment


# ============================================================
# TEST 1: Scenario Loading
# ============================================================

def test_scenario_loading():
    """Test that all scenarios load correctly."""
    print("\n" + "="*60)
    print("TEST 1: Scenario Loading")
    print("="*60)
    
    tasks = get_available_tasks()
    assert len(tasks) == 3, f"Expected 3 tasks, got {len(tasks)}"
    assert "task1" in tasks
    assert "task2" in tasks
    assert "task3" in tasks
    
    for task_id in tasks:
        scenario = load_scenario(task_id)
        assert scenario["task_id"] == task_id
        assert "pr" in scenario
        assert "repo_context" in scenario
        assert "budget" in scenario
        assert "tool_responses" in scenario
        print(f"✓ Task {task_id} loaded: {scenario['title']}")
    
    print("✓ All scenarios loaded successfully\n")


# ============================================================
# TEST 2: Tool Dispatcher
# ============================================================

def test_tool_dispatcher():
    """Test that tools execute and return reasonable outputs."""
    print("\n" + "="*60)
    print("TEST 2: Tool Dispatcher")
    print("="*60)
    
    scenario = load_scenario("task1")
    env_state = {}
    
    # Test inspect_diff
    action = DevsecopsAction(tool_name="inspect_diff")
    output, metadata = dispatch_tool(action, scenario, env_state)
    assert "output" in output or output is not None
    assert isinstance(metadata, dict)
    print(f"✓ inspect_diff: {len(output)} chars output, {len(metadata)} metadata fields")
    
    # Test run_ci
    action = DevsecopsAction(tool_name="run_ci", scope="unit_only")
    output, metadata = dispatch_tool(action, scenario, env_state)
    assert output is not None
    print(f"✓ run_ci: {len(output)} chars output")
    
    # Test query_package_registry
    action = DevsecopsAction(tool_name="query_package_registry", pkg="test", version="1.0.0")
    output, metadata = dispatch_tool(action, scenario, env_state)
    assert output is not None
    print(f"✓ query_package_registry: {len(output)} chars output")
    
    # Test search_vuln_db
    action = DevsecopsAction(tool_name="search_vuln_db", pkg="test", version="1.0.0")
    output, metadata = dispatch_tool(action, scenario, env_state)
    assert output is not None
    print(f"✓ search_vuln_db: {len(output)} chars output")
    
    # Test make_decision
    action = DevsecopsAction(
        tool_name="make_decision",
        verdict="MERGE",
        justification="Test decision"
    )
    output, metadata = dispatch_tool(action, scenario, env_state)
    assert "FINAL DECISION" in output
    assert metadata.get("verdict") == "MERGE"
    print(f"✓ make_decision: Verdict={metadata['verdict']}")
    
    print("✓ All tools dispatch correctly\n")


# ============================================================
# TEST 3: Task 2 Code Patching
# ============================================================

def test_task2_code_patching():
    """Test that Task 2 code patching affects CI results."""
    print("\n" + "="*60)
    print("TEST 3: Task 2 Code Patching State Tracking")
    print("="*60)
    
    scenario = load_scenario("task2")
    env_state = {}
    
    # Before patching: CI should fail
    action = DevsecopsAction(tool_name="run_ci", scope="unit_only")
    output_before, meta_before = dispatch_tool(action, scenario, env_state)
    assert "FAILED" in output_before or "AttributeError" in output_before
    print("✓ Before patch: CI FAILS with AttributeError")
    
    # Patch the code
    action = DevsecopsAction(
        tool_name="patch_code",
        file="src/api_client.py",
        old_code="await client.send(httpx.Request('GET', url))",
        new_code="await client.request('GET', url)"
    )
    output_patch, meta_patch = dispatch_tool(action, scenario, env_state)
    assert meta_patch.get("success") == True
    print("✓ Patch succeeded")
    
    # After patching: CI should pass
    action = DevsecopsAction(tool_name="run_ci", scope="unit_only")
    output_after, meta_after = dispatch_tool(action, scenario, env_state)
    assert "passed" in output_after.lower()
    assert "42" in output_after  # 42 tests
    print("✓ After patch: CI PASSES")
    
    print("✓ Code patching state tracking works correctly\n")


# ============================================================
# TEST 4: Task 3 Malware Detection
# ============================================================

def test_task3_malware_detection():
    """Test that Task 3 detects malware in setup.py."""
    print("\n" + "="*60)
    print("TEST 4: Task 3 Malware Detection")
    print("="*60)
    
    scenario = load_scenario("task3")
    env_state = {}
    
    # Inspect diff should detect malware
    action = DevsecopsAction(tool_name="inspect_diff")
    output, metadata = dispatch_tool(action, scenario, env_state)
    assert "malware" in output.lower() or "suspicious" in output.lower()
    assert metadata.get("malware_detected") == True
    print("✓ inspect_diff detects malware")
    
    # Registry query should show suspicious maintainer
    action = DevsecopsAction(
        tool_name="query_package_registry",
        pkg="cryptoutils",
        version="2.1.5"
    )
    output, metadata = dispatch_tool(action, scenario, env_state)
    assert metadata.get("maintainer_account_age_days") == 3
    assert metadata.get("ownership_transfer") == True
    print("✓ query_package_registry shows new maintainer (3 days old)")
    
    # Running CI would execute malware
    action = DevsecopsAction(tool_name="run_ci", scope="unit_only")
    output, metadata = dispatch_tool(action, scenario, env_state)
    assert "CRITICAL ERROR" in output or "NEVER run CI" in output.upper()
    print("✓ run_ci warns about malware execution")
    
    print("✓ Malware detection works correctly\n")


# ============================================================
# TEST 5: Reward Calculation
# ============================================================

def test_reward_calculation():
    """Test that reward functions compute correct values."""
    print("\n" + "="*60)
    print("TEST 5: Reward Calculation")
    print("="*60)
    
    # Task 1: Docs-only
    reward_optimal = compute_reward("task1", verdict="MERGE", ci_runs_used=0)
    assert reward_optimal == 5.0, f"Task1 optimal should be 5.0, got {reward_optimal}"
    
    reward_wasted = compute_reward("task1", verdict="MERGE", ci_runs_used=3)
    assert reward_wasted < reward_optimal, "Task1 with wasted CI should be less"
    assert reward_wasted == 3.5, f"Task1 with 3 CI runs should be 3.5, got {reward_wasted}"
    print(f"✓ Task1: Optimal={reward_optimal}, With 3 CI runs={reward_wasted}")
    
    # Task 2: Silent API Rename
    reward_full_opt = compute_reward("task2", verdict="MERGE", ci_runs_used=2, code_patched=True)
    assert reward_full_opt == 7.0, f"Task2 optimal should be 7.0, got {reward_full_opt}"
    
    reward_merged_broken = compute_reward("task2", verdict="MERGE", ci_runs_used=0, code_patched=False)
    assert reward_merged_broken == -3.0, f"Task2 merged broken should be -3.0, got {reward_merged_broken}"
    print(f"✓ Task2: Optimal={reward_full_opt}, Merged broken={reward_merged_broken}")
    
    # Task 3: Poisoned Package
    reward_blocked = compute_reward("task3", verdict="BLOCK", ci_runs_used=0)
    assert reward_blocked == 5.0, f"Task3 blocked should be 5.0, got {reward_blocked}"
    
    reward_merged_malware = compute_reward("task3", verdict="MERGE", ci_runs_used=0)
    assert reward_merged_malware == -3.0, f"Task3 merged malware should be -3.0, got {reward_merged_malware}"
    
    reward_ci_malware = compute_reward("task3", verdict="BLOCK", ci_runs_used=2)
    assert reward_ci_malware < reward_blocked, "Task3 with CI runs should be less"
    assert reward_ci_malware == 3.0, f"Task3 blocked but 2 CI runs should be 3.0, got {reward_ci_malware}"
    print(f"✓ Task3: Blocked={reward_blocked}, Merged malware={reward_merged_malware}, With 2 CI runs={reward_ci_malware}")
    
    print("✓ All reward calculations correct\n")


# ============================================================
# TEST 6: End-to-End Episode Flow
# ============================================================

def test_episode_task1():
    """Test a complete optimal episode for Task 1."""
    print("\n" + "="*60)
    print("TEST 6: End-to-End Episode - Task 1 (Optimal)")
    print("="*60)
    
    env = DevSecOpsEnvironment()
    obs = env.reset(options={"task": "task1"})
    
    assert obs.task_id == "task1"
    assert obs.step_count == 0
    assert obs.episode_reward == 0.0
    assert obs.budget.ci_runs == 5
    print(f"✓ Reset: Task={obs.task_id}, Step=0, Budget.ci_runs={obs.budget.ci_runs}")
    
    # Inspect diff
    action = DevsecopsAction(tool_name="inspect_diff")
    obs = env.step(action)
    assert obs.step_count == 1
    assert "docs" in obs.last_tool_output.lower() or "no functional" in obs.last_tool_output.lower()
    assert obs.budget.ci_runs == 5  # No CI run, budget unchanged
    print(f"✓ Step 1 (inspect_diff): Output mentions docs-only")
    
    # Make decision
    action = DevsecopsAction(
        tool_name="make_decision",
        verdict="MERGE",
        justification="Documentation changes only, no functional code modified"
    )
    obs = env.step(action)
    assert obs.done == True
    assert obs.episode_reward == 5.0  # Optimal reward
    assert obs.step_count == 2
    print(f"✓ Step 2 (make_decision): Done={obs.done}, Reward={obs.episode_reward}")
    
    summary = env.get_episode_summary()
    assert summary["verdict"] == "MERGE"
    assert summary["ci_runs_used"] == 0
    assert summary["episode_reward"] == 5.0
    print(f"✓ Episode summary: ci_runs=0, verdict=MERGE, reward=5.0\n")


def test_episode_task2():
    """Test a complete optimal episode for Task 2."""
    print("="*60)
    print("TEST 7: End-to-End Episode - Task 2 (Optimal)")
    print("="*60)
    
    env = DevSecOpsEnvironment()
    obs = env.reset(options={"task": "task2"})
    
    assert obs.task_id == "task2"
    print(f"✓ Reset: Task={obs.task_id}")
    
    # Inspect diff
    action = DevsecopsAction(tool_name="inspect_diff")
    obs = env.step(action)
    print(f"✓ Step 1 (inspect_diff)")
    
    # Run CI before patch - should FAIL
    action = DevsecopsAction(tool_name="run_ci", scope="unit_only")
    obs = env.step(action)
    assert "FAILED" in obs.last_tool_output
    assert obs.budget.ci_runs == 4  # One CI run consumed
    print(f"✓ Step 2 (run_ci): FAILED, ci_runs={obs.budget.ci_runs}")
    
    # Patch code
    action = DevsecopsAction(
        tool_name="patch_code",
        file="src/api_client.py",
        old_code="await client.send(httpx.Request('GET', url))",
        new_code="await client.request('GET', url)"
    )
    obs = env.step(action)
    assert "successfully" in obs.last_tool_output.lower()
    print(f"✓ Step 3 (patch_code): Patch applied")
    
    # Run CI after patch - should PASS
    action = DevsecopsAction(tool_name="run_ci", scope="unit_only")
    obs = env.step(action)
    assert "passed" in obs.last_tool_output.lower()
    assert obs.budget.ci_runs == 3  # Second CI run consumed
    print(f"✓ Step 4 (run_ci): PASSED, ci_runs={obs.budget.ci_runs}")
    
    # Make decision
    action = DevsecopsAction(
        tool_name="make_decision",
        verdict="MERGE",
        justification="Fixed API usage for httpx 0.28.0, tests passing"
    )
    obs = env.step(action)
    assert obs.done == True
    assert obs.episode_reward == 7.0  # Optimal reward
    print(f"✓ Step 5 (make_decision): Done={obs.done}, Reward={obs.episode_reward}\n")


def test_episode_task3():
    """Test a complete optimal episode for Task 3."""
    print("="*60)
    print("TEST 8: End-to-End Episode - Task 3 (Optimal)")
    print("="*60)
    
    env = DevSecOpsEnvironment()
    obs = env.reset(options={"task": "task3"})
    
    assert obs.task_id == "task3"
    print(f"✓ Reset: Task={obs.task_id}")
    
    # Inspect diff - should detect malware
    action = DevsecopsAction(tool_name="inspect_diff")
    obs = env.step(action)
    assert "malware" in obs.last_tool_output.lower() or "suspicious" in obs.last_tool_output.lower()
    print(f"✓ Step 1 (inspect_diff): Malware detected")
    
    # Query registry - should show suspicious maintainer
    action = DevsecopsAction(
        tool_name="query_package_registry",
        pkg="cryptoutils",
        version="2.1.5"
    )
    obs = env.step(action)
    assert "NEW" in obs.last_tool_output or "3 days" in obs.last_tool_output
    print(f"✓ Step 2 (query_package_registry): Suspicious maintainer found")
    
    # Make decision - BLOCK
    action = DevsecopsAction(
        tool_name="make_decision",
        verdict="BLOCK",
        justification="New maintainer (3 days old), ownership transfer, subprocess exfiltration in setup.py"
    )
    obs = env.step(action)
    assert obs.done == True
    assert obs.episode_reward == 5.0  # Optimal reward
    assert obs.budget.ci_runs == 5  # Did NOT run CI on malware (budget still full)
    print(f"✓ Step 3 (make_decision): Done={obs.done}, Reward={obs.episode_reward}, ci_runs={obs.budget.ci_runs}\n")


# ============================================================
# RUN ALL TESTS
# ============================================================

def run_all_tests():
    """Run the complete test suite."""
    print("\n" + "=" * 60)
    print("DEVSECOPS ENVIRONMENT TEST SUITE")
    print("=" * 60)
    
    try:
        test_scenario_loading()
        test_tool_dispatcher()
        test_task2_code_patching()
        test_task3_malware_detection()
        test_reward_calculation()
        test_episode_task1()
        test_episode_task2()
        test_episode_task3()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60 + "\n")
        return True
        
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}\n")
        return False
    except Exception as e:
        print(f"\n[ERROR] ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
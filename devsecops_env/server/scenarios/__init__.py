# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Scenario registry and utilities for DevSecOps RL environment.

This module provides:
- SCENARIO_REGISTRY: Dictionary of all available scenarios
- load_scenario(): Function to load a scenario by task_id
- get_available_tasks(): List all task IDs
"""

import random
from typing import Dict, Any, Optional, List

from .task1 import TASK1_SCENARIO, calculate_task1_reward
from .task2 import TASK2_SCENARIO, calculate_task2_reward
from .task3 import TASK3_SCENARIO, calculate_task3_reward


# ============================================================
# SCENARIO REGISTRY
# ============================================================

SCENARIO_REGISTRY: Dict[str, Dict[str, Any]] = {
    "task1": TASK1_SCENARIO,
    "task2": TASK2_SCENARIO,
    "task3": TASK3_SCENARIO,
}

REWARD_CALCULATORS = {
    "task1": calculate_task1_reward,
    "task2": calculate_task2_reward,
    "task3": calculate_task3_reward,
}


# ============================================================
# SCENARIO LOADING FUNCTIONS
# ============================================================

def get_available_tasks() -> List[str]:
    """
    Get list of all available task IDs.
    
    Returns:
        List of task IDs: ["task1", "task2", "task3"]
    """
    return list(SCENARIO_REGISTRY.keys())


def load_scenario(task_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Load a scenario by task_id.
    
    If task_id is None, randomly selects one of the 3 tasks.
    
    Args:
        task_id: Which task to load. If None, randomly selects.
                 Must be one of: "task1", "task2", "task3"
    
    Returns:
        Deep copy of the scenario dictionary
        
    Raises:
        ValueError: If task_id is not recognized
        
    Example:
        >>> scenario = load_scenario("task1")
        >>> scenario["title"]
        "Docs-Only PR - No Functional Changes"
        
        >>> scenario = load_scenario()  # Random
        >>> task_id = scenario["task_id"]
    """
    
    if task_id is None:
        # Randomly select a task
        task_id = random.choice(get_available_tasks())
    
    if task_id not in SCENARIO_REGISTRY:
        available = get_available_tasks()
        raise ValueError(
            f"Unknown task_id '{task_id}'. "
            f"Available tasks: {available}"
        )
    
    # Return deep copy to avoid mutation of the registry
    import copy
    return copy.deepcopy(SCENARIO_REGISTRY[task_id])


def get_reward_calculator(task_id: str):
    """
    Get the reward calculation function for a task.
    
    Args:
        task_id: Task to get calculator for
        
    Returns:
        Callable reward function
        
    Raises:
        ValueError: If task_id not recognized
    """
    if task_id not in REWARD_CALCULATORS:
        raise ValueError(f"No reward calculator for task '{task_id}'")
    
    return REWARD_CALCULATORS[task_id]


# ============================================================
# SCENARIO DESCRIPTIONS
# ============================================================

SCENARIO_DESCRIPTIONS = {
    "task1": {
        "title": "Docs-Only PR",
        "complexity": "Easy",
        "optimal_steps": 2,
        "optimal_reward": 5.0,
        "key_skill": "Recognition - identify when code changes are absent",
    },
    "task2": {
        "title": "Silent API Rename",
        "complexity": "Medium",
        "optimal_steps": 6,
        "optimal_reward": 7.0,
        "key_skill": "Detection & Remediation - fix breaking dependency changes",
    },
    "task3": {
        "title": "Poisoned Package",
        "complexity": "Hard",
        "optimal_steps": 3,
        "optimal_reward": 5.0,
        "key_skill": "Security - detect supply chain attacks",
    },
}


def get_scenario_description(task_id: str) -> Dict[str, Any]:
    """
    Get human-readable description of a scenario.
    
    Args:
        task_id: Task ID
        
    Returns:
        Description dictionary
    """
    if task_id not in SCENARIO_DESCRIPTIONS:
        raise ValueError(f"No description for task '{task_id}'")
    
    return SCENARIO_DESCRIPTIONS[task_id].copy()


__all__ = [
    "SCENARIO_REGISTRY",
    "REWARD_CALCULATORS",
    "get_available_tasks",
    "load_scenario",
    "get_reward_calculator",
    "get_scenario_description",
]

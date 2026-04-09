# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
DevSecOps Environment Implementation.

Core state machine for the PR gatekeeper RL environment.
Manages episode state, tool execution, reward calculation, and episode transitions.
"""

from uuid import uuid4
from typing import Dict, Any, Optional
import copy

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

import sys
from pathlib import Path

try:
    from devsecops_env.models import (
        DevsecopsAction,
        DevsecopsObservation,
        PullRequest,
        RepositoryContext,
        Budget,
        ToolUseRecord,
    )
except ImportError:
    # Fallback for direct import
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models import (
        DevsecopsAction,
        DevsecopsObservation,
        PullRequest,
        RepositoryContext,
        Budget,
        ToolUseRecord,
    )
from .scenarios import load_scenario, get_reward_calculator
from .mock_tools import dispatch_tool
from .graders import compute_reward


class DevSecOpsEnvironment(Environment):
    """
    DevSecOps Gatekeeper RL Environment.
    
    Trains agents to make security-aware decisions on incoming Pull Requests
    by using simulated tools: code inspection, CI execution, vulnerability scanning.
    
    The environment is fully stateful per-episode:
    - Each reset() creates a new PR scenario (task1, task2, or task3)
    - Each step() executes a tool and updates the observable state
    - State tracking enables task2 code patching and task3 malware detection
    
    The environment supports concurrent sessions (SUPPORTS_CONCURRENT_SESSIONS=True)
    because each instance gets its own reset() call and maintains isolated state.
    
    Example:
        >>> env = DevSecOpsEnvironment()
        >>> obs = env.reset()
        >>> print(obs.task_id)  # "task1", "task2", or "task3"
        >>> 
        >>> # Run CI to check the PR
        >>> action = DevsecopsAction(tool_name="run_ci", scope="unit_only")
        >>> obs = env.step(action)
        >>> print(obs.reward)
        >>>
        >>> # Make final decision
        >>> action = DevsecopsAction(
        ...     tool_name="make_decision",
        ...     verdict="MERGE",
        ...     justification="Documentation changes only"
        ... )
        >>> obs = env.step(action)
        >>> print(obs.done)  # True
        >>> print(obs.episode_reward)  # Total accumulated reward
    """
    
    # Enable concurrent WebSocket sessions
    # Each client connection gets its own environment instance
    SUPPORTS_CONCURRENT_SESSIONS: bool = True
    
    # Environment metadata for Gymnasium/OpenEnv compliance
    render_mode: str = "text"
    spec: Optional[Dict[str, Any]] = None  # Can be populated with EnvSpec if needed
    
    def __init__(self):
        """Initialize the environment."""
        self._state = State(episode_id=str(uuid4()), step_count=0)
        
        # Per-episode state - initialized in reset()
        self._scenario: Optional[Dict[str, Any]] = None
        self._observation_state = {
            "pr": None,
            "repo_context": None,
            "budget": None,
            "pipeline_history": [],
            "done": False,
            "reward": 0.0,
            "episode_reward": 0.0,
            "step_count": 0,
            "last_tool_output": None,
            "task_id": None,
        }
        
        # Mutable state tracking across tool calls in same episode
        self._internal_state: Dict[str, Any] = {}
        
        # For reward calculation at episode end
        self._verdict: Optional[str] = None
        self._ci_runs_used: int = 0
        self._code_patched: bool = False
        self._final_justification: str = ""
    
    # ========================================================================
    # RESET: Initialize new episode
    # ========================================================================
    
    def reset(self, options: Optional[Dict[str, Any]] = None) -> DevsecopsObservation:
        """
        Reset environment for a new episode.
        
        Args:
            options: Optional dict with:
                - "task": Specific task to load ("task1", "task2", "task3")
                         If not provided, randomly selects one
                         
        Returns:
            DevsecopsObservation: Initial state for the episode
        """
        
        # Reset episode tracking
        self._state = State(episode_id=str(uuid4()), step_count=0)
        
        # Load scenario (random or specified)
        task_id = None
        if options and "task" in options:
            task_id = options["task"]
        self._scenario = load_scenario(task_id)
        
        # Reset internal state tracking
        self._internal_state = {}
        self._verdict = None
        self._ci_runs_used = 0
        self._code_patched = False
        self._final_justification = ""
        
        # Initialize observation state from scenario
        pr = self._scenario["pr"]
        repo = self._scenario["repo_context"]
        budget = self._scenario["budget"]
        
        # Make deep copies to avoid mutation of scenario
        self._observation_state = {
            "pr": copy.deepcopy(pr),
            "repo_context": copy.deepcopy(repo),
            "budget": copy.deepcopy(budget),
            "pipeline_history": [],
            "done": False,
            "reward": 0.0,
            "episode_reward": 0.0,
            "step_count": 0,
            "last_tool_output": None,
            "task_id": self._scenario["task_id"],
            "internal_state": {},
        }
        
        return self._make_observation(reward=0.0)
    
    # ========================================================================
    # STEP: Execute action (tool call)
    # ========================================================================
    
    def step(self, action: DevsecopsAction) -> DevsecopsObservation:
        """
        Execute a tool action.
        
        Args:
            action: DevsecopsAction specifying tool and parameters
            
        Returns:
            DevsecopsObservation: Updated state after tool execution
        """
        
        if self._scenario is None:
            raise RuntimeError("Must call reset() before step()")
        
        # Increment step count
        self._state.step_count += 1
        self._observation_state["step_count"] = self._state.step_count
        
        # ====================================================================
        # STEP 1: Dispatch tool and get result
        # ====================================================================
        
        tool_output, tool_metadata = dispatch_tool(
            action=action,
            scenario=self._scenario,
            environment_state=self._internal_state,
        )
        
        # Update internal state tracking
        # (e.g., task2_code_patched flag set by patch_code tool)
        if action.tool_name == "patch_code" and tool_metadata.get("success"):
            self._code_patched = True
            self._internal_state["task2_code_patched"] = True
        
        # Track CI usage
        if action.tool_name == "run_ci":
            self._ci_runs_used += 1
            self._observation_state["budget"].use_ci()
        
        # ====================================================================
        # STEP 2: Record tool call in pipeline history
        # ====================================================================
        
        tool_record = ToolUseRecord(
            step=self._state.step_count,
            tool_name=action.tool_name,
            arguments={
                k: v for k, v in action.dict().items()
                if v is not None and k != "tool_name"
            },
            result=tool_output[:500],  # Truncate for storage
        )
        self._observation_state["pipeline_history"].append(tool_record)
        
        # ====================================================================
        # STEP 3: Check if episode is done (make_decision called)
        # ====================================================================
        
        is_done = False
        step_reward = 0.0
        
        if action.tool_name == "make_decision":
            is_done = True
            self._verdict = action.verdict
            self._final_justification = action.justification or ""
            
            # Calculate step reward [0, 1] based on verdict + work done
            step_reward = compute_reward(
                task_id=self._scenario["task_id"],
                verdict=self._verdict,
                ci_runs_used=self._ci_runs_used,
                code_patched=self._code_patched,
                justification=self._final_justification,
            )
        else:
            # Intermediate step - small penalty for each step/tool
            # (encourages efficiency)
            step_reward = 0.0  # Or -0.1 per step if you want to encourage finishing
        
        # ====================================================================
        # STEP 4: Update observation state
        # ====================================================================
        
        self._observation_state["done"] = is_done
        self._observation_state["reward"] = step_reward
        self._observation_state["episode_reward"] += step_reward
        self._observation_state["last_tool_output"] = tool_output
        self._observation_state["internal_state"] = copy.deepcopy(self._internal_state)
        
        # Check budget exceeded
        if self._observation_state["step_count"] >= self._observation_state["budget"].step_limit:
            self._observation_state["done"] = True
        
        return self._make_observation(reward=step_reward)
    
    # ========================================================================
    # HELPERS: Observation construction
    # ========================================================================
    
    def _make_observation(self, reward: float) -> DevsecopsObservation:
        """
        Construct a DevsecopsObservation from current state.
        
        Args:
            reward: Reward from the last step
            
        Returns:
            DevsecopsObservation instance
        """
        
        obs = DevsecopsObservation(
            task_id=self._observation_state["task_id"],
            pr=self._observation_state["pr"],
            repo_context=self._observation_state["repo_context"],
            pipeline_history=self._observation_state["pipeline_history"],
            budget=self._observation_state["budget"],
            last_tool_output=self._observation_state["last_tool_output"],
            done=self._observation_state["done"],
            reward=reward,
            episode_reward=self._observation_state["episode_reward"],
            step_count=self._observation_state["step_count"],
            internal_state=self._observation_state["internal_state"],
            metadata={
                "episode_id": self._state.episode_id,
                "verdict": self._verdict,
                "ci_runs_used": self._ci_runs_used,
                "code_patched": self._code_patched,
            },
        )
        
        return obs
    
    # ========================================================================
    # STATE ACCESS (for debugging)
    # ========================================================================
    
    @property
    def state(self) -> State:
        """Get current environment state (episode_id, step_count)."""
        return self._state
    
    def get_episode_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current episode.
        
        Useful for debugging and analysis.
        """
        
        return {
            "episode_id": self._state.episode_id,
            "task_id": self._observation_state["task_id"],
            "step_count": self._state.step_count,
            "done": self._observation_state["done"],
            "episode_reward": self._observation_state["episode_reward"],
            "ci_runs_used": self._ci_runs_used,
            "code_patched": self._code_patched,
            "verdict": self._verdict,
            "tool_calls": [
                {"step": t.step, "tool": t.tool_name}
                for t in self._observation_state["pipeline_history"]
            ],
        }

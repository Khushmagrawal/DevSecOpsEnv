# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
DevSecOps Environment Client.

HTTP/WebSocket client for connecting to the DevSecOps RL environment server.
Handles action serialization and observation deserialization.
"""

from typing import Dict, Any, Optional

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

from .models import (
    DevsecopsAction,
    DevsecopsObservation,
    PullRequest,
    RepositoryContext,
    Budget,
    ToolUseRecord,
)


class DevsecopsEnv(
    EnvClient[DevsecopsAction, DevsecopsObservation, State]
):
    """
    Client for the DevSecOps Environment.

    This client maintains a persistent WebSocket connection to the environment server,
    enabling efficient multi-step interactions with lower latency.
    Each client instance has its own dedicated environment session on the server.

    The client handles:
    - Serialization of DevsecopsAction to JSON
    - Deserialization of JSON responses into DevsecopsObservation
    - Connection management (HTTP/WebSocket)

    Example:
        >>> # Connect to a running server
        >>> with DevsecopsEnv(base_url="http://localhost:8000") as client:
        ...     result = client.reset()
        ...     print(f"Task: {result.observation.task_id}")
        ...
        ...     # Inspect the PR changes
        ...     action = DevsecopsAction(tool_name="inspect_diff")
        ...     result = client.step(action)
        ...     print(result.observation.last_tool_output)
        ...
        ...     # Make a decision
        ...     action = DevsecopsAction(
        ...         tool_name="make_decision",
        ...         verdict="MERGE",
        ...         justification="Docs only, no functional changes"
        ...     )
        ...     result = client.step(action)
        ...     print(f"Done: {result.done}, Reward: {result.observation.episode_reward}")

    Example with Docker:
        >>> # Automatically start container and connect
        >>> client = DevsecopsEnv.from_docker_image("devsecops_env:latest")
        >>> try:
        ...     result = client.reset()
        ...     # ... interact with environment ...
        ... finally:
        ...     client.close()
    """

    def _step_payload(self, action: DevsecopsAction) -> Dict[str, Any]:
        """
        Convert DevsecopsAction to JSON payload for step message.

        Serializes all non-None action fields as a dictionary.

        Args:
            action: DevsecopsAction instance

        Returns:
            Dictionary representation suitable for JSON encoding
        """
        # Serialize action dict, removing None values
        return {k: v for k, v in action.dict().items() if v is not None}

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[DevsecopsObservation]:
        """
        Parse server response into StepResult[DevsecopsObservation].

        Reconstructs all nested Pydantic models from JSON data.

        Args:
            payload: JSON response data from server

        Returns:
            StepResult with DevsecopsObservation
        """
        obs_data = payload.get("observation", {})
        
        # Reconstruct nested Pydantic models
        pr = PullRequest(**obs_data.get("pr", {})) if obs_data.get("pr") else None
        repo = RepositoryContext(**obs_data.get("repo_context", {})) if obs_data.get("repo_context") else None
        budget = Budget(**obs_data.get("budget", {})) if obs_data.get("budget") else None
        
        # Reconstruct tool use records
        history = [
            ToolUseRecord(**record)
            for record in obs_data.get("pipeline_history", [])
        ]
        
        # Create observation
        observation = DevsecopsObservation(
            task_id=obs_data.get("task_id", ""),
            pr=pr or PullRequest(pr_id="", title="", author=""),
            repo_context=repo or RepositoryContext(repo_name=""),
            pipeline_history=history,
            budget=budget or Budget(),
            last_tool_output=obs_data.get("last_tool_output"),
            done=payload.get("done", False),
            reward=payload.get("reward", 0.0),
            episode_reward=obs_data.get("episode_reward", 0.0),
            step_count=obs_data.get("step_count", 0),
            internal_state=obs_data.get("internal_state", {}),
            metadata=obs_data.get("metadata", {}),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward", 0.0),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict[str, Any]) -> State:
        """
        Parse server response into State object.

        Args:
            payload: JSON response from state request

        Returns:
            State object with episode_id and step_count
        """
        return State(
            episode_id=payload.get("episode_id", ""),
            step_count=payload.get("step_count", 0),
        )

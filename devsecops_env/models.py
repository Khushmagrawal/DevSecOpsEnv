# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the DevSecOps Gatekeeper Environment.

This module defines the action and observation schemas for the PR review RL environment.
The environment trains agents to make high-stakes security decisions on incoming PRs.

Key Design:
- Action: Flat schema with tool_name + optional fields for tool parameters
- Observation: Complete state snapshot updated after each step
- All models use Pydantic v2 for validation and serialization
"""

from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field, field_validator

from openenv.core.env_server.types import Action, Observation


# ============================================================================
# ENUMS
# ============================================================================

class ToolName(str, Enum):
    """Available tools the agent can call."""
    
    INSPECT_DIFF = "inspect_diff"
    RUN_CI = "run_ci"
    PATCH_CODE = "patch_code"
    QUERY_PACKAGE_REGISTRY = "query_package_registry"
    SEARCH_VULN_DB = "search_vuln_db"
    MAKE_DECISION = "make_decision"


class CIScope(str, Enum):
    """CI run scope options."""
    
    UNIT_ONLY = "unit_only"
    FULL = "full"


class PRVerdictType(str, Enum):
    """Terminal decision types for PR."""
    
    MERGE = "MERGE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    BLOCK = "BLOCK"


class CIResult(str, Enum):
    """CI test results."""
    
    PASSED = "PASSED"
    FAILED = "FAILED"
    PENDING = "PENDING"


# ============================================================================
# TOOL-SPECIFIC SCHEMAS
# ============================================================================

class PullRequest(BaseModel):
    """PR metadata and content."""
    
    pr_id: str = Field(..., description="Unique PR identifier")
    title: str = Field(..., description="PR title")
    description: str = Field(default="", description="PR description/body")
    author: str = Field(..., description="PR author")
    target_branch: str = Field(default="main", description="Target branch")
    files_changed: List[str] = Field(default_factory=list, description="List of changed files")
    
    class Config:
        json_schema_extra = {
            "example": {
                "pr_id": "pr_001",
                "title": "Bump httpx to 0.28.0",
                "author": "dependabot[bot]",
                "files_changed": ["requirements.txt", "src/api_client.py"]
            }
        }


class RepositoryContext(BaseModel):
    """Metadata about the repository."""
    
    repo_name: str = Field(..., description="Repository name")
    repo_url: str = Field(default="", description="Repository URL")
    main_language: str = Field(default="python", description="Primary language")
    has_ci: bool = Field(default=True, description="Has CI/CD pipeline")
    critical_modules: List[str] = Field(default_factory=list, description="Critical code modules")


class Budget(BaseModel):
    """Available resources for this episode."""
    
    ci_runs: int = Field(default=5, description="Remaining CI run credits")
    step_limit: int = Field(default=10, description="Max steps before episode ends")
    
    def has_ci_budget(self) -> bool:
        """Check if can run CI."""
        return self.ci_runs > 0
    
    def use_ci(self) -> None:
        """Consume one CI run credit."""
        if self.ci_runs > 0:
            self.ci_runs -= 1


class ToolUseRecord(BaseModel):
    """Record of tool usage in the episode."""
    
    step: int = Field(..., description="Step number when tool was called")
    tool_name: str = Field(..., description="Which tool was called")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    result: str = Field(default="", description="Tool result/output")
    

class CITestResult(BaseModel):
    """Result from running CI."""
    
    status: CIResult = Field(..., description="PASSED, FAILED, or PENDING")
    test_count: int = Field(default=0, description="Number of tests run")
    coverage: Optional[float] = Field(default=None, description="Code coverage percentage")
    failure_reason: str = Field(default="", description="If FAILED, why it failed")
    error_location: Optional[str] = Field(default=None, description="File:line of first error")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "FAILED",
                "test_count": 42,
                "error_location": "src/api_client.py:4",
                "failure_reason": "AttributeError: 'AsyncClient' has no attr 'send'"
            }
        }


class PackageMetadata(BaseModel):
    """Metadata from package registry (PyPI, etc)."""
    
    package_name: str = Field(..., description="Package name")
    version: str = Field(..., description="Package version")
    published_at: str = Field(default="", description="When published (ISO timestamp or 'N hours ago')")
    maintainer_username: str = Field(default="", description="Current maintainer")
    maintainer_account_age_days: int = Field(default=0, description="Days since maintainer account created")
    prior_versions_by_maintainer: int = Field(default=0, description="How many versions this maintainer released")
    downloads_last_24h: int = Field(default=0, description="Downloads in last 24 hours")
    prev_version_downloads_24h: int = Field(default=0, description="Previous version's 24h downloads")
    ownership_transfer: bool = Field(default=False, description="Was there a recent ownership transfer")
    notes: str = Field(default="", description="Additional notes")


class VulnerabilityReport(BaseModel):
    """Security vulnerability data."""
    
    cve_ids: List[str] = Field(default_factory=list, description="Associated CVEs")
    osv_entries: List[str] = Field(default_factory=list, description="OSV identifiers")
    critical: bool = Field(default=False, description="Critical severity")
    suspicious_patterns: List[str] = Field(default_factory=list, description="Suspicious code patterns detected")
    note: str = Field(default="", description="Additional analysis notes")


# ============================================================================
# MAIN ACTION SCHEMA
# ============================================================================

class DevsecopsAction(Action):
    """
    Action schema for DevSecOps environment.
    
    Flat structure with all optional tool parameters. Only tool_name is required,
    and the relevant parameters for that tool should be populated.
    
    Example (inspect_diff):
        DevsecopsAction(tool_name="inspect_diff", pr_id="pr_001")
    
    Example (run_ci):
        DevsecopsAction(tool_name="run_ci", scope=CIScope.UNIT_ONLY)
    
    Example (make_decision):
        DevsecopsAction(
            tool_name="make_decision",
            verdict="MERGE",
            justification="Docs only, no functional changes"
        )
    """
    
    # Required field
    tool_name: str = Field(
        ...,
        description="Name of tool to invoke",
        json_schema_extra={"enum": [t.value for t in ToolName]}
    )
    
    # Tool parameters (all optional)
    pr_id: Optional[str] = Field(
        default=None,
        description="PR identifier for inspect_diff"
    )
    
    scope: Optional[str] = Field(
        default=None,
        description="CI scope: 'unit_only' or 'full'"
    )
    
    pkg: Optional[str] = Field(
        default=None,
        description="Package name for query_package_registry/search_vuln_db"
    )
    
    version: Optional[str] = Field(
        default=None,
        description="Package version for query_package_registry/search_vuln_db"
    )
    
    file: Optional[str] = Field(
        default=None,
        description="File path for patch_code"
    )
    
    old_code: Optional[str] = Field(
        default=None,
        description="Code to replace in patch_code"
    )
    
    new_code: Optional[str] = Field(
        default=None,
        description="Replacement code in patch_code"
    )
    
    verdict: Optional[str] = Field(
        default=None,
        description="PR decision: MERGE, REQUEST_CHANGES, or BLOCK",
        json_schema_extra={"enum": [v.value for v in PRVerdictType]}
    )
    
    justification: Optional[str] = Field(
        default="",
        description="Reasoning for the verdict"
    )
    
    @field_validator("tool_name")
    @classmethod
    def validate_tool_name(cls, v: str) -> str:
        """Ensure tool_name is one of the valid tools."""
        valid_tools = {t.value for t in ToolName}
        if v not in valid_tools:
            raise ValueError(f"tool_name must be one of {valid_tools}")
        return v
    
    @field_validator("verdict")
    @classmethod
    def validate_verdict(cls, v: Optional[str]) -> Optional[str]:
        """Ensure verdict is one of the allowed types."""
        if v is not None:
            valid_verdicts = {vt.value for vt in PRVerdictType}
            if v not in valid_verdicts:
                raise ValueError(f"verdict must be one of {valid_verdicts}")
        return v

    class Config:
        """Pydantic configuration."""
        extra = "ignore"
        json_schema_extra = {
            "example": {
                "tool_name": "inspect_diff",
                "pr_id": "pr_001"
            }
        }


# ============================================================================
# MAIN OBSERVATION SCHEMA
# ============================================================================

class DevsecopsObservation(Observation):
    """
    Complete environment state snapshot.
    
    Sent after every step and reset. Contains all information the agent
    needs to make decisions. Immutable during a step (updated only by environment).
    
    Matches OpenEnv specification for Observation interface.
    """
    
    # Current task info
    task_id: str = Field(..., description="Which task (task1, task2, task3)")
    
    # PR and repo details
    pr: PullRequest = Field(..., description="Current PR being reviewed")
    repo_context: RepositoryContext = Field(..., description="Repo metadata")
    
    # History and state
    pipeline_history: List[ToolUseRecord] = Field(
        default_factory=list,
        description="All tool calls made so far in episode"
    )
    
    # Resources and constraints
    budget: Budget = Field(..., description="Remaining CI runs and step limit")
    
    # Last action result
    last_tool_output: Optional[str] = Field(
        default=None,
        description="Text output from most recent tool call"
    )
    
    # Episode status
    done: bool = Field(default=False, description="Episode is over")
    reward: float = Field(default=0.0, description="Reward for last step")
    episode_reward: float = Field(default=0.0, description="Cumulative reward this episode")
    step_count: int = Field(default=0, description="Total steps taken")
    
    # Internal state tracking (varies by task)
    internal_state: Dict[str, Any] = Field(
        default_factory=dict,
        description="Task-specific state (patched files, etc)"
    )
    
    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional debugging info"
    )
    
    def summary(self) -> str:
        """Get a human-readable summary of current observation."""
        summary_lines = [
            f"Task: {self.task_id}",
            f"PR: {self.pr.pr_id} - {self.pr.title}",
            f"Step: {self.step_count}",
            f"CI Budget: {self.budget.ci_runs} runs remaining",
            f"Episode Reward: {self.episode_reward:.2f}",
        ]
        if self.last_tool_output:
            summary_lines.append(f"Last Tool: {self.last_tool_output[:100]}...")
        return "\n".join(summary_lines)


# ============================================================================
# TYPE EXPORTS
# ============================================================================

__all__ = [
    "DevsecopsAction",
    "DevsecopsObservation",
    "ToolName",
    "CIScope",
    "PRVerdictType",
    "CIResult",
    "PullRequest",
    "RepositoryContext",
    "Budget",
    "ToolUseRecord",
    "CITestResult",
    "PackageMetadata",
    "VulnerabilityReport",
]

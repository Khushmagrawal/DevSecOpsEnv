---
title: DevSecOps Gatekeeper Environment
emoji: 🚀
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
  - security
  - reinforcement-learning
  - devsecops
---

# DevSecOps Gatekeeper Environment

An advanced OpenEnv RL environment where AI agents learn to make high-stakes security decisions on incoming Pull Requests. The agent uses simulated tools to analyze code changes, run CI/CD pipelines, patch code, scan vulnerabilities, and ultimately approve or block PRs.

## Overview

This environment presents three progressively harder scenarios:

### Task 1: Docs-Only PR
**Complexity**: Easy

A PR that ONLY changes documentation and comments. The agent should recognize this and approve without unnecessary testing.

- **Optimal path**: inspect_diff → make_decision(MERGE)
- **Optimal reward**: ~0.999
- **Key skill**: Recognition - identify zero-risk changes

### Task 2: Silent API Rename
**Complexity**: Medium

A package dependency bump (httpx 0.23.0 → 0.28.0) has breaking API changes. The agent must:
1. Detect the breaking change
2. Run CI to see the failure
3. Patch the code to use the new API
4. Verify the fix with CI
5. Approve the PR

- **Optimal path**: inspect_diff → run_ci (fail) → query_registry → patch_code → run_ci (pass) → make_decision(MERGE)
- **Optimal reward**: ~0.999
- **Key skill**: Remediation - fix breaking dependency changes

### Task 3: Poisoned Package
**Complexity**: Hard

A package (cryptoutils 2.1.5) contains malware in its setup.py that exfiltrates system information. The agent must:
1. Detect malicious code patterns
2. Check suspicious package metadata (new maintainer, ownership transfer)
3. Block the malicious package
4. CRUCIALLY: Avoid running CI (which would execute the malware)

- **Optimal path**: inspect_diff → query_registry → make_decision(BLOCK)
- **Optimal reward**: ~0.999
- **Key skill**: Security - detect supply chain attacks

## Installation

```bash
# Install the environment package
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

## Quick Start

### Using the Python Client

```python
from devsecops_env import DevsecopsEnv, DevsecopsAction

# Connect to locally running server
with DevsecopsEnv(base_url="http://localhost:8000") as client:
    # Reset to start a new episode
    result = client.reset()
    print(f"Task: {result.observation.task_id}")
    
    # Inspect PR changes
    action = DevsecopsAction(tool_name="inspect_diff")
    result = client.step(action)
    print(f"Diff: {result.observation.last_tool_output[:200]}...")
    
    # Make decision
    action = DevsecopsAction(
        tool_name="make_decision",
        verdict="MERGE",
        justification="Docs only, no functional changes"
    )
    result = client.step(action)
    print(f"Done: {result.done}, Reward: {result.observation.episode_reward}")
```

### Starting the Server Locally

```bash
# Install dependencies
uv sync

# Start server
cd devsecops_env && uvicorn server.app:app --reload --port 8000
```

The server will be available at `http://localhost:8000` with:
- REST API endpoints for reset/step/state
- WebSocket support for persistent sessions
- Gradio web interface at `/web`

### Running Tests

```bash
# Run comprehensive test suite
python test_env.py

# Or with pytest
pytest test_env.py -v
```

Tests validate:
- Scenario loading and integrity
- Tool dispatcher behavior
- State transitions and tracking
- Reward calculations
- End-to-end episode flows

## Environment API

### Action Schema

`DevsecopsAction` contains:
- `tool_name` (required): One of ["inspect_diff", "run_ci", "patch_code", "query_package_registry", "search_vuln_db", "make_decision"]
- Tool-specific parameters (all optional): `pr_id`, `scope`, `pkg`, `version`, `file`, `old_code`, `new_code`, `verdict`, `justification`

Example actions:

```python
# Inspect PR changes
inspect_action = DevsecopsAction(tool_name="inspect_diff", pr_id="pr_001")

# Run CI with specific scope
ci_action = DevsecopsAction(tool_name="run_ci", scope="unit_only")

# Patch code (Task 2)
patch_action = DevsecopsAction(
    tool_name="patch_code",
    file="src/api_client.py",
    old_code="await client.send(request)",
    new_code="await client.request('GET', url)"
)

# Query package registry
query_action = DevsecopsAction(
    tool_name="query_package_registry",
    pkg="httpx",
    version="0.28.0"
)

# Search vulnerability databases
vuln_action = DevsecopsAction(
    tool_name="search_vuln_db",
    pkg="cryptoutils",
    version="2.1.5"
)

# Make final decision
decision_action = DevsecopsAction(
    tool_name="make_decision",
    verdict="MERGE",  # or "REQUEST_CHANGES" or "BLOCK"
    justification="Security checks passed"
)
```

### Observation Schema

`DevsecopsObservation` contains:
- `task_id`: Current task being solved
- `pr`: Pull request metadata
- `repo_context`: Repository information
- `budget`: Remaining CI runs and step limit
- `pipeline_history`: All tool calls made so far
- `last_tool_output`: Text output from most recent tool
- `done`: Episode completion flag
- `reward`: Reward from last step
- `episode_reward`: Cumulative reward
- `step_count`: Total steps taken
- `internal_state`: Task-specific mutable state (code_patched, etc)

## Tools Explained

### inspect_diff
Analyzes the PR diff to understand what's changing. Returns:
- Summary of files changed
- Analysis (docs-only? code changes? breaking changes?)
- Red flags or warnings

### run_ci
Runs the CI/CD pipeline. Results depend on:
- Task ID
- Current state (e.g., whether code was patched in Task 2)
- Scope: "unit_only" or "full"

Cost: 1 CI run (budget is limited)

### patch_code
Attempts to patch code. For Task 2, validates that the patch:
- Replaces deprecated API calls
- Makes semantic sense

Success marks code as patched in internal state, affecting subsequent CI runs.

### query_package_registry
Looks up package metadata from PyPI/registry:
- Maintainer information (age, prior releases)
- Download statistics
- Ownership transfer history
- Notes on suspicious patterns

### search_vuln_db
Searches CVE and OSV vulnerability databases:
- Known CVEs
- Suspicious code patterns detected
- Notes on package age (very new packages have no history)

### make_decision
Terminal action that ends the episode. Sets verdict ("MERGE", "REQUEST_CHANGES", or "BLOCK") and triggers reward calculation.

## Reward Structure

All rewards are normalized to the range `(0, 1)`.

### Task 1 (Docs-Only)
- Correct verdict (MERGE): High reward (~0.999)
- Incorrect verdict (BLOCK): Very low reward (~0.0001)
- Penalty: Slight reduction for each unnecessary CI run.

### Task 2 (Silent API Rename)
- Correct verdict with patch: Optimal reward (~0.999)
- Verdict without patch: Negative sentiment reflected in low reward.
- Penalty: Reduction for excessive CI runs beyond optimal (2).

### Task 3 (Poisoned Package)
- Correct verdict (BLOCK): High reward (~0.999)
- Incorrect verdict (MERGE): Catastrophic failure (~0.0001)
- Penalty: Significant reduction for each CI run (as CI executes malware).

## State Management

The environment uses **per-episode mutable state** to enable:
- **Task 2**: Tracking whether code has been patched (affects CI results)
- **Task 3**: Stateless (each tool call returns deterministic output)

Each `reset()` creates a fresh, isolated episode state.

## Docker Deployment

Build the Docker image:

```bash
docker build -t devsecops_env:latest server/
```

Run locally:

```bash
docker run -p 8000:8000 devsecops_env:latest
```

## Deploying to Hugging Face Spaces

```bash
huggingface-cli login
openenv push
```

Pushes the environment to Hugging Face Spaces with automatic Docker building and Gradio web interface.

## File Structure

```
devsecops_env/
├── __init__.py                    # Package exports
├── models.py                      # Pydantic schemas (Action, Observation)
├── client.py                      # HTTP/WebSocket client
├── test_env.py                    # Comprehensive test suite
├── openenv.yaml                   # OpenEnv manifest
├── pyproject.toml                 # Package configuration
├── README.md                      # This file
└── server/
    ├── __init__.py
    ├── app.py                     # FastAPI application
    ├── devsecops_env_environment.py  # Core environment logic
    ├── mock_tools.py              # Tool implementations
    ├── graders.py                 # Reward calculation
    ├── requirements.txt
    ├── Dockerfile
    └── scenarios/
        ├── __init__.py            # Registry and loader
        ├── task1.py               # Docs-only scenario
        ├── task2.py               # Silent API rename scenario
        └── task3.py               # Poisoned package scenario
```

## References

- [OpenEnv Specification](https://github.com/huggingface/openenv-course)
- [Meta OpenEnv Repository](https://github.com/meta-pytorch/OpenEnv)
- [Gymnasium API](https://gymnasium.farama.org/)

openenv push --base-image ghcr.io/meta-pytorch/openenv-base:latest

# Push as a private space
openenv push --private

# Combine options
openenv push --repo-id my-org/my-env --base-image custom-base:latest --private
```

After deployment, your space will be available at:
`https://huggingface.co/spaces/<repo-id>`

The deployed space includes:
- **Web Interface** at `/web` - Interactive UI for exploring the environment
- **API Documentation** at `/docs` - Full OpenAPI/Swagger interface
- **Health Check** at `/health` - Container health monitoring
- **WebSocket** at `/ws` - Persistent session endpoint for low-latency interactions

## Development & Testing

### Direct Environment Testing

Test the environment logic directly without starting the HTTP server:

```bash
python test_env.py
```

### Starting the Server Locally

```bash
uvicorn server.app:app --reload
```

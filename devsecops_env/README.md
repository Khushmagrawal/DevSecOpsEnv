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
- **Optimal reward**: +5.0
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
- **Optimal reward**: +7.0 (5.0 verdict + 2.0 patch bonus)
- **Key skill**: Remediation - fix breaking dependency changes

### Task 3: Poisoned Package
**Complexity**: Hard

A package (cryptoutils 2.1.5) contains malware in its setup.py that exfiltrates system information. The agent must:
1. Detect malicious code patterns
2. Check suspicious package metadata (new maintainer, ownership transfer)
3. Block the malicious package
4. CRUCIALLY: Avoid running CI (which would execute the malware)

- **Optimal path**: inspect_diff → query_registry → make_decision(BLOCK)
- **Optimal reward**: +5.0
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

### Task 1 (Docs-Only)
```
Base:       +5.0 (MERGE) | -1.0 (REQUEST_CHANGES) | -3.0 (BLOCK)
Penalty:    -0.5 per CI run (docs-only, CI is wasteful)
Optimal:    Merge without CI = +5.0
```

### Task 2 (Silent API Rename)
```
Base:       +5.0 (MERGE with patch) | -3.0 (MERGE without patch) | +1.0-2.0 (REQUEST_CHANGES)
Patch bonus: +2.0 (if code_patched=true)
Penalty:    -0.5 per extra CI run (optimal is 2)
Optimal:    Fix + merge = +7.0
```

### Task 3 (Poisoned Package)
```
Base:       +5.0 (BLOCK) | -3.0 (MERGE) | -1.0 (REQUEST_CHANGES)
CI penalty: -1.0 per CI run (running CI executes malware!)
Optimal:    Block without CI = +5.0
```

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

## Environment Details

### Action
**DevsecopsAction**: Contains a single field
- `message` (str) - The message to echo back

### Observation
**DevsecopsObservation**: Contains the echo response and metadata
- `echoed_message` (str) - The message echoed back
- `message_length` (int) - Length of the message
- `reward` (float) - Reward based on message length (length × 0.1)
- `done` (bool) - Always False for echo environment
- `metadata` (dict) - Additional info like step count

### Reward
The reward is calculated as: `message_length × 0.1`
- "Hi" → reward: 0.2
- "Hello, World!" → reward: 1.3
- Empty message → reward: 0.0

## Advanced Usage

### Connecting to an Existing Server

If you already have a Devsecops Env environment server running, you can connect directly:

```python
from devsecops_env import DevsecopsEnv

# Connect to existing server
devsecops_envenv = DevsecopsEnv(base_url="<ENV_HTTP_URL_HERE>")

# Use as normal
result = devsecops_envenv.reset()
result = devsecops_envenv.step(DevsecopsAction(message="Hello!"))
```

Note: When connecting to an existing server, `devsecops_envenv.close()` will NOT stop the server.

### Using the Context Manager

The client supports context manager usage for automatic connection management:

```python
from devsecops_env import DevsecopsAction, DevsecopsEnv

# Connect with context manager (auto-connects and closes)
with DevsecopsEnv(base_url="http://localhost:8000") as env:
    result = env.reset()
    print(f"Reset: {result.observation.echoed_message}")
    # Multiple steps with low latency
    for msg in ["Hello", "World", "!"]:
        result = env.step(DevsecopsAction(message=msg))
        print(f"Echoed: {result.observation.echoed_message}")
```

The client uses WebSocket connections for:
- **Lower latency**: No HTTP connection overhead per request
- **Persistent session**: Server maintains your environment state
- **Efficient for episodes**: Better for many sequential steps

### Concurrent WebSocket Sessions

The server supports multiple concurrent WebSocket connections. To enable this,
modify `server/app.py` to use factory mode:

```python
# In server/app.py - use factory mode for concurrent sessions
app = create_app(
    DevsecopsEnvironment,  # Pass class, not instance
    DevsecopsAction,
    DevsecopsObservation,
    max_concurrent_envs=4,  # Allow 4 concurrent sessions
)
```

Then multiple clients can connect simultaneously:

```python
from devsecops_env import DevsecopsAction, DevsecopsEnv
from concurrent.futures import ThreadPoolExecutor

def run_episode(client_id: int):
    with DevsecopsEnv(base_url="http://localhost:8000") as env:
        result = env.reset()
        for i in range(10):
            result = env.step(DevsecopsAction(message=f"Client {client_id}, step {i}"))
        return client_id, result.observation.message_length

# Run 4 episodes concurrently
with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(run_episode, range(4)))
```

## Development & Testing

### Direct Environment Testing

Test the environment logic directly without starting the HTTP server:

```bash
# From the server directory
python3 server/devsecops_env_environment.py
```

This verifies that:
- Environment resets correctly
- Step executes actions properly
- State tracking works
- Rewards are calculated correctly

### Running Locally

Run the server locally for development:

```bash
uvicorn server.app:app --reload
```

## Project Structure

```
devsecops_env/
├── .dockerignore         # Docker build exclusions
├── __init__.py            # Module exports
├── README.md              # This file
├── openenv.yaml           # OpenEnv manifest
├── pyproject.toml         # Project metadata and dependencies
├── uv.lock                # Locked dependencies (generated)
├── client.py              # DevsecopsEnv client
├── models.py              # Action and Observation models
└── server/
    ├── __init__.py        # Server module exports
    ├── devsecops_env_environment.py  # Core environment logic
    ├── app.py             # FastAPI application (HTTP + WebSocket endpoints)
    └── Dockerfile         # Container image definition
```

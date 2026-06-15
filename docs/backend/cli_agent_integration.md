# CLI Agent Integration Strategy

## Objective
To enable efficient, low-cost models (such as Gemma 4, 12B) to delegate complex, specialized tasks to sub-agents via CLI execution, minimizing the reasoning burden on the primary LLM and reducing context window bloat.

## Architectural Approach: The "Agent-as-a-Tool" Pattern
Instead of treating the CLI as a separate runtime, we integrate CLI execution as a first-class **ADK Tool**. This allows the primary ADK Agent to maintain orchestration and state while offloading execution to specialized subprocesses.

### 1. Component: `CLIAgentTool`
A new tool implemented within the `app/agent/tools/` directory.

**Responsibilities:**
* **Spec Encapsulation:** Provides a structured interface for the Orchestrator to define a sub-agent with `name`, `description`, `instructions`, and `tools`.
* **Subprocess Orchestration:** Converts the spec into a local CLI launch of `app.agent.sub_agent_launcher` using Python's `subprocess` module.
* **Output Translation:** Captures `stdout` and `stderr` and formats them into a `tool_result` for the ADK `Runner`.
* **Environment Management:** Ensures necessary environment variables and working directories are passed to the sub-agent.

### 2. Sub-Agent Architecture: The "Local Process" Model
To maintain high performance and low cost, sub-agents will be implemented as **lightweight, headless Python scripts** running as local subprocesses.

**Sub-Agent Characteristics:**
* **Specialization:** Each sub-agent is purpose-built (e.g., `researcher.py`, `coder.py`, `tester.py`) with a minimal set of tools.
* **Minimalism:** They do not require a full API server; they follow a "Run $\rightarrow$ Result $\rightarrow$ Exit" lifecycle.
* **Independence:** They can be developed and tested independently of the main FastAPI backend.
* **Launcher Contract:** The sub-agent launcher builds the ADK agent from the provided spec and runs the task described by `instructions`.

### 3. Security & Safety (Critical)
Since CLI execution carries high risk, the tool must be gated by:
* **PathPolicy Integration:** The tool must consult `app/security/PathPolicy` to ensure the command is not attempting to access unauthorized directories.
* **Command Whitelisting:** Only authorized binaries (e.g., `python`, `node`, `uv`) are permitted.
* **Resource Limits:** Implementation of execution timeouts to prevent "zombie" sub-agents from consuming system resources.

### 4. Integration Workflow

#### **A. Tool Registration**
In `app/agent/runner.py`, the `CLIAgentTool` is added to the `build_agent_tools` factory:
```python
# Conceptual integration in ChatRuntime
tools = build_agent_tools(path_policy)
tools.append(CLIAgentTool(allowed_binaries=["python", "uv", "node"]))
```

#### **B. Execution Flow**
1. **Intent Detection:** The Orchestrator (Gemma 4) identifies a task requiring specialized expertise.
2. **Tool Call:** The LLM emits a `tool_call` for `spawn_sub_agent` with `name`, `description`, `instructions`, and `tools`.
3. **Execution:** The `CLIAgentTool` validates the spec, writes it to a temp file, and launches `app.agent.sub_agent_launcher`.
4. **Result Streaming:** The output of the sub-agent is captured and returned as a `tool_result` event.
5. **Reasoning Loop:** The Orchestrator receives the result and decides whether to proceed or call another sub-agent.

#### **Example Tool Call**
```json
{
  "name": "code_reviewer",
  "description": "A specialized agent that focuses on linting, security vulnerabilities, and PEP8 compliance.",
  "instructions": "You are a senior security engineer. Review the provided code snippets for vulnerabilities and style issues.",
  "tools": ["filesystem", "terminal"]
}
```

## Benefits for Small/Efficient Models (Gemma 4)
* **Reduced Reasoning Load:** The model acts as a "Manager" rather than a "Worker," delegating complex task execution to specialized agents.
* **Context Efficiency:** Large volumes of data processed by sub-agents can be summarized before being returned to the primary model, keeping the context window clean.
* **Modularity:** New capabilities can be added by simply dropping a new `.py` script into the project.

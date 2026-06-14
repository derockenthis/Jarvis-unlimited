# Implementation Strategy: Google ADK 2.0 for Agentic Web Building

This document outlines how the **Agent Development Kit (ADK) 2.0** will be utilized to build a superior, industry-specialized AI web application builder, specifically addressing the limitations found in generalist tools like Lovable.

## 1. Core Architectural Shift: From Linear to Graph-Based
Current AI builders use a linear "Prompt $\rightarrow$ Code" approach, which is prone to architectural drift and broken dependencies. We will replace this with **ADK 2.0 Graph Workflows**.

### The "Development Pipeline" Graph
Instead of a single LLM call, the building process will be a **Directed Acyclic Graph (DAG)** where each node is a specialized agent or tool.

| Node Type | Agent/Tool Name | Responsibility |
| :--- | :--- | :--- |
| **LLM Agent** | `Architect_Agent` | Translates user intent into a structured JSON "Technical Blueprint" (Schema, Routes, Files). |
| **Logic Node** | `Schema_Validator` | A deterministic Python node that validates the Blueprint against industry-standard rules. |
| **LLM Agent** | `Developer_Agent` | Consumes the validated Blueprint to generate modular Vue.js and FastAPI code. |
| **Tool Node** | `QA_Linter_Tool` | Executes automated linting and unit tests on the generated code. |
| **Decision Node** | `Router_Node` | Evaluates QA results. If `FAIL`, routes back to `Developer_Agent` with error logs. If `PASS`, routes to `Deployment`. |

**Advantage:** This ensures **architectural integrity**. The AI cannot write code that violates the pre-approved blueprint.

---

## 2. The "Consultative Engineering" Workflow (Human-in-the-Loop)
To solve the "Black Box" and "Complexity" issues, we move away from "Shotgun Prompting" toward a multi-stage, human-verified pipeline.

### Phase 1: Ambiguity Detection & Clarification
*   **The Clarifier Node:** Before planning, an agent analyzes the prompt for missing requirements (e.g., "You said you want an event app, but should it support tiered ticketing?").
*   **The Pause State:** The graph enters a `PAUSE` state, triggering a UI component that presents these questions to the user. The build does not proceed until requirements are solidified.

### Phase 2: Architect-First Planning (The Blueprint)
*   **The Architect Node:** Instead of writing code, this agent produces a **Technical Blueprint** (JSON) containing the Database Schema, Component Tree, and API Routes.
*   **The Approval Gate:** The graph enters a `PENDING_APPROVAL` state. The user reviews a high-level summary (The Blueprint) in the UI. 
*   **User Interaction:** The user can "Approve & Build" or "Iterate on Design" (modifying the blueprint via chat).

### Phase 3: Implementation & Self-Correction
*   **The Developer Node:** Only executes once the Blueprint is signed off. It uses the blueprint as a "strict instruction set" to minimize hallucinations.
*   **The QA/Self-Healing Loop:** If the QA node detects an error, the graph automatically routes back to the Developer with the specific error logs, creating a self-correcting loop before the user even sees the result.

---

## 3. Long-Running Agents & UX
We will leverage ADK 2.0's ability to manage long-running tasks to handle complex builds that take minutes.

*   **Asynchronous Builds:** The backend returns a `session_id` immediately; the user is never left staring at a timeout.
*   **Real-time Observability:** Using WebSockets, the Vue frontend displays a live "Dev Log" (e.g., *"Architect is designing database..."* $\rightarrow$ *"Developer is writing components..."*).
*   **Resumable Sessions:** Users can close the browser and return to find the agent still working or waiting for their input at a specific graph node.

---

## 4. Technical Requirements & Integration

### Backend Stack (Python)
*   **Framework:** FastAPI (for the API Server).
*   **Orchestration:** `google-adk` (ADK 2.0 Python SDK).
*   **Intelligence:** Gemini 2.0 / Claude 3.5 via ADK Tool calling.
*   **Memory:** ADK 2.0 Session & Memory management for context caching.

### Frontend Stack (Vue.js)
*   **Framework:** Vue 3 (Vite + Tailwind CSS).
*   **UI Library:** **Shadcn/UI** (for modular, professional, and industry-standard components).
*   **Communication:** WebSockets for real-time graph state updates.
*   **Execution:** WebContainers (to run the generated code in-browser).

## Summary of Value Proposition
By using ADK 2.0, we move from a "Chat-to-Code" tool to a **"Managed Development Lifecycle."** We solve the **Glass Ceiling** through deterministic graph routing, the **Black Box** through transparent architectural steps, and the **Complexity Wall** through multi-agent specialization.

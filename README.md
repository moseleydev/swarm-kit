# 🐝 Swarm Kit

> A minimalist, state-aware multi-agent orchestration framework.

Swarm Kit is a lightweight Python framework designed to build fault-tolerant, multi-agent systems. It provides native state management, tool execution, and a beautiful real-time local dashboard, all while remaining LLM-agnostic via LiteLLM.

## Features

- **🧠 Native State Management:** Agents share a global memory state, preventing context loss in long workflows.
- **🛠️ Tool Execution:** Easily map native Python functions to agents for database lookups, API calls, and more.
- **🔄 Fault-Tolerant Routing:** Built-in guardrails prevent infinite self-transfer loops and LLM hallucination crashes.
- **📊 Agent Studio UI:** A beautiful, real-time local dashboard to observe agent logic and handovers.
- **🔌 LLM Agnostic:** Swap between OpenAI, Anthropic, Gemini, or local models by simply changing a string.

---

## Installation

```bash
pip install swarm-kit
```

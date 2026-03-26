# Swarm Agent Kit

> A minimalist, state-aware multi-agent orchestration framework designed for production backends.

Swarm Agent Kit is a lightweight Python framework built to orchestrate fault-tolerant, multi-agent systems. It bridges the gap between simple chat scripts and complex production environments by providing native state management, async execution, database persistence hooks, and a real-time observability dashboard.

## 📚 Documentation

For full API references, tutorials, and advanced database integration guides, visit the official documentation:
**[Swarm Agent Kit Official Docs](https://moseleydev.github.io/swarm-kit/)**

---

## Core Features

- **Dual-Mode Orchestration:** Choose between unsupervised dynamic routing (agents autonomously hand off tasks) or supervised execution (a central LLM planner forces agents through a strict sequential pipeline).
- **Production-Ready Async:** Full support for non-blocking `async/await` execution, making it safe to deploy inside high-concurrency web frameworks like FastAPI.
- **Bring-Your-Own-Database (BYOD):** Native persistence hooks allow you to seamlessly save and resume sessions using Redis, PostgreSQL, or any database of your choice.
- **Global State Management:** Agents share and mutate a global memory dictionary via built-in tools, preventing context loss and keeping token usage lean during long workflows.
- **Native Tool Execution:** Easily bind standard Python functions and JSON schemas to specific agents to trigger external APIs or internal logic.
- **LLM Agnostic:** Powered by LiteLLM under the hood, allowing you to swap between OpenAI, Anthropic, Gemini, or local models by simply changing a model string.

---

## 📦 Installation

Install the package via PyPI:

```bash
pip install swarm-agent-kit
```

Set your API keys in a `.env` file (Swarm Kit supports 100+ providers):

```env
OPENAI_API_KEY="sk-..."
GEMINI_API_KEY="..."
```

---

## 💻 CLI Commands

Swarm Agent Kit comes with a built-in command-line interface for local development and observability.

```bash
# Launch the real-time observability dashboard (Agent Studio)
swarm-kit studio

# View all available commands and help options
swarm-kit --help
```

_(Note: The studio runs locally on `http://localhost:8000` by default)._

---

## 💡 Integration Examples

Looking for drop-in code to get started? Check out the `examples/` directory in our [GitHub repository](https://www.google.com/search?q=https://github.com/moseleydev/swarm-kit/tree/main/examples) for production-ready implementations:

- **`unsupervised_chat.py`**: A dynamic customer support bot that utilizes custom tools and BYOD database persistence.
- **`supervised_pipeline.py`**: A strict data extraction pipeline guided step-by-step by a central LLM planner.

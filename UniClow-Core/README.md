# UniClaw

UniClaw is an enterprise agent framework that lets employees interact with multiple enterprise systems through one conversational AI interface. Instead of switching between separate consoles, dashboards, and approval portals, users can use natural language to trigger workflows, query operational data, and complete cross-system tasks from a single entry point.

This repository contains the `smartcmp-ai` implementation of the UniClaw core, including the agent runtime, API layer, channel adapters, provider registry, skills, tools, and session/memory management.

## Background

Enterprise software teams often need to work across CRM, ITSM, Monitoring, HR, Finance, and other internal systems. The challenge is not only system fragmentation, but also the mismatch between data models, workflow boundaries, authorization models, and user experience across those systems.

UniClaw is designed around two practical developer questions:

- How do you provide one unified AI Agent experience on top of the systems an enterprise already has?
- How do you let enterprise software developers add AI Agent capabilities to their own systems quickly, without rebuilding agent infrastructure from scratch?

UniClaw addresses those problems with a developer-oriented agent framework:

- A unified conversational layer for cross-system workflows and operations
- A pluggable provider model that lets developers expose system capabilities to the agent quickly
- Strict permission inheritance so every action runs under the authenticated user's real access rights
- Multi-channel access through web UI, embedded panels, chat platforms, and programmatic webhooks

The framework is built to help teams add agent capabilities to existing enterprise software without weakening governance. UniClaw does not bypass RBAC, does not escalate privileges, and keeps platform-specific authorization and auditing where they already belong.

## Key Capabilities

- LLM-driven Skills model instead of hard-coded traditional workflows
- Skills define business scenarios, decision boundaries, and how the agent interacts with external systems
- A cross-system agent brain for analysis, judgment, coordination, and execution across enterprise software
- Provider-based integration model that lets developers add new system capabilities quickly
- Thin-core architecture that keeps platform-specific logic in Providers and reusable agent logic in the core
- Embeddable agent foundation for enterprise application developers
- API-first interaction model with interactive APIs, WebSocket streaming, and webhook entry points
- Flexible LLM backend support through external model providers

## Deployment Modes

UniClaw supports two practical usage modes for enterprise software teams.

### Embedded Agent Mode

UniClaw can be embedded into an existing enterprise system as a module inside that system. In this mode, the AI Agent becomes part of the product itself, serving that system's own users, data, and business scenarios.

- Embedded as an in-product AI module
- Supports both user-facing interaction interfaces and agent-style automation
- Uses Skills to define scenarios and system-specific actions inside the host application
- Fits teams that want to add AI Agent capability to an existing enterprise product quickly

### Standalone Agent Mode

UniClaw can also run as an independent enterprise AI Agent system that connects multiple existing systems together. In this mode, it acts as a unified AI layer above those systems rather than belonging to only one of them.

- Runs as an independent AI Agent platform for the enterprise
- Connects and coordinates multiple systems through Providers
- Builds a shared cross-system brain for analysis, judgment, coordination, and execution
- Fits teams that want one unified AI Agent entry point across the enterprise

## Architecture

UniClaw is organized around a thin core plus rich providers.

- Access channels support both embedded in-system experiences and standalone enterprise entry points
- UniClaw Core hosts the API layer, session/config services, and the agent engine
- LLM services are external and replaceable through configuration
- Providers encapsulate authentication, skills, and scripts for each connected enterprise platform
- Enterprise systems remain the source of truth for authorization and auditing

### Overall Architecture

![UniClaw overall architecture](docs/images/architecture/v4-01-overall-architecture.png)

At a high level, requests enter through one of the supported channels, pass through the UniClaw Core, and are executed against enterprise systems through Providers. In embedded mode, the entry point can be an AI panel or module inside an existing enterprise application. In standalone mode, UniClaw exposes an independent AI Agent interface that sits above multiple enterprise systems. In both cases, the core remains lightweight and reusable, while each Provider contains the system-specific integration logic.

### Core Architecture

![UniClaw core architecture](docs/images/architecture/v4-04-agent-core-components.png)

The core runtime in this repository centers on:

- `API Layer`: interactive APIs, WebSocket streaming, and webhook endpoints for both user-driven and programmatic invocation
- `Agent Engine`: routing, prompt building, tool selection, and execution orchestration
- `Session & Memory`: conversation context, persistence, and retrieval
- `Tools & Skills`: reusable execution units exposed to the agent
- `Provider Registry`: registration and discovery of enterprise integrations
- `Execution Context`: dependency injection for auth, tenant, and runtime-scoped data

## Repository Layout

```text
project-root/
├── app/uniclaw/api/         # REST, SSE, WebSocket, gateway orchestration
├── app/uniclaw/agent/       # Agent runner, routing, streaming, prompt building
├── app/uniclaw/channels/    # Channel adapters and registries
├── app/uniclaw/core/        # Config, execution context, provider registry
├── app/uniclaw/memory/      # Memory manager and retrieval
├── app/uniclaw/session/     # Session context, queue, and manager
├── app/uniclaw/skills/      # Skill loading and registry
├── app/uniclaw/tools/       # Built-in tools and tool catalog
├── app/uniclaw/workflow/    # Workflow engine and orchestrator
├── docs/                    # Concepts, tools, channels, and design notes
└── tests/                   # Pytest test suite
```

## Quick Start

### Requirements

- Python 3.11+
- A virtual environment is recommended
- Access to an LLM provider and target enterprise systems for end-to-end integration

### Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure Environment

UniClaw uses `uniclaw.json` for configuration. Create a configuration file in the project root:

```json
{
  "model": {
    "provider": "doubao",
    "model": "your-model-name",
    "api_key": "your-api-key",
    "base_url": "https://ark.cn-beijing.volces.com/api/v3"
  },
  "agent_defaults": {
    "max_retries": 3,
    "timeout": 30
  }
}
```

Configuration options:

- `model.provider` - LLM provider (doubao, openai, etc.)
- `model.model` - Model name
- `model.api_key` - API key for the provider
- `model.base_url` - Base URL for the API endpoint

Adjust the configuration to match your LLM provider and SmartCMP environment before running integration flows.

### Run Tests

```bash
pytest tests/uniclaw -q
```

### Start the Service

Start the backend API server:

```bash
uvicorn app.uniclaw.api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://127.0.0.1:8000`.

### Access the Web UI

Once the service is running, open your browser and navigate to:

```
http://127.0.0.1:8000/
```

The Web UI provides:
- Chat interface powered by DeepChat
- Real-time streaming responses via SSE
- Multi-language support (Chinese / English)
- Session management with conversation history

### Frontend Development

The frontend is located in `app/frontend/` and supports two deployment modes:

**Open Source Mode** (default):
- Source files are served directly without bundling
- No build step required
- Edit files in `app/frontend/scripts/` and refresh browser

**Enterprise Mode**:
```bash
cd app/frontend
npm install
npm run build
```
- Produces minified `dist/app.min.js`
- Update `index.html` to reference the bundled file

**Run Frontend Tests**:
```bash
cd app/frontend
npm test
```

## Development Notes

- This repository currently exposes the UniClaw core as application modules rather than a single documented `main.py` entrypoint
- The API surface lives under `app/uniclaw/api/`
- Core orchestration logic lives under `app/uniclaw/agent/`, `app/uniclaw/workflow/`, and `app/uniclaw/tools/`
- Provider integrations can be added under `app/uniclaw/providers/`

If you are integrating UniClaw into a host service, start by wiring the API layer, execution context, provider registry, and session manager together in your application bootstrap.

## Further Reading

- [Architecture Concepts](docs/concepts/architecture.md)
- [Tooling Documentation](docs/tools/index.md)
- [Channel Documentation](docs/channels/index.md)
- [Automation Documentation](docs/automation/webhook.md)

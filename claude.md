# SkillClaw

An intelligent AI Agent framework with skills, memory, and multi-agent support.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure API key in settings.local.json
# Or set environment variable: export KIMI_API_KEY=your_key

# Run the application
python app.py
```

## Project Structure

```
SkillClaw/
├── core/                      # Core modules
│   ├── __init__.py
│   ├── config.py             # Configuration management
│   ├── skill_registry.py     # Skill discovery and loading
│   ├── memory_manager.py     # Markdown-based memory
│   ├── kimi_client.py        # LLM API client
│   └── agent_core.py         # ReAct agent implementation
├── .claude/
│   ├── skills/               # Skill definitions (.md files)
│   ├── agents/               # Agent configurations
│   ├── memory/               # Persistent memory storage
│   └── agent-memory/         # Runtime agent memory
├── rules/                    # Behavior rules
├── app.py                    # Gradio web interface
├── settings.local.json       # Local configuration
├── USER.md                   # User profile (auto-generated)
└── requirements.txt
```

## Adding Skills

Create a new skill by adding a `.md` file to `.claude/skills/`:

```markdown
---
name: my-skill
description: What this skill does
tags: [coding, analysis]
---

# My Skill

Instructions for the agent when using this skill...
```

## Architecture

- **SkillRegistry**: Scans `.claude/skills/*.md` and auto-registers as tools
- **MemoryManager**: Pure markdown-based persistence (no database)
- **KimiClient**: OpenAI-compatible API with streaming and retry
- **AgentCore**: ReAct loop (Memory → Planning → Tools → Observation → Summary)
- **MultiAgentSystem**: Routes tasks to specialized agents

## License

MIT

# 🦅 SkillClaw

A Claude Code compatible AI Agent framework with skills, memory, and multi-agent support.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features

- 🧩 **Skill System**: Hot-pluggable skills via markdown files
- 🧠 **Persistent Memory**: Local markdown-based storage (zero database)
- 🤖 **Multi-Agent**: Route tasks to specialized agents
- 🔧 **Tool Calling**: Automatic skill/tool invocation
- 🌊 **Streaming**: Real-time response streaming
- 🔄 **ReAct Loop**: Memory → Planning → Tools → Observation → Summary
- 💻 **Gradio UI**: Web interface with chat, memory panel, and agent switching

## 🚀 Quick Start

### 1. Installation

```bash
# Clone or create the project
git clone <repository-url>
cd SkillClaw

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Edit `settings.local.json`:

```json
{
  "llm": {
    "provider": "kimi",
    "model": "kimi-k2.5",
    "api_base": "https://api.moonshot.cn/v1",
    "api_key": "your-api-key-here"
  }
}
```

Or set environment variable:
```bash
export KIMI_API_KEY=your-api-key-here
```

### 3. Run

```bash
python app.py
```

Open http://localhost:7860 in your browser.

## 📁 Project Structure

```
SkillClaw/
├── core/                      # Core modules
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
├── SOUL.md                   # Agent personality definition
├── AGENTS.md                 # Multi-agent system docs
├── TOOLS.md                  # Tool usage documentation
└── IDENTITY.md               # Agent identity
```

## 🛠️ Creating Skills

Skills are markdown files with YAML frontmatter:

```bash
# Create a new skill
cat > .claude/skills/my-skill.md << 'EOF'
---
name: my-skill
description: What this skill does
version: 1.0.0
author: Your Name
tags: [coding, analysis]
---

# My Skill

You are an expert at [domain].

## Capabilities

1. Describe what you can do
2. List specific tasks
3. Explain limitations

## Usage

When using this skill:
1. Step one
2. Step two
3. Step three
EOF
```

Skills are automatically discovered and registered as tools. No code changes needed!

## 🧠 Memory System

SkillClaw uses pure markdown files for persistence:

- **Session Memory**: `.claude/memory/sessions/*.md`
- **Global Memory**: `.claude/memory/global.md`
- **Entity Memory**: `.claude/memory/entities/*.md`
- **User Profile**: `USER.md` (auto-updated)

### Memory Features

- Automatic session recording
- Global knowledge storage
- User preference tracking
- Hobby and interest recording
- Entity-based memory (projects, people, etc.)

## 🤖 Multi-Agent System

SkillClaw supports multiple specialized agents:

| Agent | Specialization |
|-------|---------------|
| `assistant` | General purpose (default) |
| `coder` | Programming and code review |
| `researcher` | Information gathering and analysis |

Switch agents in the UI or programmatically:

```python
from core import AgentCore, SkillRegistry, MemoryManager, KimiClient

agent = agent_system.get_agent("coder")
result = agent.run("Review this code...")
```

## 🔧 Core Modules

### SkillRegistry

```python
from core import SkillRegistry

skills = SkillRegistry()

# List all skills
all_skills = skills.get_all_skills()

# Search skills
results = skills.search_skills("code")

# Activate a skill
content = skills.activate_skill("code-review")
```

### MemoryManager

```python
from core import MemoryManager

memory = MemoryManager()

# Add global memory
memory.add_global_memory(
    content="User prefers Python",
    category="preferences",
    importance=3
)

# Add user hobby
memory.add_user_hobby("photography", "enjoys landscape photography")

# Search memories
results = memory.search_memories("python")
```

### KimiClient

```python
from core import KimiClient

llm = KimiClient(
    api_key="your-key",
    model="kimi-k2.5"
)

# Regular chat
response = llm.chat(messages=[
    {"role": "user", "content": "Hello!"}
])

# Streaming
for chunk in llm.chat_stream(messages=[...]):
    print(chunk.content, end="")
```

### AgentCore

```python
from core import AgentCore

agent = AgentCore(
    llm_client=llm,
    skill_registry=skills,
    memory_manager=memory
)

# Run with automatic tool calling
result = agent.run("Help me organize my files")
print(result.content)
```

## ⚙️ Configuration

### settings.local.json

```json
{
  "llm": {
    "provider": "kimi",
    "model": "kimi-k2.5",
    "api_base": "https://api.moonshot.cn/v1",
    "api_key": "your-key",
    "temperature": 0.7,
    "max_tokens": 8192,
    "timeout": 60,
    "retry_attempts": 3
  },
  "agent": {
    "max_iterations": 10,
    "enable_streaming": true,
    "auto_save_memory": true
  },
  "memory": {
    "session_ttl_hours": 24,
    "max_context_messages": 50
  },
  "ui": {
    "theme": "default",
    "show_tool_calls": true
  }
}
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `KIMI_API_KEY` | API key for Kimi/Moonshot |
| `OPENAI_API_KEY` | Alternative API key |
| `LLM_MODEL` | Override model name |
| `LLM_API_BASE` | Override API base URL |

## 📝 Example Skills

### Code Review

```markdown
---
name: code-review
description: Reviews code for bugs and best practices
tags: [coding, review]
---

# Code Review Skill

When reviewing code, check for:
1. Security vulnerabilities
2. Performance issues
3. Code style violations
4. Logic errors
```

### API Tester

```markdown
---
name: api-tester
description: Makes HTTP requests and analyzes responses
tags: [api, testing, http]
---

# API Tester

You can make HTTP requests using Python's requests library.
Always show status code, headers, and formatted response body.
```

## 🧪 Development

### Running Tests

```bash
# TODO: Add test suite
```

### Adding New Features

1. Create feature branch
2. Implement in appropriate module
3. Add skill if needed
4. Update documentation
5. Submit PR

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add/update tests
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- Inspired by [agent-skills](https://agentskills.io) standard
- Built for [Claude Code](https://claude.ai/code) compatibility
- Uses [Gradio](https://gradio.app) for UI
- Powered by [Kimi](https://www.moonshot.cn) AI

## 📞 Support

- Issues: [GitHub Issues](https://github.com/yourusername/skillclaw/issues)
- Discussions: [GitHub Discussions](https://github.com/yourusername/skillclaw/discussions)

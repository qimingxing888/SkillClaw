# Multi-Agent System Architecture

SkillClaw supports multiple specialized agents working together to handle different types of tasks efficiently.

## Overview

The `MultiAgentSystem` class orchestrates multiple `AgentCore` instances, each specialized for different domains. Tasks are automatically routed to the most appropriate agent.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              MultiAgentSystem                        │
├─────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  Assistant  │  │    Coder    │  │  Researcher │  │
│  │   Agent     │  │   Agent     │  │   Agent     │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
│         │                │                │          │
│         └────────────────┼────────────────┘          │
│                          ▼                          │
│              ┌─────────────────────┐                │
│              │   Task Router       │                │
│              │  (Keyword/LLM based)│                │
│              └─────────────────────┘                │
└─────────────────────────────────────────────────────┘
```

## Default Agents

### 1. Assistant Agent (Default)

**Role**: General-purpose assistant  
**System Prompt**:
```
You are SkillClaw, a helpful AI assistant.
You have access to various skills and tools to help users.
Be thorough, accurate, and helpful in your responses.
```

**Best For**:
- General questions
- Task coordination
- Multi-step workflows
- When no specialized agent fits

### 2. Coder Agent

**Role**: Programming specialist  
**System Prompt**:
```
You are SkillClaw-Coder, a code specialist.
You excel at programming tasks, code review, debugging, and software architecture.
Use the code-review skill when analyzing code.
```

**Best For**:
- Code review
- Debugging
- Programming help
- Software design
- Technical implementation

**Auto-Activation Keywords**:
- "code", "programming", "debug", "error"
- "function", "class", "algorithm"
- "review", "refactor", "optimize"
- Language names: "python", "javascript", etc.

### 3. Researcher Agent

**Role**: Information specialist  
**System Prompt**:
```
You are SkillClaw-Researcher, a research specialist.
You help with information gathering, analysis, and synthesis.
Use available skills to find and process information.
```

**Best For**:
- Information gathering
- Data analysis
- Fact-checking
- Research synthesis
- Learning new topics

**Auto-Activation Keywords**:
- "research", "find", "search"
- "analyze", "compare", "evaluate"
- "what is", "how does", "explain"

## Task Routing

### Simple Routing (Current)

Based on keyword matching:

```python
def route_task(user_input: str) -> Agent:
    user_lower = user_input.lower()

    # Check agent name matches
    if "coder" in user_lower or any(kw in user_lower for kw in CODE_KEYWORDS):
        return self.agents["coder"]

    if "researcher" in user_lower or any(kw in user_lower for kw in RESEARCH_KEYWORDS):
        return self.agents["researcher"]

    return self.default_agent
```

### LLM-Based Routing (Future)

More sophisticated routing using LLM:

```python
def route_task_llm(user_input: str) -> Agent:
    routing_prompt = f"""
    Given the user request: "{user_input}"

    Which agent should handle this?
    - assistant: General tasks, coordination
    - coder: Programming, debugging, code review
    - researcher: Information gathering, analysis

    Respond with just the agent name.
    """

    response = llm.chat([{"role": "user", "content": routing_prompt}])
    return self.agents.get(response.content.strip(), self.default_agent)
```

## Creating Custom Agents

### Basic Registration

```python
from core import MultiAgentSystem, KimiClient, SkillRegistry, MemoryManager

system = MultiAgentSystem(llm, skills, memory)

system.register_agent(
    name="writer",
    system_prompt="""You are a writing specialist.
You help with content creation, editing, and style improvement.""",
    make_default=False
)
```

### With Specialized Skills

```python
# Create agent that only uses specific skills
system.register_agent(
    name="api-tester",
    system_prompt="""You are an API testing specialist.
Focus on HTTP requests, response analysis, and API documentation."""
)

# The agent can access all skills, but you can filter in custom implementations
```

## Agent Communication

### Direct Handoff

Agents can explicitly transfer to another agent:

```python
# In AgentCore
if "write code" in user_input:
    return self.system.transfer_to("coder", user_input)
```

### Shared Memory

All agents share:
- `MemoryManager` - common memory store
- `SkillRegistry` - all available skills
- Conversation history (within session)

### Independent State

Each agent maintains:
- Own system prompt
- Tool handler registrations
- Current state

## Use Cases

### 1. Complex Workflow

```
User: "Build a web scraper that analyzes news sentiment"

1. Researcher: Research sentiment analysis techniques
2. Coder: Implement the scraper
3. Assistant: Integrate and test
```

### 2. Code Review Pipeline

```
User: "Review this PR and check for security issues"

1. Coder: Review code quality
2. Researcher: Check security best practices
3. Assistant: Summarize findings
```

### 3. Learning Journey

```
User: "I want to learn about machine learning"

1. Researcher: Create learning plan
2. Assistant: Guide through concepts
3. Coder: Provide code examples
```

## Configuration

### Agent Definitions

Agents can be defined in `.claude/agents/`:

```yaml
# .claude/agents/coder.yaml
name: coder
description: Programming specialist
system_prompt: |
  You are SkillClaw-Coder...
activation_keywords:
  - code
  - programming
  - debug
skills:
  - code-review
  - git-helper
```

### Runtime Selection

Users can explicitly select agents:

```python
# Force specific agent
result = system.run("Help me", agent_name="coder")

# UI dropdown selection
agent_dropdown = gr.Dropdown(choices=system.list_agents())
```

## Future Enhancements

1. **Hierarchical Agents**: Manager agents that delegate to workers
2. **Parallel Execution**: Multiple agents working simultaneously
3. **Agent Specialization**: Auto-train agents from usage patterns
4. **Collaborative Problem Solving**: Agents discussing solutions
5. **Dynamic Agent Creation**: Spawn agents for specific tasks

## Best Practices

1. **Clear Boundaries**: Each agent should have a distinct domain
2. **Shared Context**: Maintain common memory for user preferences
3. **Graceful Degradation**: If routing fails, use default agent
4. **User Control**: Allow explicit agent selection when needed
5. **Transparent Routing**: Show user which agent is handling their request

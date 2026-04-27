# Tool System

SkillClaw's tool system enables agents to interact with the world through skills and built-in capabilities.

## Overview

Tools are functions that the LLM can call to perform actions. They are defined using the OpenAI function calling format and registered with the agent.

```
User Input → LLM → [Tool Call?] → Execute Tool → Return Result → LLM → Final Response
                    ↓
              No Tool Call
                    ↓
            Direct Response
```

## Tool Types

### 1. Skill-Based Tools

Automatically generated from skill definitions:

```markdown
---
name: api-tester
description: Makes HTTP requests to APIs
---
```

Becomes:

```python
{
  "type": "function",
  "function": {
    "name": "skill_api_tester",
    "description": "[api-tester] Makes HTTP requests to APIs",
    "parameters": {
      "type": "object",
      "properties": {
        "context": {
          "type": "string",
          "description": "The context or task details for the skill"
        }
      },
      "required": ["context"]
    }
  }
}
```

### 2. Built-in Tools

Core capabilities available to all agents:

#### search_memory

Search the memory system for relevant information.

```python
{
  "name": "search_memory",
  "description": "Search the memory for relevant information",
  "parameters": {
    "query": "string"
  }
}
```

Usage:
```json
{
  "query": "user's favorite programming language"
}
```

#### add_memory

Add information to persistent memory.

```python
{
  "name": "add_memory",
  "description": "Add a new memory entry",
  "parameters": {
    "content": "string",
    "category": "string (optional)",
    "importance": "integer 1-5 (optional)"
  }
}
```

Usage:
```json
{
  "content": "User prefers Python for data science",
  "category": "preferences",
  "importance": 3
}
```

#### list_skills

List all available skills.

```python
{
  "name": "list_skills",
  "description": "List all available skills",
  "parameters": {}
}
```

### 3. Custom Tools

Register custom tools with the agent:

```python
from core import AgentCore

agent = AgentCore(...)

# Define tool handler
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression"""
    try:
        result = eval(expression)  # Safe in controlled environment
        return f"Result: {result}"
    except Exception as e:
        return f"Error: {e}"

# Register tool
agent.tool_handlers["calculate"] = calculate

# Define tool schema
calculate_tool = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": "Calculate a mathematical expression",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate"
                }
            },
            "required": ["expression"]
        }
    }
}

# Add to tools list
agent.custom_tools = [calculate_tool]
```

## Tool Execution Flow

### 1. LLM Decides to Call Tool

```
User: "What's the weather in Tokyo?"

LLM Response:
{
  "content": null,
  "tool_calls": [
    {
      "id": "call_123",
      "type": "function",
      "function": {
        "name": "skill_weather",
        "arguments": '{"context": "Get weather for Tokyo"}'
      }
    }
  ]
}
```

### 2. Tool is Executed

```python
tool_call = ToolCall(
    id="call_123",
    name="skill_weather",
    arguments={"context": "Get weather for Tokyo"}
)

result = agent._execute_tool(tool_call)
# Result: "Skill 'weather' activated.\n\n[Skill content...]"
```

### 3. Result Returned to LLM

```python
messages.append({
    "role": "tool",
    "tool_call_id": "call_123",
    "content": result
})

# LLM generates final response
```

### 4. Final Response

```
SkillClaw: "The weather in Tokyo is currently 22°C and sunny..."
```

## Tool Best Practices

### 1. Clear Descriptions

Tool descriptions should be explicit about what the tool does:

```python
# Good
description = "Search the memory for information about the user's preferences and past conversations"

# Bad
description = "Search memory"
```

### 2. Specific Parameters

Define clear, specific parameters:

```python
# Good
"parameters": {
    "query": {
        "type": "string",
        "description": "Search query to find relevant memories about user's preferences, hobbies, or past interactions"
    },
    "limit": {
        "type": "integer",
        "description": "Maximum number of results to return (default: 5)"
    }
}

# Bad
"parameters": {
    "q": {"type": "string"}
}
```

### 3. Error Handling

Tools should handle errors gracefully:

```python
def my_tool(param: str) -> str:
    try:
        result = risky_operation(param)
        return f"Success: {result}"
    except ValueError as e:
        return f"Invalid input: {e}"
    except Exception as e:
        return f"Error: {e}"
```

### 4. Result Formatting

Return results in a format the LLM can easily use:

```python
# Good
return json.dumps({
    "status": "success",
    "data": result,
    "metadata": {"count": len(result)}
})

# Bad
return str(result)  # Ambiguous format
```

## Tool Registration

### Programmatic Registration

```python
agent = AgentCore(...)

# Register handler
agent.tool_handlers["my_tool"] = my_tool_function

# Add to available tools
agent.additional_tools = [my_tool_definition]
```

### Skill-Based Registration

Skills automatically become tools when placed in `.claude/skills/`:

```bash
cp my-skill.md .claude/skills/
# Automatically available as skill_my_skill tool
```

### MCP Server Registration

MCP (Model Context Protocol) servers can be registered in `mcp.json`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/files"]
    },
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"]
    }
  }
}
```

## Advanced Tool Patterns

### 1. Chained Tools

Tools that call other tools:

```python
def analyze_code(code: str) -> str:
    # Call review skill
    review = agent.tool_handlers["skill_code_review"](context=f"Review: {code}")

    # Call security check
    security = agent.tool_handlers["skill_security"](context=f"Check: {code}")

    return f"Review:\n{review}\n\nSecurity:\n{security}"
```

### 2. Conditional Tools

Tools that execute based on context:

```python
def smart_search(query: str, context: str = "") -> str:
    # Decide which search to use
    if "preference" in context or "like" in context:
        return memory.search_memories(query)
    else:
        return web_search(query)
```

### 3. Stateful Tools

Tools that maintain state:

```python
class StatefulTool:
    def __init__(self):
        self.history = []

    def execute(self, command: str) -> str:
        self.history.append(command)

        if command == "undo":
            return self._undo()

        # Process command
        return result
```

## Tool Security

### Input Validation

Always validate tool inputs:

```python
def safe_tool(user_input: str) -> str:
    # Sanitize input
    if ";" in user_input or "|" in user_input:
        return "Error: Invalid characters in input"

    # Validate type
    if not isinstance(user_input, str):
        return "Error: Input must be a string"

    # Execute
    return process(user_input)
```

### Permission Checks

For sensitive operations:

```python
def delete_file(path: str) -> str:
    # Check if path is allowed
    allowed_paths = ["/tmp/", "/var/data/"]
    if not any(path.startswith(p) for p in allowed_paths):
        return "Error: Path not allowed"

    # Additional confirmation for destructive operations
    return f"Ready to delete {path}. Confirm with confirm_delete tool."
```

## Debugging Tools

### Tool Call Logging

Enable verbose logging:

```python
agent = AgentCore(..., debug=True)

# Logs:
# [TOOL CALL] skill_api_tester: {"url": "example.com"}
# [TOOL RESULT] Status: 200, Content: {...}
```

### Tool Testing

Test tools independently:

```python
def test_tool():
    agent = AgentCore(...)

    # Test specific tool
    result = agent.tool_handlers["calculate"](expression="2 + 2")
    assert result == "Result: 4"
```

## Reference

### OpenAI Tool Format

```python
{
    "type": "function",
    "function": {
        "name": "function_name",
        "description": "What this function does",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "Description of param1"
                },
                "param2": {
                    "type": "integer",
                    "description": "Description of param2"
                }
            },
            "required": ["param1"]
        }
    }
}
```

### Tool Response Format

```python
{
    "role": "tool",
    "tool_call_id": "call_xxx",
    "content": "Result of tool execution"
}
```

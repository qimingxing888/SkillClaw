"""
AgentCore - ReAct loop implementation with multi-agent support
Memory -> Planning -> Tool Calling -> Observation -> Summary
"""

import json
import re
from typing import Dict, List, Optional, Any, Callable, Generator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .kimi_client import KimiClient, ChatResponse, StreamChunk
from .skill_registry import SkillRegistry
from .memory_manager import MemoryManager


class AgentState(Enum):
    """Agent execution states"""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    OBSERVING = "observing"
    SUMMARIZING = "summarizing"
    FINISHED = "finished"
    ERROR = "error"


@dataclass
class ToolCall:
    """A tool call request"""
    id: str
    name: str
    arguments: Dict[str, Any]
    result: Optional[str] = None
    error: Optional[str] = None
    executed_at: Optional[datetime] = None


@dataclass
class AgentStep:
    """A single step in the agent's execution"""
    number: int
    state: AgentState
    thought: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    observation: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AgentResult:
    """Final result of an agent execution"""
    content: str
    steps: List[AgentStep]
    tool_calls_count: int
    duration_seconds: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentCore:
    """
    Core agent implementation with ReAct loop.
    Supports planning, tool calling, observation, and summarization.
    """

    def __init__(
        self,
        llm_client: KimiClient,
        skill_registry: SkillRegistry,
        memory_manager: MemoryManager,
        max_iterations: int = 10,
        system_prompt: Optional[str] = None
    ):
        self.llm = llm_client
        self.skills = skill_registry
        self.memory = memory_manager
        self.max_iterations = max_iterations
        self.system_prompt = system_prompt or self._default_system_prompt()

        # Tool handlers
        self.tool_handlers: Dict[str, Callable] = {}
        self._register_default_tools()

        # State
        self.current_state = AgentState.IDLE
        self.conversation_history: List[Dict] = []

    def _default_system_prompt(self) -> str:
        """Generate default system prompt"""
        return """You are SkillClaw, an AI assistant with access to specialized skills and tools.

Your job is to help users by:
1. Understanding their requests
2. Planning the approach
3. Using available skills and tools when needed
4. Providing clear, helpful responses

When you need to use a skill or tool:
- Call the appropriate function with the required parameters
- Wait for the result before proceeding
- Incorporate the result into your response

Always be helpful, accurate, and thorough in your responses."""

    def _register_default_tools(self):
        """Register built-in tool handlers"""
        self.tool_handlers["search_memory"] = self._tool_search_memory
        self.tool_handlers["add_memory"] = self._tool_add_memory
        self.tool_handlers["list_skills"] = self._tool_list_skills

    def _tool_search_memory(self, query: str, **kwargs) -> str:
        """Search memory for relevant information"""
        results = self.memory.search_memories(query, limit=5)
        if results:
            lines = ["Found relevant memories:"]
            for mem in results:
                lines.append(f"- {mem.content}")
            return "\n".join(lines)
        return "No relevant memories found."

    def _tool_add_memory(self, content: str, category: str = "general", **kwargs) -> str:
        """Add a memory entry"""
        self.memory.add_global_memory(
            content=content,
            category=category,
            importance=kwargs.get("importance", 1),
            tags=kwargs.get("tags", [])
        )
        return f"Memory added: {content[:50]}..."

    def _tool_list_skills(self, **kwargs) -> str:
        """List available skills"""
        skills = self.skills.get_all_skills()
        lines = ["Available skills:"]
        for skill in skills:
            lines.append(f"- {skill.name}: {skill.description}")
        return "\n".join(lines)

    def _build_messages(self, user_input: str, context: Optional[str] = None) -> List[Dict]:
        """Build message list for LLM"""
        messages = [{"role": "system", "content": self.system_prompt}]

        # Add user context from memory
        user_context = self.memory.get_user_context_prompt()
        if user_context:
            messages.append({"role": "system", "content": f"User context:\n{user_context}"})

        # Add recent conversation history (limited)
        recent_history = self.conversation_history[-10:]
        messages.extend(recent_history)

        # Add current user input
        content = user_input
        if context:
            content = f"Context: {context}\n\nUser: {user_input}"
        messages.append({"role": "user", "content": content})

        return messages

    def _get_tools(self) -> List[Dict]:
        """Get available tools from skills and built-ins"""
        tools = self.skills.get_tool_definitions()

        # Add built-in tools
        tools.extend([
            {
                "type": "function",
                "function": {
                    "name": "search_memory",
                    "description": "Search the memory for relevant information about the user or past conversations",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "add_memory",
                    "description": "Add a new memory entry for future reference",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "Content to remember"
                            },
                            "category": {
                                "type": "string",
                                "description": "Category of the memory"
                            },
                            "importance": {
                                "type": "integer",
                                "description": "Importance level (1-5)"
                            }
                        },
                        "required": ["content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_skills",
                    "description": "List all available skills",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
        ])

        return tools

    def _execute_tool(self, tool_call: ToolCall) -> str:
        """Execute a tool call and return result"""
        tool_name = tool_call.name
        arguments = tool_call.arguments

        # Handle skill activation (skill_* prefix)
        if tool_name.startswith("skill_"):
            skill_name = tool_name.replace("skill_", "")
            # Try to find original skill name
            for s in self.skills.get_all_skills():
                safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', s.name)
                if safe_name == skill_name:
                    skill_name = s.name
                    break

            skill_content = self.skills.activate_skill(skill_name)
            if skill_content:
                return f"Skill '{skill_name}' activated.\n\n{skill_content}"
            return f"Error: Skill '{skill_name}' not found"

        # Handle built-in tools
        if tool_name in self.tool_handlers:
            try:
                result = self.tool_handlers[tool_name](**arguments)
                return result
            except Exception as e:
                return f"Error executing {tool_name}: {str(e)}"

        # Handle custom tools registered by skills
        return f"Unknown tool: {tool_name}"

    def run(
        self,
        user_input: str,
        context: Optional[str] = None,
        stream: bool = False
    ) -> AgentResult:
        """
        Run the agent with user input.

        Args:
            user_input: The user's message
            context: Optional additional context
            stream: Whether to stream the response

        Returns:
            AgentResult with the final response
        """
        import time
        start_time = time.time()

        steps: List[AgentStep] = []
        total_tool_calls = 0

        # Add user message to history
        self.memory.add_message_to_session("user", user_input)

        # Build messages
        messages = self._build_messages(user_input, context)
        tools = self._get_tools()

        # ReAct loop
        iteration = 0
        final_response = ""

        while iteration < self.max_iterations:
            iteration += 1
            self.current_state = AgentState.PLANNING

            step = AgentStep(number=iteration, state=self.current_state)

            try:
                # Get LLM response
                response = self.llm.chat(
                    messages=messages,
                    tools=tools,
                    tool_choice="auto"
                )

                # Check for tool calls
                if response.tool_calls:
                    self.current_state = AgentState.EXECUTING
                    step.state = self.current_state
                    step.thought = response.content or "I'll use the available tools to help with this."

                    # Process each tool call
                    for tc in response.tool_calls:
                        tool_call = ToolCall(
                            id=tc["id"],
                            name=tc["function"]["name"],
                            arguments=json.loads(tc["function"]["arguments"]),
                            executed_at=datetime.now()
                        )

                        # Execute the tool
                        result = self._execute_tool(tool_call)
                        tool_call.result = result
                        step.tool_calls.append(tool_call)
                        total_tool_calls += 1

                    # Build observation
                    observations = []
                    for tc in step.tool_calls:
                        observations.append(f"Tool '{tc.name}' result:\n{tc.result}")
                    step.observation = "\n\n".join(observations)

                    # Add to messages for next iteration
                    messages.append({
                        "role": "assistant",
                        "content": response.content or "",
                        "reasoning_content": response.reasoning_content,  # Required for Kimi K2.5 thinking mode
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.arguments)
                                }
                            }
                            for tc in step.tool_calls
                        ]
                    })

                    # Add tool results
                    for tc in step.tool_calls:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": tc.result or ""
                        })

                    steps.append(step)
                    continue  # Next iteration to process tool results

                else:
                    # No tool calls - we have a final response
                    self.current_state = AgentState.FINISHED
                    final_response = response.content or ""

                    step.state = self.current_state
                    step.thought = "Providing final response."
                    steps.append(step)

                    # Add to conversation history
                    self.conversation_history.append({
                        "role": "user",
                        "content": user_input
                    })
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": final_response,
                        "reasoning_content": response.reasoning_content  # Required for Kimi K2.5 thinking mode
                    })

                    # Add to session memory
                    self.memory.add_message_to_session("assistant", final_response)

                    break

            except Exception as e:
                self.current_state = AgentState.ERROR
                step.state = self.current_state
                step.observation = f"Error: {str(e)}"
                steps.append(step)
                final_response = f"I encountered an error: {str(e)}"
                break

        duration = time.time() - start_time

        return AgentResult(
            content=final_response,
            steps=steps,
            tool_calls_count=total_tool_calls,
            duration_seconds=duration,
            metadata={
                "iterations": iteration,
                "model": self.llm.model,
                "finish_state": self.current_state.value
            }
        )

    def run_stream(
        self,
        user_input: str,
        context: Optional[str] = None
    ) -> Generator[tuple[str, Optional[AgentStep]], None, AgentResult]:
        """
        Run the agent with streaming response.

        Yields:
            (text_chunk, current_step) tuples

        Returns:
            Final AgentResult
        """
        import time
        start_time = time.time()

        steps: List[AgentStep] = []
        total_tool_calls = 0

        # Add user message to history
        self.memory.add_message_to_session("user", user_input)

        # Build messages
        messages = self._build_messages(user_input, context)
        tools = self._get_tools()

        # For simplicity, non-streaming execution with streaming final response
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            try:
                response = self.llm.chat(
                    messages=messages,
                    tools=tools,
                    tool_choice="auto"
                )

                if response.tool_calls:
                    step = AgentStep(
                        number=iteration,
                        state=AgentState.EXECUTING,
                        thought=response.content or "Executing tools..."
                    )

                    for tc in response.tool_calls:
                        tool_call = ToolCall(
                            id=tc["id"],
                            name=tc["function"]["name"],
                            arguments=json.loads(tc["function"]["arguments"]),
                            executed_at=datetime.now()
                        )

                        # Yield tool execution status
                        yield (f"\n[Using tool: {tool_call.name}]\n", step)

                        result = self._execute_tool(tool_call)
                        tool_call.result = result
                        step.tool_calls.append(tool_call)
                        total_tool_calls += 1

                    step.observation = "\n".join([f"{tc.name}: {tc.result[:100]}..." for tc in step.tool_calls])
                    steps.append(step)

                    # Update messages
                    messages.append({
                        "role": "assistant",
                        "content": response.content or "",
                        "reasoning_content": response.reasoning_content,  # Required for Kimi K2.5 thinking mode
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.arguments)
                                }
                            }
                            for tc in step.tool_calls
                        ]
                    })

                    for tc in step.tool_calls:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": tc.result or ""
                        })

                    continue

                else:
                    # Stream the final response
                    final_response = ""
                    step = AgentStep(
                        number=iteration,
                        state=AgentState.SUMMARIZING
                    )

                    for chunk in self.llm.chat_stream(
                        messages=messages,
                        tools=None
                    ):
                        final_response += chunk.content
                        yield (chunk.content, step)

                    step.thought = "Final response complete."
                    steps.append(step)

                    # Update history
                    self.conversation_history.append({
                        "role": "user",
                        "content": user_input
                    })
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": final_response,
                        "reasoning_content": response.reasoning_content  # Required for Kimi K2.5 thinking mode
                    })

                    self.memory.add_message_to_session("assistant", final_response)

                    duration = time.time() - start_time

                    return AgentResult(
                        content=final_response,
                        steps=steps,
                        tool_calls_count=total_tool_calls,
                        duration_seconds=duration,
                        metadata={
                            "iterations": iteration,
                            "model": self.llm.model,
                            "finish_state": "finished"
                        }
                    )

            except Exception as e:
                error_msg = f"Error: {str(e)}"
                yield (f"\n[{error_msg}]\n", None)

                duration = time.time() - start_time

                return AgentResult(
                    content=error_msg,
                    steps=steps,
                    tool_calls_count=total_tool_calls,
                    duration_seconds=duration,
                    metadata={"error": str(e)}
                )

        # Max iterations reached
        duration = time.time() - start_time
        return AgentResult(
            content="Maximum iterations reached without conclusion.",
            steps=steps,
            tool_calls_count=total_tool_calls,
            duration_seconds=duration,
            metadata={"error": "max_iterations"}
        )


class MultiAgentSystem:
    """
    Multi-agent orchestration system.
    Manages multiple specialized agents and routes tasks between them.
    """

    def __init__(
        self,
        llm_client: KimiClient,
        skill_registry: SkillRegistry,
        memory_manager: MemoryManager
    ):
        self.llm = llm_client
        self.skills = skill_registry
        self.memory = memory_manager

        self.agents: Dict[str, AgentCore] = {}
        self.default_agent: Optional[str] = None

    def register_agent(
        self,
        name: str,
        system_prompt: str,
        specialized_skills: Optional[List[str]] = None,
        make_default: bool = False
    ):
        """Register a specialized agent"""
        agent = AgentCore(
            llm_client=self.llm,
            skill_registry=self.skills,
            memory_manager=self.memory,
            system_prompt=system_prompt
        )

        self.agents[name] = agent

        if make_default or self.default_agent is None:
            self.default_agent = name

    def get_agent(self, name: Optional[str] = None) -> AgentCore:
        """Get an agent by name, or default agent"""
        if name and name in self.agents:
            return self.agents[name]
        if self.default_agent:
            return self.agents[self.default_agent]
        raise ValueError("No agents registered")

    def route_task(
        self,
        user_input: str,
        context: Optional[str] = None
    ) -> tuple[str, AgentCore]:
        """
        Route a task to the most appropriate agent.
        Returns (agent_name, agent) tuple.
        """
        if len(self.agents) <= 1:
            return self.default_agent, self.get_agent()

        # Simple routing based on keywords
        # Could be enhanced with LLM-based routing
        user_lower = user_input.lower()

        for name, agent in self.agents.items():
            # Check if agent name or skills match the query
            if name.lower() in user_lower:
                return name, agent

        # Default to main agent
        return self.default_agent, self.get_agent()

    def run(
        self,
        user_input: str,
        agent_name: Optional[str] = None,
        context: Optional[str] = None
    ) -> AgentResult:
        """Run the appropriate agent for the task"""
        if agent_name:
            agent = self.get_agent(agent_name)
        else:
            _, agent = self.route_task(user_input, context)

        return agent.run(user_input, context)

    def list_agents(self) -> List[Dict]:
        """List all registered agents"""
        return [
            {
                "name": name,
                "is_default": name == self.default_agent,
                "system_prompt_preview": agent.system_prompt[:100] + "..."
            }
            for name, agent in self.agents.items()
        ]


# Convenience alias
ReActAgent = AgentCore

"""
SkillClaw - Gradio Web Interface
Multi-turn chat, tool status visualization, memory panel, agent switching
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Generator
from datetime import datetime

import gradio as gr

# Add core to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import Config
from core.skill_registry import SkillRegistry
from core.memory_manager import MemoryManager
from core.kimi_client import KimiClient
from core.agent_core import MultiAgentSystem, AgentState


class SkillClawUI:
    """Gradio-based UI for SkillClaw"""

    def __init__(self):
        self.config = Config()
        self.skills = SkillRegistry()
        self.memory = MemoryManager()

        # Initialize LLM client
        self.llm = KimiClient(
            api_key=self.config.llm.api_key,
            base_url=self.config.llm.api_base,
            model=self.config.llm.model,
            temperature=self.config.llm.temperature,
            max_tokens=self.config.llm.max_tokens,
            timeout=self.config.llm.timeout,
            retry_attempts=self.config.llm.retry_attempts
        )

        # Initialize multi-agent system
        self.agent_system = MultiAgentSystem(
            llm_client=self.llm,
            skill_registry=self.skills,
            memory_manager=self.memory
        )

        # Register default agents
        self._setup_agents()

        # UI state
        self.current_agent = self.agent_system.default_agent
        self.chat_history: List[Tuple[str, str]] = []
        self.tool_status = []

    def _setup_agents(self):
        """Register default agents"""
        # Main assistant
        self.agent_system.register_agent(
            name="assistant",
            system_prompt="""You are SkillClaw, a helpful AI assistant.
You have access to various skills and tools to help users.
Be thorough, accurate, and helpful in your responses.""",
            make_default=True
        )

        # Code specialist
        self.agent_system.register_agent(
            name="coder",
            system_prompt="""You are SkillClaw-Coder, a code specialist.
You excel at programming tasks, code review, debugging, and software architecture.
Use the code-review skill when analyzing code."""
        )

        # Research specialist
        self.agent_system.register_agent(
            name="researcher",
            system_prompt="""You are SkillClaw-Researcher, a research specialist.
You help with information gathering, analysis, and synthesis.
Use available skills to find and process information."""
        )

    def _format_message(self, role: str, content: str) -> str:
        """Format a message for display"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        if role == "user":
            return f"**You** ({timestamp}):\n{content}"
        else:
            return f"**SkillClaw** ({timestamp}):\n{content}"

    def _get_memory_panel_content(self) -> str:
        """Generate memory panel content"""
        lines = ["## 🧠 Memory Status\n"]

        # User profile
        profile = self.memory.get_user_profile()
        if profile:
            lines.append("### User Profile")
            prefs = profile.get("preferences", {})
            for key, data in prefs.items():
                lines.append(f"- **{key}**: {data['value']}")

            hobbies = profile.get("hobbies", {})
            if hobbies:
                lines.append("\n### Hobbies")
                for hobby in hobbies.keys():
                    lines.append(f"- {hobby}")
            lines.append("")

        # Recent memories
        memories = self.memory.get_global_memories(limit=5)
        if memories:
            lines.append("### Recent Memories")
            for mem in memories:
                lines.append(f"- {mem.content[:60]}...")
            lines.append("")

        # Current session
        if self.memory.current_session:
            lines.append(f"### Current Session")
            lines.append(f"- **ID**: {self.memory.current_session.id[:8]}...")
            lines.append(f"- **Messages**: {len(self.memory.current_session.messages)}")
            lines.append(f"- **Title**: {self.memory.current_session.title}")

        return "\n".join(lines) if len(lines) > 2 else "No memory data yet."

    def _get_skills_panel_content(self) -> str:
        """Generate skills panel content"""
        lines = ["## 🛠️ Available Skills\n"]

        for skill in self.skills.get_all_skills():
            lines.append(f"### {skill.name}")
            lines.append(f"*{skill.description}*")
            if skill.tags:
                lines.append(f"Tags: {', '.join(skill.tags)}")
            lines.append("")

        return "\n".join(lines) if len(lines) > 2 else "No skills loaded."

    def chat(
        self,
        message: str,
        history: List[Dict],
        agent_name: str,
        show_tool_calls: bool
    ) -> Generator[Tuple[List[Dict], str, str], None, None]:
        """
        Process a chat message.

        Returns:
            Generator yielding (chat_history, memory_panel, tool_status)
        """
        if not message.strip():
            yield history, self._get_memory_panel_content(), ""
            return

        # Add user message to history (using messages format for Gradio 6.0+)
        history.append({"role": "user", "content": message})
        # Add empty assistant message placeholder
        history.append({"role": "assistant", "content": ""})
        yield history, self._get_memory_panel_content(), "Processing..."

        try:
            # Get agent
            agent = self.agent_system.get_agent(agent_name)

            # Stream the response
            full_response = ""
            tool_status_lines = []

            for chunk, step in agent.run_stream(message):
                full_response += chunk
                # Update the last assistant message
                if history and history[-1]["role"] == "assistant":
                    history[-1]["content"] = full_response

                # Update tool status
                if step and step.tool_calls:
                    tool_status_lines = []
                    for tc in step.tool_calls:
                        status = "✅" if not tc.error else "❌"
                        tool_status_lines.append(
                            f"{status} **{tc.name}**: {tc.result[:80] if tc.result else '...'}"
                        )

                yield (
                    history,
                    self._get_memory_panel_content(),
                    "\n".join(tool_status_lines) if tool_status_lines else "Thinking..."
                )

            # Final update
            yield (
                history,
                self._get_memory_panel_content(),
                "Done" if not tool_status_lines else "\n".join(tool_status_lines)
            )

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            # Update the last assistant message with error
            if history and history[-1]["role"] == "assistant":
                history[-1]["content"] = error_msg
            yield history, self._get_memory_panel_content(), f"❌ {error_msg}"

    def new_session(self) -> Tuple[List[Dict], str, str]:
        """Start a new session"""
        self.memory.create_session()
        self.chat_history = []
        return [], self._get_memory_panel_content(), "New session started"

    def load_session(self, session_id: str) -> Tuple[List[Dict], str, str]:
        """Load a previous session"""
        session = self.memory.get_session(session_id)
        if not session:
            return [], self._get_memory_panel_content(), "Session not found"

        self.memory.current_session = session

        # Convert messages to chat format (using messages format for Gradio 6.0+)
        chat_history = []
        for msg in session.messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role in ["user","assistant"]:
                # Use messages format: {"role": "user"/"assistant", "content": "..."}
                chat_history.append({"role": role, "content": content})

        return chat_history, self._get_memory_panel_content(), f"Loaded: {session.title}"

    def list_sessions(self) -> List[Dict]:
        """List all sessions for dropdown"""
        sessions = self.memory.list_sessions(limit=20)
        return [
            {"label": f"{s['title']} ({s['updated_at'][:10]})", "value": s['id']}
            for s in sessions
        ]

    def add_memory(self, content: str, category: str) -> str:
        """Add a memory entry"""
        if not content.strip():
            return "Memory content cannot be empty"

        self.memory.add_global_memory(
            content=content,
            category=category,
            importance=2
        )
        return f"Added memory: {content[:50]}..."

    def search_memory(self, query: str) -> str:
        """Search memories"""
        if not query.strip():
            return "Please enter a search query"

        results = self.memory.search_memories(query, limit=10)
        if not results:
            return "No memories found matching your query."

        lines = [f"### Search Results for '{query}'\n"]
        for mem in results:
            lines.append(f"- **{mem.category}**: {mem.content}")

        return "\n".join(lines)

    def reload_skills(self) -> str:
        """Reload all skills"""
        count = self.skills.reload_all()
        return f"Reloaded {count} skills"

    def get_system_info(self) -> str:
        """Get system information"""
        info = {
            "Model": self.config.llm.model,
            "API Base": self.config.llm.api_base,
            "Skills Loaded": len(self.skills.get_all_skills()),
            "Active Agent": self.current_agent,
            "Memory Sessions": len(self.memory.list_sessions()),
            "Current Session": self.memory.current_session.id if self.memory.current_session else "None"
        }

        lines = ["### System Information\n"]
        for key, value in info.items():
            lines.append(f"- **{key}**: {value}")

        return "\n".join(lines)

    def build_ui(self) -> gr.Blocks:
        """Build the Gradio UI"""
        with gr.Blocks(
            title="SkillClaw - AI Agent"
        ) as app:
            gr.Markdown("# 🦅 SkillClaw - AI Agent with Skills")
            gr.Markdown("An intelligent agent system with skills, memory, and multi-agent support.")

            with gr.Row():
                # Left sidebar - Controls
                with gr.Column(scale=1):
                    gr.Markdown("### 🤖 Agent Selection")
                    agent_dropdown = gr.Dropdown(
                        choices=["assistant", "coder", "researcher"],
                        value="assistant",
                        label="Select Agent"
                    )

                    with gr.Accordion("📁 Session Management", open=False):
                        new_session_btn = gr.Button("🆕 New Session", variant="primary")
                        session_dropdown = gr.Dropdown(
                            choices=[],  # Will be populated
                            label="Load Previous Session"
                        )
                        load_session_btn = gr.Button("📂 Load Session")
                        refresh_sessions_btn = gr.Button("🔄 Refresh List")

                    with gr.Accordion("🧠 Memory Tools", open=False):
                        memory_content = gr.Textbox(
                            label="Memory Content",
                            placeholder="Enter something to remember..."
                        )
                        memory_category = gr.Textbox(
                            label="Category",
                            value="general"
                        )
                        add_memory_btn = gr.Button("💾 Add Memory")
                        memory_result = gr.Textbox(label="Result", interactive=False)

                        gr.Markdown("---")
                        search_query = gr.Textbox(
                            label="Search Memories",
                            placeholder="Enter search query..."
                        )
                        search_btn = gr.Button("🔍 Search")
                        search_result = gr.Textbox(label="Search Results", interactive=False)

                    with gr.Accordion("⚙️ System", open=False):
                        reload_skills_btn = gr.Button("🔄 Reload Skills")
                        reload_result = gr.Textbox(label="Status", interactive=False)
                        system_info = gr.Markdown(self.get_system_info())
                        refresh_info_btn = gr.Button("🔄 Refresh Info")

                # Middle - Chat
                with gr.Column(scale=3):
                    chatbot = gr.Chatbot(
                        label="Conversation",
                        height=500
                    )

                    with gr.Row():
                        msg_input = gr.Textbox(
                            label="Message",
                            placeholder="Type your message here...",
                            scale=8,
                            show_label=False
                        )
                        submit_btn = gr.Button("Send", scale=1, variant="primary")

                    with gr.Row():
                        show_tools_checkbox = gr.Checkbox(
                            label="Show Tool Calls",
                            value=True
                        )
                        clear_btn = gr.Button("Clear Chat")

                    tool_status = gr.Textbox(
                        label="Tool Status",
                        interactive=False,
                        visible=True
                    )

                # Right sidebar - Memory & Skills
                with gr.Column(scale=1):
                    gr.Markdown("### 📊 Status")
                    memory_panel = gr.Markdown(
                        self._get_memory_panel_content(),
                        elem_classes=["panel-container"]
                    )

                    gr.Markdown("### 🛠️ Skills")
                    skills_panel = gr.Markdown(
                        self._get_skills_panel_content(),
                        elem_classes=["panel-container"]
                    )

            # Event handlers
            submit_btn.click(
                fn=self.chat,
                inputs=[msg_input, chatbot, agent_dropdown, show_tools_checkbox],
                outputs=[chatbot, memory_panel, tool_status]
            ).then(
                fn=lambda: "",
                outputs=[msg_input]
            )

            msg_input.submit(
                fn=self.chat,
                inputs=[msg_input, chatbot, agent_dropdown, show_tools_checkbox],
                outputs=[chatbot, memory_panel, tool_status]
            ).then(
                fn=lambda: "",
                outputs=[msg_input]
            )

            clear_btn.click(
                fn=lambda: ([], self._get_memory_panel_content(), "Clear Chat"),
                outputs=[chatbot, memory_panel, tool_status]
            )

            new_session_btn.click(
                fn=self.new_session,
                outputs=[chatbot, memory_panel, tool_status]
            )

            load_session_btn.click(
                fn=self.load_session,
                inputs=[session_dropdown],
                outputs=[chatbot, memory_panel, tool_status]
            )

            def update_session_list():
                sessions = self.list_sessions()
                return gr.Dropdown(choices=[s["value"] for s in sessions])

            refresh_sessions_btn.click(
                fn=update_session_list,
                outputs=[session_dropdown]
            )

            add_memory_btn.click(
                fn=self.add_memory,
                inputs=[memory_content, memory_category],
                outputs=[memory_result]
            ).then(
                fn=self._get_memory_panel_content,
                outputs=[memory_panel]
            )

            search_btn.click(
                fn=self.search_memory,
                inputs=[search_query],
                outputs=[search_result]
            )

            reload_skills_btn.click(
                fn=self.reload_skills,
                outputs=[reload_result]
            ).then(
                fn=self._get_skills_panel_content,
                outputs=[skills_panel]
            )

            refresh_info_btn.click(
                fn=self.get_system_info,
                outputs=[system_info]
            )

            # Initialize session list
            app.load(
                fn=update_session_list,
                outputs=[session_dropdown]
            )

            # Auto-refresh memory panel periodically (using gr.Timer for Gradio 6.0+)
            timer = gr.Timer(value=10)
            timer.tick(
                fn=lambda: self._get_memory_panel_content(),
                outputs=[memory_panel]
            )

        return app


def main():
    """Run the SkillClaw UI"""
    ui = SkillClawUI()
    app = ui.build_ui()

    # Create initial session
    ui.memory.create_session(title="New Conversation")

    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        theme=gr.themes.Soft(),
        inbrowser=True,
        css="""
        .chat-container { height: 70vh; }
        .panel-container { height: 35vh; overflow-y: auto; }
        .status-bar { font-size: 0.9em; color: #666; }
        """
    )


if __name__ == "__main__":
    main()

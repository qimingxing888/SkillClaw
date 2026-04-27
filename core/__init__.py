"""
SkillClaw - AI Agent Framework
A Claude Code compatible agent system with skills, memory, and multi-agent support.
"""

__version__ = "1.0.0"
__author__ = "SkillClaw Team"

from .config import Config
from .skill_registry import SkillRegistry
from .memory_manager import MemoryManager
from .kimi_client import KimiClient
from .agent_core import AgentCore, ReActAgent

__all__ = [
    "Config",
    "SkillRegistry",
    "MemoryManager",
    "KimiClient",
    "AgentCore",
    "ReActAgent",
]

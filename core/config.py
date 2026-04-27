"""Configuration management for SkillClaw"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class LLMConfig:
    """LLM configuration"""
    provider: str = "kimi"
    model: str = "kimi-k2.5"
    api_base: str = "https://api.moonshot.cn/v1"
    api_key: str = ""
    temperature: float = 1.0
    max_tokens: int = 8192
    timeout: int = 60
    retry_attempts: int = 3

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class AgentConfig:
    """Agent configuration"""
    name: str = "SkillClaw"
    version: str = "1.0.0"
    max_iterations: int = 10
    enable_streaming: bool = True
    auto_save_memory: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class MemoryConfig:
    """Memory configuration"""
    session_ttl_hours: int = 24
    max_context_messages: int = 50
    auto_summarize_threshold: int = 20

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class UIConfig:
    """UI configuration"""
    theme: str = "default"
    language: str = "zh"
    show_tool_calls: bool = True
    show_memory_panel: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UIConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


class Config:
    """Global configuration manager"""

    def __init__(self, config_path: Optional[str] = None):
        self.project_root = Path(__file__).parent.parent
        self.config_path = Path(config_path) if config_path else self.project_root / "settings.local.json"

        self.llm = LLMConfig()
        self.agent = AgentConfig()
        self.memory = MemoryConfig()
        self.ui = UIConfig()

        self._load()
        self._override_from_env()

    def _load(self):
        """Load configuration from JSON file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if "llm" in data:
                    self.llm = LLMConfig.from_dict(data["llm"])
                if "agent" in data:
                    self.agent = AgentConfig.from_dict(data["agent"])
                if "memory" in data:
                    self.memory = MemoryConfig.from_dict(data["memory"])
                if "ui" in data:
                    self.ui = UIConfig.from_dict(data["ui"])
            except Exception as e:
                print(f"Warning: Failed to load config from {self.config_path}: {e}")

    def _override_from_env(self):
        """Override configuration with environment variables"""
        if os.getenv("KIMI_API_KEY"):
            self.llm.api_key = os.getenv("KIMI_API_KEY")
        if os.getenv("OPENAI_API_KEY"):
            self.llm.api_key = os.getenv("OPENAI_API_KEY")
        if os.getenv("LLM_MODEL"):
            self.llm.model = os.getenv("LLM_MODEL")
        if os.getenv("LLM_API_BASE"):
            self.llm.api_base = os.getenv("LLM_API_BASE")

    def get_paths(self) -> Dict[str, Path]:
        """Get standard project paths"""
        return {
            "skills": self.project_root / ".claude" / "skills",
            "agents": self.project_root / ".claude" / "agents",
            "memory": self.project_root / ".claude" / "memory",
            "agent_memory": self.project_root / ".claude" / "agent-memory",
            "rules": self.project_root / "rules",
        }

    def save(self):
        """Save current configuration to file"""
        data = {
            "llm": {
                "provider": self.llm.provider,
                "model": self.llm.model,
                "api_base": self.llm.api_base,
                "api_key": self.llm.api_key,
                "temperature": self.llm.temperature,
                "max_tokens": self.llm.max_tokens,
                "timeout": self.llm.timeout,
                "retry_attempts": self.llm.retry_attempts,
            },
            "agent": {
                "name": self.agent.name,
                "version": self.agent.version,
                "max_iterations": self.agent.max_iterations,
                "enable_streaming": self.agent.enable_streaming,
                "auto_save_memory": self.agent.auto_save_memory,
            },
            "memory": {
                "session_ttl_hours": self.memory.session_ttl_hours,
                "max_context_messages": self.memory.max_context_messages,
                "auto_summarize_threshold": self.memory.auto_summarize_threshold,
            },
            "ui": {
                "theme": self.ui.theme,
                "language": self.ui.language,
                "show_tool_calls": self.ui.show_tool_calls,
                "show_memory_panel": self.ui.show_memory_panel,
            }
        }

        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

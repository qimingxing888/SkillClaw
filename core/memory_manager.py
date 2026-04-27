"""
Memory Manager - Local markdown-based memory persistence
Supports session memory, global memory, and entity memory.
All data stored in .md files, no database required.
"""

import json
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import OrderedDict
import hashlib


@dataclass
class MemoryEntry:
    """A single memory entry"""
    id: str
    content: str
    timestamp: datetime
    category: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance: int = 1  # 1-5 scale
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "category": self.category,
            "metadata": self.metadata,
            "importance": self.importance,
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "MemoryEntry":
        return cls(
            id=data["id"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            category=data.get("category", "general"),
            metadata=data.get("metadata", {}),
            importance=data.get("importance", 1),
            tags=data.get("tags", [])
        )


@dataclass
class Session:
    """A conversation session"""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[Dict[str, Any]] = field(default_factory=list)
    summary: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "messages": self.messages,
            "summary": self.summary,
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Session":
        return cls(
            id=data["id"],
            title=data["title"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            messages=data.get("messages", []),
            summary=data.get("summary"),
            tags=data.get("tags", [])
        )


class MemoryManager:
    """
    Manages all types of memory using local markdown files.
    Directory structure:
    - .claude/memory/sessions/ - Session history
    - .claude/memory/global.md - Global memories
    - .claude/memory/entities/ - Entity memories (user, project, etc.)
    """

    def __init__(self, memory_directory: Optional[str] = None):
        if memory_directory:
            self.memory_dir = Path(memory_directory)
        else:
            project_root = Path(__file__).parent.parent
            self.memory_dir = project_root / ".claude" / "memory"

        # Subdirectories
        self.sessions_dir = self.memory_dir / "sessions"
        self.entities_dir = self.memory_dir / "entities"

        # Ensure directories exist
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.entities_dir.mkdir(parents=True, exist_ok=True)

        # Cache
        self._sessions_cache: Dict[str, Session] = {}
        self._global_memory: List[MemoryEntry] = []
        self._user_profile: Dict[str, Any] = {}

        # Load existing data
        self._load_global_memory()
        self._load_user_profile()

        self.current_session: Optional[Session] = None

    # ========== Session Management ==========

    def create_session(self, title: Optional[str] = None) -> Session:
        """Create a new conversation session"""
        session_id = self._generate_id()
        now = datetime.now()

        session = Session(
            id=session_id,
            title=title or f"Session {now.strftime('%Y-%m-%d %H:%M')}",
            created_at=now,
            updated_at=now
        )

        self._sessions_cache[session_id] = session
        self.current_session = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID"""
        if session_id in self._sessions_cache:
            return self._sessions_cache[session_id]

        # Try to load from disk
        session_file = self.sessions_dir / f"{session_id}.md"
        if session_file.exists():
            session = self._load_session_file(session_file)
            if session:
                self._sessions_cache[session_id] = session
                return session

        return None

    def list_sessions(self, limit: int = 50) -> List[Dict]:
        """List all sessions, sorted by updated_at desc"""
        sessions = []

        # Scan for new sessions
        for session_file in self.sessions_dir.glob("*.md"):
            session_id = session_file.stem
            if session_id not in self._sessions_cache:
                session = self._load_session_file(session_file)
                if session:
                    self._sessions_cache[session_id] = session

        # Sort and limit
        sorted_sessions = sorted(
            self._sessions_cache.values(),
            key=lambda s: s.updated_at,
            reverse=True
        )

        for session in sorted_sessions[:limit]:
            sessions.append({
                "id": session.id,
                "title": session.title,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "message_count": len(session.messages),
                "summary": session.summary
            })

        return sessions

    def add_message_to_session(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
        session_id: Optional[str] = None
    ):
        """Add a message to a session"""
        session = None
        if session_id:
            session = self.get_session(session_id)

        if not session:
            if not self.current_session:
                self.create_session()
            session = self.current_session

        if session:
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            session.messages.append(message)
            session.updated_at = datetime.now()
            self._save_session(session)

    def save_session_summary(self, session_id: str, summary: str):
        """Save a summary for a session"""
        session = self.get_session(session_id)
        if session:
            session.summary = summary
            self._save_session(session)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        session_file = self.sessions_dir / f"{session_id}.md"

        if session_file.exists():
            session_file.unlink()

        if session_id in self._sessions_cache:
            del self._sessions_cache[session_id]

        if self.current_session and self.current_session.id == session_id:
            self.current_session = None

        return True

    # ========== Global Memory ==========

    def add_global_memory(
        self,
        content: str,
        category: str = "general",
        importance: int = 1,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> MemoryEntry:
        """Add a global memory entry"""
        entry = MemoryEntry(
            id=self._generate_id(),
            content=content,
            timestamp=datetime.now(),
            category=category,
            importance=importance,
            tags=tags or [],
            metadata=metadata or {}
        )

        self._global_memory.append(entry)
        self._save_global_memory()
        return entry

    def get_global_memories(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_importance: int = 1,
        limit: int = 100
    ) -> List[MemoryEntry]:
        """Get global memories with optional filtering"""
        results = self._global_memory

        if category:
            results = [m for m in results if m.category == category]

        if tags:
            results = [m for m in results if any(t in m.tags for t in tags)]

        results = [m for m in results if m.importance >= min_importance]

        # Sort by importance desc, then timestamp desc
        results = sorted(
            results,
            key=lambda m: (m.importance, m.timestamp),
            reverse=True
        )

        return results[:limit]

    def search_memories(self, query: str, limit: int = 20) -> List[MemoryEntry]:
        """Search memories by content"""
        query = query.lower()
        results = []

        for memory in self._global_memory:
            if query in memory.content.lower():
                results.append(memory)

        # Sort by relevance (exact matches first) and importance
        results = sorted(
            results,
            key=lambda m: (
                query in m.content.lower(),
                m.importance
            ),
            reverse=True
        )

        return results[:limit]

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory entry"""
        for i, memory in enumerate(self._global_memory):
            if memory.id == memory_id:
                del self._global_memory[i]
                self._save_global_memory()
                return True
        return False

    # ========== User Profile ==========

    def update_user_profile(self, key: str, value: Any, category: str = "general"):
        """Update user profile information"""
        if category not in self._user_profile:
            self._user_profile[category] = {}

        self._user_profile[category][key] = {
            "value": value,
            "updated_at": datetime.now().isoformat()
        }

        self._save_user_profile()

    def get_user_profile(self, category: Optional[str] = None) -> Dict:
        """Get user profile data"""
        if category:
            return self._user_profile.get(category, {})
        return self._user_profile

    def add_user_preference(self, preference: str, value: Any):
        """Add a user preference (convenience method for preferences category)"""
        self.update_user_profile(preference, value, "preferences")

    def add_user_hobby(self, hobby: str, details: Optional[str] = None):
        """Add a user hobby"""
        if "hobbies" not in self._user_profile:
            self._user_profile["hobbies"] = {}

        self._user_profile["hobbies"][hobby] = {
            "details": details or "",
            "added_at": datetime.now().isoformat()
        }

        self._save_user_profile()

    def get_user_context_prompt(self) -> str:
        """Generate a prompt snippet with user context"""
        lines = []

        if self._user_profile:
            lines.append("## User Profile")

            # Preferences
            prefs = self._user_profile.get("preferences", {})
            if prefs:
                lines.append("\n### Preferences")
                for key, data in prefs.items():
                    lines.append(f"- {key}: {data['value']}")

            # Hobbies
            hobbies = self._user_profile.get("hobbies", {})
            if hobbies:
                lines.append("\n### Interests & Hobbies")
                for hobby, data in hobbies.items():
                    detail = data.get("details", "")
                    if detail:
                        lines.append(f"- {hobby}: {detail}")
                    else:
                        lines.append(f"- {hobby}")

        # Recent important memories
        important_memories = self.get_global_memories(min_importance=3, limit=5)
        if important_memories:
            lines.append("\n### Important Context")
            for mem in important_memories:
                lines.append(f"- {mem.content}")

        return "\n".join(lines) if lines else ""

    # ========== Entity Memory ==========

    def save_entity(self, entity_type: str, entity_id: str, data: Dict):
        """Save entity memory (project, person, etc.)"""
        entity_dir = self.entities_dir / entity_type
        entity_dir.mkdir(exist_ok=True)

        entity_file = entity_dir / f"{entity_id}.md"

        # Create markdown with YAML frontmatter
        content = f"""---
entity_type: {entity_type}
entity_id: {entity_id}
updated_at: {datetime.now().isoformat()}
---

# {entity_id}

{json.dumps(data, indent=2, ensure_ascii=False)}
"""
        with open(entity_file, 'w', encoding='utf-8') as f:
            f.write(content)

    def get_entity(self, entity_type: str, entity_id: str) -> Optional[Dict]:
        """Get entity memory"""
        entity_file = self.entities_dir / entity_type / f"{entity_id}.md"

        if entity_file.exists():
            try:
                with open(entity_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Extract JSON from content (after frontmatter)
                if '---' in content:
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        json_content = parts[2].strip()
                        # Remove markdown code block markers if present
                        json_content = re.sub(r'^```json\s*', '', json_content)
                        json_content = re.sub(r'```\s*$', '', json_content)
                        return json.loads(json_content)
            except Exception as e:
                print(f"Warning: Failed to load entity {entity_type}/{entity_id}: {e}")

        return None

    def list_entities(self, entity_type: str) -> List[str]:
        """List all entities of a type"""
        entity_dir = self.entities_dir / entity_type

        if not entity_dir.exists():
            return []

        return [f.stem for f in entity_dir.glob("*.md")]

    # ========== Private Methods ==========

    def _generate_id(self) -> str:
        """Generate a unique ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = hashlib.md5(
            str(datetime.now().timestamp()).encode()
        ).hexdigest()[:6]
        return f"{timestamp}_{random_suffix}"

    def _save_session(self, session: Session):
        """Save a session to disk"""
        session_file = self.sessions_dir / f"{session.id}.md"

        # Build markdown content
        lines = [
            "---",
            yaml.dump({
                "id": session.id,
                "title": session.title,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "summary": session.summary,
                "tags": session.tags
            }, allow_unicode=True),
            "---",
            "",
            f"# {session.title}",
            "",
            "## Messages",
            ""
        ]

        for msg in session.messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")

            lines.append(f"### {role.title()} ({timestamp})")
            lines.append("")
            lines.append(content)
            lines.append("")

        with open(session_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

    def _load_session_file(self, session_file: Path) -> Optional[Session]:
        """Load a session from markdown file"""
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse frontmatter
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    metadata = yaml.safe_load(parts[1]) or {}

                    session = Session(
                        id=metadata.get("id", session_file.stem),
                        title=metadata.get("title", "Untitled"),
                        created_at=datetime.fromisoformat(metadata["created_at"]),
                        updated_at=datetime.fromisoformat(metadata["updated_at"]),
                        summary=metadata.get("summary"),
                        tags=metadata.get("tags", [])
                    )

                    # Parse messages from markdown
                    body = parts[2]
                    messages = []

                    # Simple message parsing
                    message_pattern = r'### (\w+) \(([^)]+)\)\n\n(.*?)(?=\n### |\Z)'
                    for match in re.finditer(message_pattern, body, re.DOTALL):
                        role = match.group(1).lower()
                        timestamp = match.group(2)
                        msg_content = match.group(3).strip()

                        messages.append({
                            "role": role,
                            "timestamp": timestamp,
                            "content": msg_content,
                            "metadata": {}
                        })

                    session.messages = messages
                    return session

        except Exception as e:
            print(f"Warning: Failed to load session {session_file}: {e}")

        return None

    def _load_global_memory(self):
        """Load global memories from disk"""
        global_file = self.memory_dir / "global.md"

        if global_file.exists():
            try:
                with open(global_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Parse entries from markdown
                # Each entry is a ### heading with YAML frontmatter-like content
                entries = []

                for block in re.split(r'\n(?=### )', content):
                    if block.strip().startswith("### "):
                        # Parse entry
                        lines = block.strip().split('\n')
                        title_line = lines[0].replace("### ", "")

                        # Try to extract metadata from the title or following lines
                        entry_data = {"content": "\n".join(lines[1:]).strip()}

                        # Look for metadata pattern: key: value
                        metadata_pattern = r'^([\w_]+):\s*(.+)$'
                        for line in lines[1:10]:  # Check first few lines
                            match = re.match(metadata_pattern, line)
                            if match:
                                key, value = match.groups()
                                if key in ["id", "category", "importance", "timestamp", "tags"]:
                                    entry_data[key] = value

                        entry = MemoryEntry(
                            id=entry_data.get("id", self._generate_id()),
                            content=entry_data.get("content", ""),
                            timestamp=datetime.fromisoformat(entry_data["timestamp"])
                            if "timestamp" in entry_data else datetime.now(),
                            category=entry_data.get("category", "general"),
                            importance=int(entry_data.get("importance", 1)),
                            tags=entry_data.get("tags", ".").split(",") if "tags" in entry_data else []
                        )
                        entries.append(entry)

                self._global_memory = entries

            except Exception as e:
                print(f"Warning: Failed to load global memory: {e}")

    def _save_global_memory(self):
        """Save global memories to disk"""
        global_file = self.memory_dir / "global.md"

        lines = [
            "---",
            "type: global_memory",
            f"updated_at: {datetime.now().isoformat()}",
            f"entry_count: {len(self._global_memory)}",
            "---",
            "",
            "# Global Memory",
            ""
        ]

        for entry in sorted(self._global_memory, key=lambda e: e.timestamp, reverse=True):
            lines.append(f"### {entry.content[:50]}...")
            lines.append(f"id: {entry.id}")
            lines.append(f"category: {entry.category}")
            lines.append(f"importance: {entry.importance}")
            lines.append(f"timestamp: {entry.timestamp.isoformat()}")
            lines.append(f"tags: {','.join(entry.tags)}")
            lines.append("")
            lines.append(entry.content)
            lines.append("")
            lines.append("---")
            lines.append("")

        with open(global_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

    def _load_user_profile(self):
        """Load user profile from USER.md"""
        project_root = Path(__file__).parent.parent
        user_file = project_root / "USER.md"

        if user_file.exists():
            try:
                with open(user_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Parse YAML frontmatter if present
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        profile_data = yaml.safe_load(parts[1]) or {}
                        self._user_profile = profile_data

            except Exception as e:
                print(f"Warning: Failed to load user profile: {e}")

    def _save_user_profile(self):
        """Save user profile to USER.md"""
        project_root = Path(__file__).parent.parent
        user_file = project_root / "USER.md"

        # Build content
        lines = [
            "---",
            yaml.dump(self._user_profile, allow_unicode=True),
            "---",
            "",
            "# User Profile",
            "",
            "This file contains user preferences, hobbies, and personal information.",
            "The agent automatically updates this file based on conversations.",
            "",
            "## Preferences",
            ""
        ]

        prefs = self._user_profile.get("preferences", {})
        for key, data in prefs.items():
            lines.append(f"- **{key}**: {data['value']}")

        lines.extend([
            "",
            "## Hobbies & Interests",
            ""
        ])

        hobbies = self._user_profile.get("hobbies", {})
        for hobby, data in hobbies.items():
            lines.append(f"- **{hobby}**")
            if data.get("details"):
                lines.append(f"  - {data['details']}")

        with open(user_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

    def get_stats(self) -> Dict:
        """Get memory statistics"""
        return {
            "sessions": len(list(self.sessions_dir.glob("*.md"))),
            "global_memories": len(self._global_memory),
            "cached_sessions": len(self._sessions_cache),
            "has_user_profile": bool(self._user_profile),
            "current_session": self.current_session.id if self.current_session else None
        }

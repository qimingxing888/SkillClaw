"""Skill Registry - Discover and load skills from markdown files"""

import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class Skill:
    """Represents a skill with its metadata and content"""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)
    path: Optional[Path] = None
    content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    loaded_at: Optional[datetime] = None
    tools: List[Dict] = field(default_factory=list)

    def load_full_content(self) -> str:
        """Load the complete skill content"""
        if self.content is None and self.path:
            with open(self.path, 'r', encoding='utf-8') as f:
                self.content = f.read()
            self.loaded_at = datetime.now()
        return self.content or ""

    def to_tool_definition(self) -> Dict[str, Any]:
        """Convert skill to OpenAI function calling format"""
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', self.name)

        # Extract parameters from metadata if available
        parameters = self.metadata.get("parameters", {
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "description": "The context or task details for the skill"
                }
            },
            "required": ["context"]
        })

        return {
            "type": "function",
            "function": {
                "name": f"skill_{safe_name}",
                "description": f"[{self.name}] {self.description}",
                "parameters": parameters
            }
        }


class SkillRegistry:
    """
    Manages skill discovery, loading, and activation.
    Scans .claude/skills/*.md files and parses YAML frontmatter.
    """

    def __init__(self, skills_directory: Optional[str] = None):
        if skills_directory:
            self.skills_dir = Path(skills_directory)
        else:
            project_root = Path(__file__).parent.parent
            self.skills_dir = project_root / ".claude" / "skills"

        self.skills: Dict[str, Skill] = {}
        self._last_scan: Optional[datetime] = None

        # Ensure directory exists
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        # Initial scan
        self.scan_skills()

    def scan_skills(self) -> List[Skill]:
        """
        Scan skills directory and discover all .md files.
        Returns list of newly discovered skills.
        """
        new_skills = []

        if not self.skills_dir.exists():
            return new_skills

        for skill_file in self.skills_dir.glob("*.md"):
            skill_name = skill_file.stem

            # Skip if already loaded and file hasn't changed
            if skill_name in self.skills:
                current_mtime = skill_file.stat().st_mtime
                if self.skills[skill_name].loaded_at:
                    continue  # Already loaded

            try:
                skill = self._parse_skill_file(skill_file)
                self.skills[skill.name] = skill
                new_skills.append(skill)
            except Exception as e:
                print(f"Warning: Failed to load skill from {skill_file}: {e}")

        self._last_scan = datetime.now()
        return new_skills

    def _parse_skill_file(self, skill_file: Path) -> Skill:
        """Parse a skill markdown file and extract metadata"""
        with open(skill_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract YAML frontmatter
        metadata = {}
        skill_content = content

        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                try:
                    metadata = yaml.safe_load(parts[1]) or {}
                    skill_content = parts[2].strip()
                except yaml.YAMLError as e:
                    print(f"Warning: Failed to parse YAML frontmatter in {skill_file}: {e}")

        # Build skill object
        name = metadata.get('name', skill_file.stem)

        return Skill(
            name=name,
            description=metadata.get('description', 'No description available'),
            version=metadata.get('version', '1.0.0'),
            author=metadata.get('author', ''),
            tags=metadata.get('tags', []),
            path=skill_file,
            content=skill_content,
            metadata=metadata,
            loaded_at=datetime.now(),
            tools=metadata.get('tools', [])
        )

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name"""
        # Try exact match first
        if name in self.skills:
            return self.skills[name]

        # Try case-insensitive match
        for skill_name, skill in self.skills.items():
            if skill_name.lower() == name.lower():
                return skill

        # Try matching by safe name
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        for skill_name, skill in self.skills.items():
            if re.sub(r'[^a-zA-Z0-9_]', '_', skill_name) == safe_name:
                return skill

        return None

    def get_all_skills(self) -> List[Skill]:
        """Get all loaded skills"""
        return list(self.skills.values())

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Convert all skills to OpenAI tool format"""
        return [skill.to_tool_definition() for skill in self.skills.values()]

    def activate_skill(self, name: str) -> Optional[str]:
        """
        Activate a skill by loading its full content.
        Returns the skill content or None if not found.
        """
        skill = self.get_skill(name)
        if skill:
            content = skill.load_full_content()
            # Prepend metadata as context
            header = f"""# Skill: {skill.name}
Description: {skill.description}
Version: {skill.version}
"""
            if skill.tags:
                header += f"Tags: {', '.join(skill.tags)}\n"
            header += "\n---\n\n"

            return header + content
        return None

    def search_skills(self, query: str) -> List[Skill]:
        """Search skills by name, description, or tags"""
        query = query.lower()
        results = []

        for skill in self.skills.values():
            if (query in skill.name.lower() or
                query in skill.description.lower() or
                any(query in tag.lower() for tag in skill.tags)):
                results.append(skill)

        return results

    def get_skills_by_tag(self, tag: str) -> List[Skill]:
        """Get all skills with a specific tag"""
        tag = tag.lower()
        return [skill for skill in self.skills.values()
                if any(tag == t.lower() for t in skill.tags)]

    def reload_skill(self, name: str) -> bool:
        """Reload a skill from disk"""
        skill = self.get_skill(name)
        if skill and skill.path:
            try:
                new_skill = self._parse_skill_file(skill.path)
                self.skills[name] = new_skill
                return True
            except Exception as e:
                print(f"Warning: Failed to reload skill {name}: {e}")
        return False

    def reload_all(self) -> int:
        """Reload all skills from disk, return count of reloaded skills"""
        self.skills.clear()
        self.scan_skills()
        return len(self.skills)

    def create_skill_template(self, name: str, description: str = "") -> Path:
        """Create a new skill template file"""
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '-', name.lower())
        skill_file = self.skills_dir / f"{safe_name}.md"

        template = f"""---
name: {name}
description: {description or f'A skill for {name}'}
version: 1.0.0
author: ""
tags: []
---

# {name}

You are an expert at {name}.

## Capabilities

1. Describe the main capabilities of this skill
2. Add specific tasks it can perform
3. List any limitations or requirements

## Usage Guidelines

### Example 1

```
User: "Example input"
Response: "Example output"
```

### Example 2

```
User: "Another example"
Response: "Another response"
```

## Tools

If this skill requires specific tools, describe them here:

- Tool 1: Description
- Tool 2: Description

## Best Practices

1. Best practice 1
2. Best practice 2
3. Best practice 3

## Notes

Any additional notes or warnings about using this skill.
"""

        with open(skill_file, 'w', encoding='utf-8') as f:
            f.write(template)

        return skill_file

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded skills"""
        return {
            "total_skills": len(self.skills),
            "last_scan": self._last_scan.isoformat() if self._last_scan else None,
            "skills_dir": str(self.skills_dir),
            "skills": [
                {
                    "name": s.name,
                    "version": s.version,
                    "tags": s.tags
                }
                for s in self.skills.values()
            ]
        }

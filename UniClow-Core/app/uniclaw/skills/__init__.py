"""

Skill system module

Includes:
- registry:SkillRegistry Skill registry
- frontmatter:YAML frontmatter parser
- generator:Open-APISkill-Generator(from Open-API JSON Skills)
"""

from app.uniclaw.skills.registry import (
    MdSkillEntry,
    SkillMetadata,
    SkillRegistry,
    validate_skill_name,
)
from app.uniclaw.skills.frontmatter import (
    FrontmatterResult,
    parse_frontmatter,
)

__all__ = [
    "FrontmatterResult",
    "MdSkillEntry",
    "SkillMetadata",
    "SkillRegistry",
    "parse_frontmatter",
    "validate_skill_name",
]

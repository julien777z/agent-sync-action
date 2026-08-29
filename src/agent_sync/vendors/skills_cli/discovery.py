import logging
from pathlib import Path

from agent_sync.document import parse_markdown
from agent_sync.models.document import SkillFrontMatter
from agent_sync.models.vendors.skills_cli import VendoredSkill

logger = logging.getLogger(__name__)


def locate_skill_directory(search_root: Path, name: str) -> Path:
    """Locate one skill directory under a search root."""

    documents = sorted(search_root.rglob("SKILL.md"))
    directory_matches = [document.parent for document in documents if document.parent.name == name]

    if len(directory_matches) == 1:
        return directory_matches[0]

    metadata_matches = [
        document.parent
        for document in documents
        if parse_markdown(
            document.read_text(encoding="utf-8"),
            SkillFrontMatter,
            str(document),
        )[0].name
        == name
    ]

    if len(metadata_matches) == 1:
        return metadata_matches[0]

    if not directory_matches and not metadata_matches and len(documents) == 1:
        return documents[0].parent

    raise RuntimeError(
        f"Could not locate one skill '{name}' under {search_root} "
        f"(found: {[str(path.parent.relative_to(search_root)) for path in documents]})"
    )


def is_search_root_skill(search_root: Path, skill: VendoredSkill) -> bool:
    """Report whether the searched directory is itself the selected upstream skill."""

    document = search_root / "SKILL.md"

    if not document.is_file():
        return False

    front_matter, _ = parse_markdown(
        document.read_text(encoding="utf-8"),
        SkillFrontMatter,
        str(document),
    )

    return front_matter.name == skill.upstream_skill

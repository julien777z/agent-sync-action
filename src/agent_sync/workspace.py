import logging
import os
import shutil
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent_sync.config import ACTION_CONFIG
from agent_sync.utils import escapes_base_directory

logger = logging.getLogger(__name__)


class Workspace(BaseModel):
    """Describe one repository and its canonical agent source directory."""

    model_config = ConfigDict(frozen=True)

    root: Path = Field(default_factory=Path.cwd)
    agents_dirname: str = ".agents"
    output_dirname: str = ""

    @field_validator("output_dirname")
    @classmethod
    def validate_output_dirname(cls, value: str) -> str:
        """Require generated provider trees to stay inside the repository."""

        if escapes_base_directory(Path(value)):
            raise ValueError("Generated output directory must be a relative path inside the repository")

        return value

    @property
    def agents_dir(self) -> Path:
        """Return the canonical agent source directory."""

        return self.root / self.agents_dirname

    @property
    def output_root(self) -> Path:
        """Return the directory that holds every generated provider tree."""

        return self.root / self.output_dirname if self.output_dirname else self.root

    @property
    def settings_dir(self) -> Path:
        """Return the canonical provider settings directory."""

        return self.agents_dir / "settings"

    @property
    def models_dir(self) -> Path:
        """Return the canonical agent model override directory."""

        return self.agents_dir / "models"

    @classmethod
    def resolve(
        cls,
        root: str | None,
        agents_dirname: str | None,
        output_dirname: str | None,
    ) -> Self:
        """Resolve CLI options, environment values, and defaults into a workspace."""

        resolved_root = root or ACTION_CONFIG.root or Path.cwd()
        resolved_agents_dirname = agents_dirname or ACTION_CONFIG.agents_dir
        resolved_output_dirname = output_dirname or ACTION_CONFIG.output_dir

        return cls(
            root=Path(resolved_root).resolve(),
            agents_dirname=resolved_agents_dirname,
            output_dirname=resolved_output_dirname,
        )

    def read_text(self, path: Path) -> str | None:
        """Read UTF-8 text when a path exists."""

        if not path.exists():
            return None

        return path.read_text(encoding="utf-8")

    def read_link(self, path: Path) -> str | None:
        """Read a symlink target without following it."""

        if not path.is_symlink():
            return None

        return os.readlink(path)

    def replace_text(self, path: Path, content: str, executable: bool) -> None:
        """Replace a path with a generated UTF-8 file."""

        self.prepare_parent(path)

        if path.is_symlink() or path.is_dir():
            self.delete(path)

        path.write_text(content, encoding="utf-8")
        path.chmod(0o755 if executable else 0o644)

    def replace_link(self, path: Path, target: Path) -> None:
        """Replace a path with a relative symlink."""

        self.prepare_parent(path)

        if path.is_symlink() or path.exists():
            self.delete(path)

        path.symlink_to(os.path.relpath(target, path.parent))

    def find_parent_blockers(self, path: Path) -> list[Path]:
        """Return non-directory ancestors that would make an output unsafe to write."""

        relative_parent = path.parent.relative_to(self.root)
        current = self.root
        blockers: list[Path] = []

        for part in relative_parent.parts:
            current /= part

            if current.is_symlink() or (current.exists() and not current.is_dir()):
                blockers.append(current)

                break

        return blockers

    def prepare_parent(self, path: Path) -> None:
        """Replace unsafe output ancestors, then create the output parent directory."""

        for blocker in self.find_parent_blockers(path):
            self.delete(blocker)

        path.parent.mkdir(parents=True, exist_ok=True)

    def delete(self, path: Path) -> None:
        """Delete a file, directory, or symlink without following links."""

        if path.is_symlink():
            path.unlink()

            return

        if not path.exists():
            return

        if path.is_dir():
            shutil.rmtree(path)

            return

        path.unlink()

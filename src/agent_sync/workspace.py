import os
import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from agent_sync.utils import relative_link_target


class Workspace(BaseModel):
    """Describe one repository and its canonical agent source directory."""

    model_config = ConfigDict(frozen=True)

    root: Path = Field(default_factory=Path.cwd)
    agents_dirname: str = ".agents"

    @property
    def agents_dir(self) -> Path:
        """Return the canonical agent source directory."""

        return self.root / self.agents_dirname

    @property
    def settings_dir(self) -> Path:
        """Return the canonical provider settings directory."""

        return self.agents_dir / "settings"

    @property
    def models_dir(self) -> Path:
        """Return the canonical agent model override directory."""

        return self.agents_dir / "models"

    @classmethod
    def resolve(cls, root: str | None, agents_dirname: str | None) -> "Workspace":
        """Resolve CLI options, environment values, and defaults into a workspace."""

        resolved_root = root or os.environ.get("AGENT_SYNC_ROOT") or os.getcwd()
        resolved_agents_dirname = (
            agents_dirname or os.environ.get("AGENT_SYNC_AGENTS_DIR") or ".agents"
        )

        return cls(
            root=Path(resolved_root).resolve(),
            agents_dirname=resolved_agents_dirname,
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

        if path.is_symlink() or path.is_dir():
            self.delete(path)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755 if executable else 0o644)

    def replace_link(self, path: Path, target: Path) -> None:
        """Replace a path with a relative symlink."""

        if path.is_symlink() or path.exists():
            self.delete(path)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(relative_link_target(path, target))

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

import argparse
import hashlib
import json
import logging
import re
import shutil
import stat
import uuid
import webbrowser
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Final
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

SKILL_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DASHBOARD_TEMPLATE: Final[Path] = SKILL_ROOT / "assets" / "dashboard.html"
DEFAULT_RUNS_ROOT: Final[Path] = Path.home() / ".agents" / "skill-gauntlet" / "runs"
PUBLIC_STATE_FILENAME: Final[str] = "state.json"
SENSITIVE_PUBLIC_KEYS: Final[frozenset[str]] = frozenset(
    {"sealed_tasks", "held_out_tasks", "evaluation_packets", "expected_answers"}
)


def utc_now() -> str:
    """Return a stable UTC timestamp."""

    return datetime.now(UTC).isoformat()


def safe_slug(value: str) -> str:
    """Convert a label into a filesystem-safe slug."""

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

    return slug or "skill"


def tree_manifest(root: Path, ignored_paths: frozenset[str] = frozenset()) -> list[dict[str, str]]:
    """Describe a directory tree deterministically."""

    entries: list[dict[str, str]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative_path = path.relative_to(root).as_posix()
        if relative_path in ignored_paths:
            continue
        if path.is_symlink():
            entries.append(
                {"path": relative_path, "type": "symlink", "target": path.readlink().as_posix()}
            )
        elif path.is_file():
            entries.append(
                {
                    "path": relative_path,
                    "type": "file",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        elif path.is_dir():
            entries.append({"path": relative_path, "type": "directory"})

    return entries


def manifest_digest(entries: list[dict[str, str]]) -> str:
    """Hash a deterministic tree manifest."""

    payload = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()

    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> dict[str, object]:
    """Read a JSON object from disk."""

    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")

    return value


def atomic_write_json(path: Path, value: dict[str, object]) -> None:
    """Write JSON atomically."""

    temporary_path = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
    temporary_path.write_text(f"{json.dumps(value, indent=2, sort_keys=True)}\n")
    temporary_path.replace(path)


def load_state(run_dir: Path) -> dict[str, object]:
    """Load one gauntlet run's public state."""

    state_path = run_dir / PUBLIC_STATE_FILENAME
    if not state_path.is_file():
        raise FileNotFoundError(f"Missing gauntlet state: {state_path}")

    return read_json(state_path)


def save_state(run_dir: Path, state: dict[str, object]) -> None:
    """Save one gauntlet run's public state."""

    state["updated_at"] = utc_now()
    atomic_write_json(run_dir / PUBLIC_STATE_FILENAME, state)


def make_read_only(root: Path) -> None:
    """Remove write permissions from a snapshot tree."""

    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_symlink():
            continue
        mode = path.stat().st_mode
        path.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))

    root.chmod(root.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def find_sensitive_key(value: object, location: str = "state") -> str | None:
    """Find sealed evaluation data accidentally placed in public state."""

    if isinstance(value, dict):
        for key, child in value.items():
            key_name = str(key)
            if key_name in SENSITIVE_PUBLIC_KEYS:
                return f"{location}.{key_name}"
            found = find_sensitive_key(child, f"{location}.{key_name}")
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = find_sensitive_key(child, f"{location}[{index}]")
            if found:
                return found

    return None


def merge_objects(current: dict[str, object], patch: dict[str, object]) -> dict[str, object]:
    """Recursively merge a JSON object patch."""

    merged = dict(current)
    for key, value in patch.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = merge_objects(existing, value)
        else:
            merged[key] = value

    return merged


def initialize_run(arguments: argparse.Namespace) -> None:
    """Create a persistent gauntlet run directory."""

    run_id = arguments.run_id or f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    runs_root = Path(arguments.runs_root).expanduser().resolve()
    run_dir = runs_root / run_id
    run_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    for directory_name in ("candidates", "evidence", "retired", "sealed", "snapshots"):
        (run_dir / directory_name).mkdir(mode=0o700)

    shutil.copy2(DASHBOARD_TEMPLATE, run_dir / "dashboard.html")

    timestamp = utc_now()
    state: dict[str, object] = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "phase": "inventory",
        "status": "running",
        "inventory": [],
        "selection": [],
        "models": {},
        "skills": {},
        "activity": [],
    }
    atomic_write_json(run_dir / PUBLIC_STATE_FILENAME, state)

    logger.info("%s", run_dir)


def snapshot_skill(arguments: argparse.Namespace) -> None:
    """Snapshot one complete installed skill."""

    run_dir = Path(arguments.run_dir).expanduser().resolve()
    installation_path = Path(arguments.path).expanduser().absolute()
    resolved_path = installation_path.resolve()
    if not resolved_path.is_dir() or not (resolved_path / "SKILL.md").is_file():
        raise ValueError(f"Not a complete skill directory: {installation_path}")

    state = load_state(run_dir)
    inventory = state.get("inventory")
    if not isinstance(inventory, list):
        raise ValueError("Public state inventory must be a list")
    if any(
        isinstance(item, dict) and item.get("installation_path") == str(installation_path)
        for item in inventory
    ):
        raise ValueError(f"Skill installation already snapshotted: {installation_path}")

    entries = tree_manifest(resolved_path)
    content_hash = manifest_digest(entries)
    duplicate_record = next(
        (
            item
            for item in inventory
            if isinstance(item, dict) and item.get("content_hash") == content_hash
        ),
        None,
    )
    if duplicate_record:
        snapshot_id = str(duplicate_record["snapshot_id"])
        snapshot_relative_path = str(duplicate_record["snapshot_path"])
    else:
        source_key = hashlib.sha256(str(resolved_path).encode()).hexdigest()[:10]
        snapshot_id = "--".join(
            (safe_slug(arguments.scope), safe_slug(arguments.name), content_hash[:12], source_key)
        )
        snapshot_relative_path = f"snapshots/{snapshot_id}"
        snapshot_path = run_dir / snapshot_relative_path
        shutil.copytree(resolved_path, snapshot_path, symlinks=True)

        manifest: dict[str, object] = {
            "snapshot_id": snapshot_id,
            "name": arguments.name,
            "scope": arguments.scope,
            "origin": arguments.origin,
            "installation_path": str(installation_path),
            "resolved_path": str(resolved_path),
            "content_hash": content_hash,
            "captured_at": utc_now(),
            "entries": entries,
        }
        atomic_write_json(snapshot_path / "manifest.json", manifest)
        make_read_only(snapshot_path)

    inventory.append(
        {
            "name": arguments.name,
            "scope": arguments.scope,
            "origin": arguments.origin,
            "installation_path": str(installation_path),
            "resolved_path": str(resolved_path),
            "activation": arguments.activation,
            "editability": arguments.editability,
            "precedence": arguments.precedence,
            "content_hash": content_hash,
            "snapshot_id": snapshot_id,
            "snapshot_path": snapshot_relative_path,
            "duplicate_of": snapshot_id if duplicate_record else None,
            "purpose": "",
            "dependencies": [],
            "overlaps": [],
        }
    )
    save_state(run_dir, state)

    logger.info("%s", snapshot_id)


def update_state(arguments: argparse.Namespace) -> None:
    """Apply an atomic patch to public run state."""

    run_dir = Path(arguments.run_dir).expanduser().resolve()
    patch = read_json(Path(arguments.patch).expanduser().resolve())
    sensitive_location = find_sensitive_key(patch)
    if sensitive_location:
        raise ValueError(f"Sealed evaluation data cannot enter public state: {sensitive_location}")

    state = merge_objects(load_state(run_dir), patch)
    save_state(run_dir, state)

    logger.info("%s", run_dir / PUBLIC_STATE_FILENAME)


def verify_run(arguments: argparse.Namespace) -> None:
    """Verify public state and every immutable snapshot."""

    run_dir = Path(arguments.run_dir).expanduser().resolve()
    state = load_state(run_dir)
    sensitive_location = find_sensitive_key(state)
    if sensitive_location:
        raise ValueError(f"Sealed evaluation data found in public state: {sensitive_location}")
    if not (run_dir / "dashboard.html").is_file():
        raise FileNotFoundError("Missing dashboard.html")
    for directory_name in ("retired", "sealed", "snapshots"):
        if not (run_dir / directory_name).is_dir():
            raise FileNotFoundError(f"Missing {directory_name} directory")

    inventory = state.get("inventory")
    if not isinstance(inventory, list):
        raise ValueError("Public state inventory must be a list")
    verified_snapshots: set[Path] = set()
    for item in inventory:
        if not isinstance(item, dict):
            raise ValueError("Inventory entries must be objects")
        snapshot_path = run_dir / str(item["snapshot_path"])
        if snapshot_path in verified_snapshots:
            continue
        entries = tree_manifest(snapshot_path, frozenset({"manifest.json"}))
        content_hash = manifest_digest(entries)
        if content_hash != item.get("content_hash"):
            raise ValueError(f"Snapshot digest mismatch: {snapshot_path}")
        for path in (snapshot_path, *snapshot_path.rglob("*")):
            if not path.is_symlink() and path.stat().st_mode & (
                stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
            ):
                raise ValueError(f"Writable snapshot path: {path}")
        verified_snapshots.add(snapshot_path)

    logger.info("Verified %d snapshots in %s", len(verified_snapshots), run_dir)


class DashboardHandler(BaseHTTPRequestHandler):
    """Serve only the public dashboard and state files."""

    run_dir: Path

    def do_GET(self) -> None:
        """Serve one public dashboard request."""

        request_path = urlparse(self.path).path
        if request_path in ("/", "/dashboard.html"):
            target_path = self.run_dir / "dashboard.html"
            content_type = "text/html; charset=utf-8"
        elif request_path == f"/{PUBLIC_STATE_FILENAME}":
            target_path = self.run_dir / PUBLIC_STATE_FILENAME
            content_type = "application/json; charset=utf-8"
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

            return

        content = target_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format_string: str, *arguments: object) -> None:
        """Route HTTP request logging through the module logger."""

        logger.debug(format_string, *arguments)


def serve_dashboard(arguments: argparse.Namespace) -> None:
    """Serve a run's view-only dashboard over loopback."""

    run_dir = Path(arguments.run_dir).expanduser().resolve()
    load_state(run_dir)

    handler_type = type("BoundDashboardHandler", (DashboardHandler,), {"run_dir": run_dir})
    server = ThreadingHTTPServer(("127.0.0.1", arguments.port), handler_type)
    host, port = server.server_address[:2]
    url = f"http://{host}:{port}/"
    logger.info("%s", url)
    if arguments.open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Dashboard server stopped")
    finally:
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description="Manage resumable Skill Gauntlet state")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create a gauntlet run")
    init_parser.add_argument("--run-id")
    init_parser.add_argument("--runs-root", default=str(DEFAULT_RUNS_ROOT))
    init_parser.set_defaults(handler=initialize_run)

    snapshot_parser = subparsers.add_parser("snapshot", help="snapshot an installed skill")
    snapshot_parser.add_argument("run_dir")
    snapshot_parser.add_argument("--name", required=True)
    snapshot_parser.add_argument("--scope", required=True)
    snapshot_parser.add_argument("--origin", required=True)
    snapshot_parser.add_argument("--path", required=True)
    snapshot_parser.add_argument("--precedence", type=int)
    snapshot_parser.add_argument(
        "--activation", choices=("active", "inactive", "unknown"), default="unknown"
    )
    snapshot_parser.add_argument(
        "--editability", choices=("editable", "read-only", "unknown"), default="unknown"
    )
    snapshot_parser.set_defaults(handler=snapshot_skill)

    update_parser = subparsers.add_parser("update", help="patch public run state")
    update_parser.add_argument("run_dir")
    update_parser.add_argument("--patch", required=True)
    update_parser.set_defaults(handler=update_state)

    verify_parser = subparsers.add_parser("verify", help="verify run integrity")
    verify_parser.add_argument("run_dir")
    verify_parser.set_defaults(handler=verify_run)

    serve_parser = subparsers.add_parser("serve", help="serve the view-only dashboard")
    serve_parser.add_argument("run_dir")
    serve_parser.add_argument("--port", type=int, default=0)
    serve_parser.add_argument("--open", action="store_true")
    serve_parser.set_defaults(handler=serve_dashboard)

    return parser


def main() -> None:
    """Run the Skill Gauntlet utility."""

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    arguments = build_parser().parse_args()
    arguments.handler(arguments)


if __name__ == "__main__":
    main()

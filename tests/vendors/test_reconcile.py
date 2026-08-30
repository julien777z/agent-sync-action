from collections.abc import Callable

import pytest

from agent_sync.models.vendors.lock import VendorLock, VendorLockEntry
from agent_sync.vendors import reconcile
from agent_sync.workspace import Workspace
from tests.factories import materialize_tree


def install_lock(workspace: Workspace, **vendors: list[str]) -> None:
    """Write a record of what each named vendor previously installed."""

    reconcile.save_lock(
        workspace,
        VendorLock(vendors={name: VendorLockEntry(paths=paths) for name, paths in vendors.items()}),
    )


class TestVendorReconciliation:
    """Test that recorded vendor paths are removed only when a vendor stops claiming them."""

    def test_unclaimed_paths_are_removed(self, workspace: Workspace) -> None:
        """Test that a path a later run stops claiming is deleted."""

        materialize_tree(
            workspace.agents_dir,
            {"skills/kept/SKILL.md": "kept\n", "skills/dropped/SKILL.md": "dropped\n"},
        )
        install_lock(workspace, ecc=[".agents/skills/kept", ".agents/skills/dropped"])

        reconcile.reconcile_installed_paths(
            workspace,
            {"ecc": [".agents/skills/kept"]},
            {"ecc"},
            dry_run=False,
        )

        assert (workspace.agents_dir / "skills/kept").exists()
        assert not (workspace.agents_dir / "skills/dropped").exists()

    def test_unrecorded_paths_are_never_removed(self, workspace: Workspace) -> None:
        """Test that content no vendor recorded survives beside vendor-installed content."""

        materialize_tree(
            workspace.agents_dir,
            {"skills/authored/SKILL.md": "authored\n", "skills/vendored/SKILL.md": "vendored\n"},
        )
        install_lock(workspace, ecc=[".agents/skills/vendored"])

        reconcile.reconcile_installed_paths(workspace, {"ecc": []}, {"ecc"}, dry_run=False)

        assert (workspace.agents_dir / "skills/authored/SKILL.md").read_text() == "authored\n"
        assert not (workspace.agents_dir / "skills/vendored").exists()

    def test_emptied_directories_are_removed(self, workspace: Workspace) -> None:
        """Test that a directory left empty by a removal does not linger."""

        materialize_tree(
            workspace.agents_dir,
            {
                "skills/dropped/references/guide.md": "guide\n",
                "skills/dropped/SKILL.md": "dropped\n",
            },
        )
        install_lock(
            workspace,
            ecc=[".agents/skills/dropped/references/guide.md", ".agents/skills/dropped/SKILL.md"],
        )

        reconcile.reconcile_installed_paths(workspace, {"ecc": []}, {"ecc"}, dry_run=False)

        assert not (workspace.agents_dir / "skills/dropped").exists()
        assert workspace.agents_dir.is_dir()

    def test_a_vendor_that_did_not_run_is_untouched(self, workspace: Workspace) -> None:
        """Test that pausing a vendor's sync leaves what it installed in place."""

        materialize_tree(workspace.agents_dir, {"skills/paused/SKILL.md": "paused\n"})
        install_lock(workspace, ecc=[".agents/skills/paused"])

        reconcile.reconcile_installed_paths(workspace, {}, {"ecc"}, dry_run=False)

        assert (workspace.agents_dir / "skills/paused").exists()
        assert reconcile.load_lock(workspace).vendors["ecc"].paths == [".agents/skills/paused"]

    def test_an_undeclared_vendor_is_withdrawn(self, workspace: Workspace) -> None:
        """Test that dropping a vendor from the registry removes what it installed."""

        materialize_tree(workspace.agents_dir, {"skills/withdrawn/SKILL.md": "withdrawn\n"})
        install_lock(workspace, ecc=[".agents/skills/withdrawn"])

        reconcile.reconcile_installed_paths(workspace, {}, set(), dry_run=False)

        assert not (workspace.agents_dir / "skills/withdrawn").exists()
        assert "ecc" not in reconcile.load_lock(workspace).vendors

    def test_a_dry_run_removes_nothing(self, workspace: Workspace) -> None:
        """Test that a dry run reports orphans without deleting or recording them."""

        materialize_tree(workspace.agents_dir, {"skills/dropped/SKILL.md": "dropped\n"})
        install_lock(workspace, ecc=[".agents/skills/dropped"])

        assert reconcile.reconcile_installed_paths(workspace, {"ecc": []}, {"ecc"}, dry_run=True) is True
        assert (workspace.agents_dir / "skills/dropped").exists()
        assert reconcile.load_lock(workspace).vendors["ecc"].paths == [".agents/skills/dropped"]

    def test_a_missing_lock_is_a_clean_first_run(self, workspace: Workspace) -> None:
        """Test that a first run records what it installed and removes nothing."""

        assert reconcile.load_lock(workspace).vendors == {}

        reconcile.reconcile_installed_paths(
            workspace,
            {"ecc": [".agents/skills/new"]},
            {"ecc"},
            dry_run=False,
        )

        assert reconcile.load_lock(workspace).vendors["ecc"].paths == [".agents/skills/new"]

    @pytest.mark.parametrize(
        ("destinations", "expected"),
        [
            ([], []),
            (["/elsewhere/skills/outside"], []),
        ],
        ids=["nothing-written", "outside-the-workspace"],
    )
    def test_destinations_outside_the_workspace_are_ignored(
        self,
        create_workspace: Callable[..., Workspace],
        destinations: list[str],
        expected: list[str],
    ) -> None:
        """Test that only destinations inside the repository are recorded."""

        workspace = create_workspace()

        assert reconcile.relative_installed_paths(workspace, destinations) == expected

    def test_destinations_are_recorded_repository_relative(self, workspace: Workspace) -> None:
        """Test that absolute installer destinations become repository-relative records."""

        destination = str(workspace.agents_dir / "skills/sample/SKILL.md")

        assert reconcile.relative_installed_paths(workspace, [destination]) == [
            ".agents/skills/sample/SKILL.md"
        ]

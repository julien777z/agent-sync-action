import pytest
from pydantic import ValidationError

from agent_sync.models.vendors.registry import VendorRegistry, Vendors
from agent_sync.models.vendors.skills_cli import SkillsCliVendor, VendoredSkill
from tests.factories import (
    EccVendorFactory,
    SkillsCliVendorFactory,
    VendorRegistryFactory,
)


class TestVendoredSkillModel:
    """Test that vendored-skill validation and defaults work."""

    def test_upstream_slug_defaults_to_local_name(self) -> None:
        """Test that an omitted upstream slug uses the local skill name."""

        skill = VendoredSkill(
            name="sample-skill",
            repo="example/sample-skill",
            update_on_sync=True,
        )

        assert skill.upstream_skill == "sample-skill"
        assert skill.skills_path is None

    @pytest.mark.parametrize("name", ["Bad Name", "UPPER", "-leading", "sample\n"])
    def test_invalid_skill_names_fail(self, name: str) -> None:
        """Test that unsafe vendored skill names are rejected."""

        with pytest.raises(ValidationError):
            VendoredSkill(name=name, repo="example/sample", update_on_sync=True)

    @pytest.mark.parametrize("skill", ["Bad Name", "UPPER", "../escape"])
    def test_invalid_upstream_skill_names_fail(self, skill: str) -> None:
        """Test that unsafe upstream skill selectors are rejected."""

        with pytest.raises(ValidationError):
            VendoredSkill(
                name="sample",
                repo="example/sample",
                skill=skill,
                update_on_sync=True,
            )

    @pytest.mark.parametrize(
        "skills_path",
        ["/skills", "../skills", "skills/..", "skills/", ".hidden", "skills dir", ""],
    )
    def test_invalid_skills_paths_fail(self, skills_path: str) -> None:
        """Test that unsafe upstream skill directories are rejected."""

        with pytest.raises(ValidationError):
            VendoredSkill(
                name="sample",
                repo="example/sample",
                skills_path=skills_path,
                update_on_sync=True,
            )

    @pytest.mark.parametrize("skills_path", ["skills", "packages/skills", "skills.v2"])
    def test_valid_skills_paths_are_accepted(self, skills_path: str) -> None:
        """Test that ordinary upstream directory names are accepted."""

        skill = VendoredSkill(
            name="sample",
            repo="example/sample",
            skills_path=skills_path,
            update_on_sync=True,
        )

        assert skill.skills_path == skills_path

    def test_update_on_sync_is_required(self) -> None:
        """Test that every skill entry chooses its update behavior explicitly."""

        with pytest.raises(ValidationError, match="update_on_sync"):
            VendoredSkill.model_validate({"name": "sample", "repo": "example/sample"})

    def test_duplicate_local_skill_names_fail(self) -> None:
        """Test that entries cannot silently overwrite one local skill directory."""

        with pytest.raises(ValidationError, match="names must be unique"):
            SkillsCliVendor(
                skills=[
                    VendoredSkill(name="sample", repo="example/first", update_on_sync=True),
                    VendoredSkill(name="sample", repo="example/second", update_on_sync=True),
                ]
            )


class TestVendorRegistryModel:
    """Test that the vendor registry accepts supported vendors and rejects others."""

    def test_registry_accepts_every_supported_vendor(self) -> None:
        """Test that both supported vendors can be configured together."""

        registry = VendorRegistry.model_validate(
            {
                "version": 1,
                "vendors": {
                    "skills-cli": {"update_on_sync": True, "skills": []},
                    "ecc": {"update_on_sync": True, "profile": "core"},
                },
            }
        )

        assert registry.vendors.skills_cli is not None
        assert registry.vendors.ecc is not None
        assert registry.vendors.ecc.profile == "core"

    def test_unknown_vendor_names_fail(self) -> None:
        """Test that an unsupported vendor name is rejected rather than ignored."""

        with pytest.raises(ValidationError, match="unsupported-vendor"):
            VendorRegistry.model_validate(
                {"version": 1, "vendors": {"unsupported-vendor": {"update_on_sync": True}}}
            )

    def test_undeclared_vendors_are_absent(self) -> None:
        """Test that a registry declaring one vendor leaves the others unset."""

        registry = VendorRegistry.model_validate({"version": 1, "vendors": {"ecc": {}}})

        assert registry.vendors.skills_cli is None

    def test_registry_round_trips_serialized_keys(self) -> None:
        """Test that a serialized registry validates back into the same configuration."""

        registry = VendorRegistryFactory.build(
            vendors=Vendors(skills_cli=SkillsCliVendorFactory.build(), ecc=EccVendorFactory.build())
        )

        assert VendorRegistry.model_validate_json(registry.model_dump_json(by_alias=True)) == registry

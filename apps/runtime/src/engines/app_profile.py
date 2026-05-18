import yaml
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger("runtime.app_profile")

PROFILES_DIR = Path(__file__).parents[2] / "data" / "app_profiles"


@dataclass
class AutomationStrategy:
    preferred_method: str = "cli"
    cli_command: Optional[str] = None
    cli_args: dict = field(default_factory=dict)


@dataclass
class AppProfile:
    app_id: str
    display_name: str
    executable: str
    category: str
    automation: AutomationStrategy = field(default_factory=AutomationStrategy)
    min_version: Optional[str] = None
    known_breaking_versions: list[str] = field(default_factory=list)
    window_patterns: list[str] = field(default_factory=list)
    skill_bindings: dict[str, str] = field(default_factory=dict)


class AppProfileManager:
    def __init__(self, profile_dir: Path = None):
        self.profile_dir = profile_dir or PROFILES_DIR
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, AppProfile] = {}

    def load(self, app_id: str) -> Optional[AppProfile]:
        if app_id in self._cache:
            return self._cache[app_id]

        profile_path = self.profile_dir / f"{app_id}.yaml"
        if not profile_path.exists():
            logger.warning(f"Profile not found: {profile_path}")
            return None

        with open(profile_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        automation_data = data.get("automation", {})
        profile = AppProfile(
            app_id=data["app_id"],
            display_name=data["display_name"],
            executable=data["executable"],
            category=data["category"],
            automation=AutomationStrategy(
                preferred_method=automation_data.get("preferred_method", "cli"),
                cli_command=automation_data.get("cli_command"),
                cli_args=automation_data.get("cli_args", {}),
            ),
            min_version=data.get("version_compatibility", {}).get("min_version"),
            known_breaking_versions=data.get("version_compatibility", {}).get("known_breaking_versions", []),
            window_patterns=data.get("window_patterns", []),
            skill_bindings=data.get("skill_bindings", {}),
        )
        self._cache[app_id] = profile
        return profile

    def save(self, profile: AppProfile):
        profile_path = self.profile_dir / f"{profile.app_id}.yaml"
        with open(profile_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self._to_dict(profile), f, default_flow_style=False, allow_unicode=True)
        self._cache[profile.app_id] = profile
        logger.info(f"Profile saved: {profile_path}")

    def list_all(self) -> list[AppProfile]:
        profiles = []
        for yaml_file in self.profile_dir.glob("*.yaml"):
            app_id = yaml_file.stem
            profile = self.load(app_id)
            if profile:
                profiles.append(profile)
        return profiles

    def _to_dict(self, profile: AppProfile) -> dict:
        return {
            "app_id": profile.app_id,
            "display_name": profile.display_name,
            "executable": profile.executable,
            "category": profile.category,
            "automation": {
                "preferred_method": profile.automation.preferred_method,
                "cli_command": profile.automation.cli_command,
                "cli_args": profile.automation.cli_args,
            },
            "version_compatibility": {
                "min_version": profile.min_version,
                "known_breaking_versions": profile.known_breaking_versions,
            },
            "window_patterns": profile.window_patterns,
            "skill_bindings": profile.skill_bindings,
        }

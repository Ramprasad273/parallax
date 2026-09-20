"""Configuration schema and loader for Parallax."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from parallax.core.logging import logger
from parallax.core.models import RiskSeverity


class ParallaxConfig(BaseModel):
    """Runtime configuration for Parallax CLI and GitHub Action."""

    model_config = ConfigDict(frozen=True)

    version: int = 1
    dialect: str = "snowflake"
    manifest_path: str = "target/manifest.json"
    base_ref: str = "origin/main"
    head_ref: str = "HEAD"
    fail_on: RiskSeverity = RiskSeverity.CRITICAL
    tier_tags: list[str] = Field(
        default_factory=lambda: ["tier_1", "finance", "executive", "board", "p0"]
    )
    ignore_patterns: list[str] = Field(
        default_factory=lambda: ["models/sandbox/**", "models/dev_*"]
    )
    update_existing_comment: bool = True

    @classmethod
    def load(cls, config_path: str | None = None) -> "ParallaxConfig":
        """Load configuration from a file (.parallax.yml) or return defaults."""
        target = Path(config_path) if config_path else Path(".parallax.yml")
        if target.is_file():
            try:
                with open(target, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                return cls(**data)
            except (yaml.YAMLError, OSError, ValueError) as e:
                logger.warning(
                    "Failed to load configuration from %s: %s. Using defaults.", target, e
                )
                return cls()
        return cls()

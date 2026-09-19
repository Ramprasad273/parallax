"""Parser and metadata extractor for dbt manifest.json artifacts."""

import json
from pathlib import Path
from typing import Any

from parallax.core.logging import logger
from parallax.core.models import ExposureNode, ExposureType, ModelLayer


class ManifestError(Exception):
    """Raised when dbt manifest is missing, corrupt, or incompatible."""


class DbtManifest:
    """Ingests and extracts node schemas, dependencies, and exposures from manifest.json."""

    def __init__(
        self,
        nodes: dict[str, dict[str, Any]],
        exposures: dict[str, dict[str, Any]],
        parent_map: dict[str, list[str]],
        child_map: dict[str, list[str]],
    ) -> None:
        self.nodes = nodes
        self.exposures = exposures
        self.parent_map = parent_map
        self.child_map = child_map

        # Index maps for fast lookups
        self._file_to_id: dict[str, str] = {}
        self._name_to_id: dict[str, str] = {}

        for uid, data in self.nodes.items():
            name = data.get("name", "")
            if name:
                self._name_to_id[name] = uid

            file_path = data.get("original_file_path", "")
            if file_path:
                norm = file_path.replace("\\", "/").strip()
                self._file_to_id[norm] = uid
                # Also index basename (e.g. stg_orders.sql)
                basename = norm.split("/")[-1]
                self._file_to_id[basename] = uid

    @classmethod
    def from_file(cls, manifest_path: str | Path) -> "DbtManifest":
        """Load and parse a target/manifest.json file."""
        p = Path(manifest_path).resolve()
        if not p.is_file():
            raise ManifestError(f"dbt manifest file not found at '{p}'. Run `dbt compile` first.")

        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise ManifestError(f"Failed to read dbt manifest at '{p}': {e}") from e

        nodes: dict[str, dict[str, Any]] = data.get("nodes", {})
        exposures: dict[str, dict[str, Any]] = data.get("exposures", {})
        parent_map: dict[str, list[str]] = data.get("parent_map", {})
        child_map: dict[str, list[str]] = data.get("child_map", {})

        # If child_map is missing, construct it from depends_on
        if not child_map:
            child_map = {uid: [] for uid in nodes}
            for uid, node_data in nodes.items():
                deps = node_data.get("depends_on", {}).get("nodes", [])
                for parent_id in deps:
                    child_map.setdefault(parent_id, []).append(uid)

            # Also link exposures
            for exp_id, exp_data in exposures.items():
                for parent_id in exp_data.get("depends_on", {}).get("nodes", []):
                    child_map.setdefault(parent_id, []).append(exp_id)

        logger.debug(
            "Parsed manifest with %d nodes, %d exposures.",
            len(nodes),
            len(exposures),
        )
        return cls(nodes, exposures, parent_map, child_map)

    def get_model_id_by_path(self, file_path: str) -> str | None:
        """Resolve a file path (e.g. models/staging/stg_orders.sql) to a model unique_id."""
        norm = file_path.replace("\\", "/").strip()
        if norm in self._file_to_id:
            return self._file_to_id[norm]
        basename = norm.split("/")[-1]
        return self._file_to_id.get(basename)


    def get_model_id_by_name(self, model_name: str) -> str | None:
        """Resolve a short model name (e.g. stg_orders) to a unique_id."""
        return self._name_to_id.get(model_name)

    def get_node_layer(self, unique_id: str) -> ModelLayer:
        """Infer architectural layer of a node from its file path or tags."""
        node = self.nodes.get(unique_id)
        if not node:
            return ModelLayer.OTHER
        file_path = node.get("original_file_path", "")
        return ModelLayer.from_path(file_path)

    def get_node_tags(self, unique_id: str) -> list[str]:
        """Return list of tags declared on the node."""
        node = self.nodes.get(unique_id)
        if not node:
            return []
        tags = node.get("tags", [])
        return [str(t) for t in tags]

    def get_exposure_node(self, unique_id: str) -> ExposureNode | None:
        """Convert an exposure dictionary into an ExposureNode model."""
        exp_data = self.exposures.get(unique_id)
        if not exp_data:
            return None

        exp_type_str = exp_data.get("type", "dashboard").lower()
        try:
            exp_type = ExposureType(exp_type_str)
        except ValueError:
            exp_type = ExposureType.DASHBOARD

        owner = exp_data.get("owner", {})
        owner_name = owner.get("name") if isinstance(owner, dict) else str(owner)

        return ExposureNode(
            name=exp_data.get("name", unique_id),
            label=exp_data.get("label"),
            exposure_type=exp_type,
            owner_name=owner_name,
            url=exp_data.get("url"),
            description=exp_data.get("description"),
        )

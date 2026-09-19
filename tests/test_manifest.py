"""Unit tests for dbt manifest ingestion and resolution."""

import json
from pathlib import Path
from typing import Any

import pytest

from parallax.core.dbt_manifest import DbtManifest, ManifestError
from parallax.core.models import ExposureType, ModelLayer


@pytest.fixture
def sample_manifest_data() -> dict:
    return {
        "nodes": {
            "model.jaffle_shop.stg_orders": {
                "name": "stg_orders",
                "resource_type": "model",
                "original_file_path": "models/staging/stg_orders.sql",
                "tags": ["staging", "finance"],
                "depends_on": {"nodes": []},
            },
            "model.jaffle_shop.fct_orders": {
                "name": "fct_orders",
                "resource_type": "model",
                "original_file_path": "models/marts/fct_orders.sql",
                "tags": ["marts", "tier_1"],
                "depends_on": {"nodes": ["model.jaffle_shop.stg_orders"]},
                "raw_code": "SELECT order_id, amount FROM {{ ref('stg_orders') }}",
            },
        },
        "exposures": {
            "exposure.jaffle_shop.board_arr": {
                "name": "board_arr",
                "label": "Board ARR Summary",
                "type": "dashboard",
                "owner": {"name": "VP Finance", "email": "finance@example.com"},
                "depends_on": {"nodes": ["model.jaffle_shop.fct_orders"]},
            }
        },
        "child_map": {
            "model.jaffle_shop.stg_orders": ["model.jaffle_shop.fct_orders"],
            "model.jaffle_shop.fct_orders": ["exposure.jaffle_shop.board_arr"],
        },
    }


def test_manifest_load_from_file(tmp_path: Path, sample_manifest_data: dict) -> None:
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(sample_manifest_data), encoding="utf-8")

    manifest = DbtManifest.from_file(manifest_file)
    assert len(manifest.nodes) == 2
    assert len(manifest.exposures) == 1

    # Test file path lookup
    uid = manifest.get_model_id_by_path("models/staging/stg_orders.sql")
    assert uid == "model.jaffle_shop.stg_orders"

    # Test basename lookup
    uid_base = manifest.get_model_id_by_path("stg_orders.sql")
    assert uid_base == "model.jaffle_shop.stg_orders"

    # Test name lookup
    assert manifest.get_model_id_by_name("fct_orders") == "model.jaffle_shop.fct_orders"


def test_manifest_node_layers(sample_manifest_data: dict) -> None:
    manifest = DbtManifest(
        sample_manifest_data["nodes"],
        sample_manifest_data["exposures"],
        {},
        sample_manifest_data["child_map"],
    )
    assert manifest.get_node_layer("model.jaffle_shop.stg_orders") == ModelLayer.STAGING
    assert manifest.get_node_layer("model.jaffle_shop.fct_orders") == ModelLayer.MARTS
    assert manifest.get_node_tags("model.jaffle_shop.fct_orders") == ["marts", "tier_1"]


def test_manifest_exposure_extraction(sample_manifest_data: dict) -> None:
    manifest = DbtManifest(
        sample_manifest_data["nodes"],
        sample_manifest_data["exposures"],
        {},
        sample_manifest_data["child_map"],
    )
    exp = manifest.get_exposure_node("exposure.jaffle_shop.board_arr")
    assert exp is not None
    assert exp.name == "board_arr"
    assert exp.label == "Board ARR Summary"
    assert exp.exposure_type == ExposureType.DASHBOARD
    assert exp.owner_name == "VP Finance"


def test_manifest_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ManifestError):
        DbtManifest.from_file(tmp_path / "non_existent_manifest.json")


def test_manifest_without_child_map(tmp_path: Path, sample_manifest_data: dict) -> None:
    """Verifies that child_map is automatically reconstructed from depends_on.nodes."""
    data = dict(sample_manifest_data)
    del data["child_map"]  # Simulate older dbt version without child_map

    manifest_file = tmp_path / "manifest_no_child_map.json"
    manifest_file.write_text(json.dumps(data), encoding="utf-8")

    manifest = DbtManifest.from_file(manifest_file)
    assert "model.jaffle_shop.stg_orders" in manifest.child_map
    assert "model.jaffle_shop.fct_orders" in manifest.child_map["model.jaffle_shop.stg_orders"]
    # Exposure dependency should also be linked
    assert "model.jaffle_shop.fct_orders" in manifest.child_map
    assert "exposure.jaffle_shop.board_arr" in manifest.child_map["model.jaffle_shop.fct_orders"]


def test_manifest_exposure_owner_string_and_custom_types() -> None:
    """Verifies that owner as a string and unknown exposure types are safely handled."""
    nodes: dict[str, dict[str, Any]] = {}
    exposures: dict[str, dict[str, Any]] = {
        "exposure.jaffle_shop.str_owner": {
            "name": "str_owner",
            "type": "dashboard",
            "owner": "Data Lead <data@example.com>",
        },
        "exposure.jaffle_shop.custom_type": {
            "name": "custom_type",
            "type": "custom_bi_tool_unknown",
            "owner": {},
        },
    }
    manifest = DbtManifest(nodes, exposures, {}, {})

    exp1 = manifest.get_exposure_node("exposure.jaffle_shop.str_owner")
    assert exp1 is not None
    assert exp1.owner_name == "Data Lead <data@example.com>"

    exp2 = manifest.get_exposure_node("exposure.jaffle_shop.custom_type")
    assert exp2 is not None
    # Defaults to ExposureType.DASHBOARD when unknown
    assert exp2.exposure_type == ExposureType.DASHBOARD
    assert exp2.owner_name is None


def test_manifest_windows_backslash_paths() -> None:
    """Verifies that models indexed with Windows backslash paths resolve properly."""
    nodes: dict[str, dict[str, Any]] = {
        "model.jaffle_shop.stg_orders": {
            "name": "stg_orders",
            "resource_type": "model",
            "original_file_path": r"models\staging\stg_orders.sql",
        }
    }
    manifest = DbtManifest(nodes, {}, {}, {})

    # Lookup with posix slash
    assert (
        manifest.get_model_id_by_path("models/staging/stg_orders.sql")
        == "model.jaffle_shop.stg_orders"
    )
    # Lookup with Windows backslash
    assert (
        manifest.get_model_id_by_path(r"models\staging\stg_orders.sql")
        == "model.jaffle_shop.stg_orders"
    )
    # Lookup with basename
    assert manifest.get_model_id_by_path("stg_orders.sql") == "model.jaffle_shop.stg_orders"


def test_manifest_corrupted_json(tmp_path: Path) -> None:
    """Verifies that malformed JSON raises ManifestError."""
    bad_file = tmp_path / "corrupt_manifest.json"
    bad_file.write_text("{ unquoted_key: missing_brackets", encoding="utf-8")

    with pytest.raises(ManifestError, match="Failed to read dbt manifest"):
        DbtManifest.from_file(bad_file)


def test_manifest_nonexistent_lookups() -> None:
    """Verifies safe defaults when querying non-existent nodes."""
    manifest = DbtManifest({}, {}, {}, {})
    assert manifest.get_model_id_by_path("does_not_exist.sql") is None
    assert manifest.get_model_id_by_name("non_existent") is None
    assert manifest.get_node_layer("non_existent_id") == ModelLayer.OTHER
    assert manifest.get_node_tags("non_existent_id") == []
    assert manifest.get_exposure_node("non_existent_id") is None

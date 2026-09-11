"""Unit tests for dbt manifest ingestion and resolution."""

import json
from pathlib import Path

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

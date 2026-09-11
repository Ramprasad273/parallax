"""DAG Lineage Graph and Blast Radius Propagation Engine."""

import networkx as nx  # type: ignore[import-untyped]

from parallax.core.dbt_manifest import DbtManifest
from parallax.core.models import DownstreamNode, ExposureNode


class LineageGraph:
    """
    Builds an in-memory directed acyclic graph (DAG) of the dbt project and
    traverses downstream dependencies to map blast radius.
    """

    def __init__(self, manifest: DbtManifest) -> None:
        self.manifest = manifest
        self.graph = nx.DiGraph()
        self._build_graph()

    def _build_graph(self) -> None:
        """Construct directed edges from upstream to downstream."""
        # Add model nodes
        for uid, data in self.manifest.nodes.items():
            self.graph.add_node(
                uid,
                name=data.get("name", uid),
                type=data.get("resource_type", "model"),
                file_path=data.get("original_file_path", ""),
            )

        # Add exposure nodes
        for uid, data in self.manifest.exposures.items():
            self.graph.add_node(
                uid,
                name=data.get("name", uid),
                type="exposure",
            )

        # Add edges: parent -> child
        for parent_id, children in self.manifest.child_map.items():
            for child_id in children:
                self.graph.add_edge(parent_id, child_id)

    def get_downstream_blast_radius(
        self,
        modified_model_ids: list[str],
        dropped_or_modified_columns: dict[str, list[str]] | None = None,
    ) -> tuple[list[DownstreamNode], list[ExposureNode], int]:
        """
        Calculate all downstream models, exposures, and max DAG depth
        originating from modified_model_ids.
        """
        dropped_or_modified_columns = dropped_or_modified_columns or {}
        all_descendants: set[str] = set()

        for mid in modified_model_ids:
            if self.graph.has_node(mid):
                desc = nx.descendants(self.graph, mid)
                all_descendants.update(desc)

        downstream_models: list[DownstreamNode] = []
        impacted_exposures: list[ExposureNode] = []
        max_depth = 0

        # All dropped columns across modified models
        all_dropped_cols: set[str] = set()
        for cols in dropped_or_modified_columns.values():
            all_dropped_cols.update(cols)

        for node_id in all_descendants:
            if not self.graph.has_node(node_id):
                continue

            node_data = self.graph.nodes[node_id]
            node_type = node_data.get("type", "")

            # Compute shortest distance from any of the modified sources
            distances: list[int] = []
            for mid in modified_model_ids:
                if self.graph.has_node(mid) and nx.has_path(self.graph, mid, node_id):
                    dist = nx.shortest_path_length(self.graph, mid, node_id)
                    distances.append(dist)
                    max_depth = max(max_depth, dist)

            min_dist = min(distances) if distances else 1

            if node_type == "exposure":
                exp_node = self.manifest.get_exposure_node(node_id)
                if exp_node is not None:
                    impacted_exposures.append(exp_node)
            else:
                # Downstream model
                layer = self.manifest.get_node_layer(node_id)
                tags = self.manifest.get_node_tags(node_id)
                file_path = node_data.get("file_path")

                # Column-level break heuristic: check if downstream node references dropped column
                broken_cols: list[str] = []
                if all_dropped_cols:
                    raw_node = self.manifest.nodes.get(node_id, {})
                    code_text = (
                        raw_node.get("raw_code") or raw_node.get("compiled_code") or ""
                    ).lower()
                    for col in all_dropped_cols:
                        if col.lower() in code_text:
                            broken_cols.append(col)

                downstream_models.append(
                    DownstreamNode(
                        unique_id=node_id,
                        name=node_data.get("name", node_id),
                        layer=layer,
                        file_path=file_path,
                        tags=tags,
                        broken_columns=broken_cols,
                        distance_from_source=min_dist,
                    )
                )

        # Sort downstream models by layer and distance
        downstream_models.sort(key=lambda m: (m.distance_from_source, m.name))
        impacted_exposures.sort(key=lambda e: e.name)

        return downstream_models, impacted_exposures, max_depth

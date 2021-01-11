"""Parser for PostgreSQL EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) output."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

SCAN_NODE_TYPES = {
    "Seq Scan",
    "Index Scan",
    "Index Only Scan",
    "Bitmap Heap Scan",
    "Bitmap Index Scan",
    "Tid Scan",
    "Tid Range Scan",
}


@dataclass
class ExplainMetrics:
    planning_time_ms: float
    execution_time_ms: float
    total_cost: float
    actual_rows: int
    shared_hit_blocks: int
    shared_read_blocks: int
    shared_dirtied_blocks: int
    shared_written_blocks: int
    temp_read_blocks: int
    temp_written_blocks: int
    scan_types: List[str] = field(default_factory=list)
    indexes_used: List[str] = field(default_factory=list)

    @property
    def total_shared_blocks(self) -> int:
        return self.shared_hit_blocks + self.shared_read_blocks

    @property
    def buffer_hit_ratio_pct(self) -> float:
        total = self.total_shared_blocks
        if total == 0:
            return 100.0
        return round((self.shared_hit_blocks / total) * 100.0, 2)


def _walk_plan_node(
    node: Dict[str, Any],
    scans: Set[str],
    indexes: Set[str],
) -> None:
    node_type = node.get("Node Type", "")
    if node_type in SCAN_NODE_TYPES:
        scans.add(node_type)
    if "Index Name" in node and node["Index Name"]:
        indexes.add(str(node["Index Name"]))
    for child in node.get("Plans", []):
        _walk_plan_node(child, scans, indexes)


def parse_explain_json(explain_payload: Any) -> ExplainMetrics:
    """Parse the root array returned by EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)."""
    if isinstance(explain_payload, list):
        if not explain_payload:
            raise ValueError("Empty EXPLAIN JSON payload")
        root = explain_payload[0]
    elif isinstance(explain_payload, dict):
        root = explain_payload
    else:
        raise TypeError(f"Unsupported EXPLAIN payload type: {type(explain_payload)!r}")

    plan = root.get("Plan")
    if not isinstance(plan, dict):
        raise ValueError("Missing 'Plan' object in EXPLAIN JSON payload")

    scans: Set[str] = set()
    indexes: Set[str] = set()
    _walk_plan_node(plan, scans, indexes)

    return ExplainMetrics(
        planning_time_ms=float(root.get("Planning Time", 0.0)),
        execution_time_ms=float(root.get("Execution Time", 0.0)),
        total_cost=float(plan.get("Total Cost", 0.0)),
        actual_rows=int(plan.get("Actual Rows", 0)),
        shared_hit_blocks=int(plan.get("Shared Hit Blocks", 0)),
        shared_read_blocks=int(plan.get("Shared Read Blocks", 0)),
        shared_dirtied_blocks=int(plan.get("Shared Dirtied Blocks", 0)),
        shared_written_blocks=int(plan.get("Shared Written Blocks", 0)),
        temp_read_blocks=int(plan.get("Temp Read Blocks", 0)),
        temp_written_blocks=int(plan.get("Temp Written Blocks", 0)),
        scan_types=sorted(scans),
        indexes_used=sorted(indexes),
    )
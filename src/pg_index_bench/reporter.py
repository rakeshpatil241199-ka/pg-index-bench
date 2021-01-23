"""Generates Markdown comparison tables and JSON reports for baseline vs optimized runs."""

import json
from pathlib import Path
from typing import Any, Dict, List


def compute_comparison(
    baseline_report: Dict[str, Any],
    optimized_report: Dict[str, Any],
) -> List[Dict[str, Any]]:
    base_map = {q["query_name"]: q for q in baseline_report["queries"]}
    opt_map = {q["query_name"]: q for q in optimized_report["queries"]}

    comparisons: List[Dict[str, Any]] = []
    for q_name in sorted(set(base_map.keys()) & set(opt_map.keys())):
        b = base_map[q_name]
        o = opt_map[q_name]

        b_p95 = max(float(b["p95_ms"]), 0.001)
        o_p95 = max(float(o["p95_ms"]), 0.001)
        speedup = round(b_p95 / o_p95, 2)

        b_blocks = float(b["avg_shared_hit_blocks"]) + float(b["avg_shared_read_blocks"])
        o_blocks = float(o["avg_shared_hit_blocks"]) + float(o["avg_shared_read_blocks"])
        block_reduction_pct = (
            0.0 if b_blocks == 0 else round(((b_blocks - o_blocks) / b_blocks) * 100.0, 2)
        )

        comparisons.append(
            {
                "query_name": q_name,
                "baseline_p95_ms": b["p95_ms"],
                "optimized_p95_ms": o["p95_ms"],
                "speedup_x": speedup,
                "baseline_blocks": round(b_blocks, 1),
                "optimized_blocks": round(o_blocks, 1),
                "block_reduction_pct": block_reduction_pct,
                "baseline_scans": ", ".join(b["scan_types"]),
                "optimized_scans": ", ".join(o["scan_types"]),
                "indexes_used": ", ".join(o["indexes_used"]) or "none",
            }
        )
    return comparisons


def render_markdown_report(
    baseline_report: Dict[str, Any],
    optimized_report: Dict[str, Any],
) -> str:
    rows = compute_comparison(baseline_report, optimized_report)
    lines: List[str] = [
        "# PostgreSQL 15 Indexing Benchmark Comparison",
        "",
        "| Query | Baseline p95 (ms) | Optimized p95 (ms) | Speedup | Buffer Reduction | Optimized Plan | Indexes Used |",
        "| :--- | :---: | :---: | :---: | :---: | :--- | :--- |",
    ]
    for r in rows:
        lines.append(
            f"| `{r['query_name']}` | {r['baseline_p95_ms']} | {r['optimized_p95_ms']} "
            f"| **{r['speedup_x']}x** | {r['block_reduction_pct']}% "
            f"| {r['optimized_scans']} | `{r['indexes_used']}` |"
        )

    opt_table = optimized_report.get("storage", {}).get("table", {})
    opt_indexes = optimized_report.get("storage", {}).get("indexes", [])
    if opt_table:
        heap_mb = round(opt_table.get("heap_bytes", 0) / (1024 * 1024), 2)
        idx_mb = round(opt_table.get("total_index_bytes", 0) / (1024 * 1024), 2)
        lines.extend(
            [
                "",
                "## Storage Footprint (Optimized Profile)",
                "",
                f"- Table Heap Size: **{heap_mb} MB**",
                f"- Total Index Size: **{idx_mb} MB**",
                "",
                "| Index Name | Size (MB) | Index Scans |",
                "| :--- | :---: | :---: |",
            ]
        )
        for idx in opt_indexes:
            sz_mb = round(idx.get("index_bytes", 0) / (1024 * 1024), 2)
            lines.append(f"| `{idx['index_name']}` | {sz_mb} | {idx.get('idx_scan', 0)} |")

    return "\n".join(lines) + "\n"


def save_reports(
    baseline_report: Dict[str, Any],
    optimized_report: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "benchmark_comparison.json"
    md_path = output_dir / "benchmark_comparison.md"

    payload = {
        "baseline": baseline_report,
        "optimized": optimized_report,
        "comparison": compute_comparison(baseline_report, optimized_report),
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_report(baseline_report, optimized_report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
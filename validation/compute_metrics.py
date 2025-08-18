#!/usr/bin/env python3
"""
Merge harness brittleness metrics with AgentBound-style entropy metrics,
and attach 95% Wilson score confidence intervals to selected rates.

Writes: validation/results/summary/all_results.json
"""

import argparse, json, math, re
from pathlib import Path
from typing import Dict, List, Tuple

# --- Kind inference from README ---
_GEN_RE = re.compile(r"(llm|gpt|model|generate|writer|assistant|agent|supervisor)", re.I)

def infer_kind(node: Dict) -> str:
    k = (node.get("kind") or "").lower()
    if k in ("generative", "deterministic"):
        return k
    label = f"{node.get('id','')} {node.get('label','')}"
    return "generative" if _GEN_RE.search(label or "") else "deterministic"

def to_canonical(graph: Dict) -> Tuple[List[Dict], List[Tuple[str, str]], str]:
    if "edges" in graph and isinstance(graph["edges"], list) and graph["edges"] and isinstance(graph["edges"][0], list):
        nodes = graph["nodes"]
        edges = [(a, b) for a, b in graph["edges"]]
        start = graph.get("start_node") or (nodes[0]["id"] if nodes else "")
        return nodes, edges, start
    nodes = graph["nodes"]
    edges: List[Tuple[str, str]] = []
    for n in nodes:
        for tgt in (n.get("edges") or []):
            edges.append((n["id"], tgt))
    start = graph.get("start_node") or (nodes[0]["id"] if nodes else "")
    return nodes, edges, start

def compute_counts(nodes: List[Dict], edges: List[Tuple[str, str]]) -> Dict:
    kinds: Dict[str, str] = {n["id"]: infer_kind(n) for n in nodes}
    G = sum(1 for k in kinds.values() if k == "generative")
    D = sum(1 for k in kinds.values() if k == "deterministic")
    gg = sum(1 for a,b in edges if kinds.get(a)=="generative" and kinds.get(b)=="generative")
    coupling = 1.0 + (math.sqrt(gg) / max(1, G)) if G > 0 else 1.0
    entropy = (G / max(1, G + D)) * coupling + 0.1 * gg
    level = "Low" if entropy < 0.30 else "Moderate" if entropy < 0.60 else "High" if entropy < 0.90 else "Very High"
    return {
        "generative_nodes": G,
        "deterministic_nodes": D,
        "gen_to_gen_edges": gg,
        "coupling_factor": round(coupling, 6),
        "entropy_score": round(entropy, 6),
        "entropy_level": level,
    }

def wilson_interval(phat: float, n: int, z: float = 1.96) -> Tuple[float,float]:
    """95% Wilson score interval for a binomial proportion."""
    if n <= 0:
        return (0.0, 0.0)
    denom = 1.0 + (z*z)/n
    center = (phat + (z*z)/(2*n)) / denom
    margin = z * math.sqrt((phat*(1.0 - phat)/n) + (z*z)/(4*n*n)) / denom
    lo = max(0.0, center - margin)
    hi = min(1.0, center + margin)
    return (lo, hi)

def read_json(p: Path):
    return json.loads(p.read_text())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graphs", required=True, help="Dir with *.json graphs (recurses)")
    ap.add_argument("--results", default="validation/results", help="Harness results base dir")
    args = ap.parse_args()

    graphs_root = Path(args.graphs)
    results_dir = Path(args.results)
    harness_summaries = results_dir / "summary" / "ALL.summaries.json"
    if not harness_summaries.exists():
        raise SystemExit("Harness summaries not found. Run run_harness.py first.")

    summaries_by_stem = read_json(harness_summaries)
    merged: List[Dict] = []

    graph_files = sorted(graphs_root.rglob("*.json"))
    if not graph_files:
        raise SystemExit(f"No JSON graphs found under {graphs_root}")

    for graph_path in graph_files:
        name = graph_path.stem
        if name not in summaries_by_stem:
            continue

        # Harness summary
        s = summaries_by_stem[name]
        n = int(s.get("runs", 0))
        fail = float(s.get("failure_rate", 0.0))
        loop = float(s.get("loop_rate", 0.0))
        tout = float(s.get("timeout_rate", 0.0))

        fail_ci = wilson_interval(fail, n)
        loop_ci = wilson_interval(loop, n)
        tout_ci = wilson_interval(tout, n)

        # Entropy metrics from graph structure
        gdict = read_json(graph_path)
        nodes, edges, _ = to_canonical(gdict)
        ab_metrics = compute_counts(nodes, edges)

        merged.append({
            "graph": name,
            "path": str(graph_path),
            **s,  # existing brittleness metrics
            "failure_rate_ci95": [round(fail_ci[0], 6), round(fail_ci[1], 6)],
            "loop_rate_ci95":    [round(loop_ci[0], 6), round(loop_ci[1], 6)],
            "timeout_rate_ci95": [round(tout_ci[0], 6), round(tout_ci[1], 6)],
            "ci_method": "wilson",
            **ab_metrics
        })

    out = results_dir / "summary" / "all_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(merged, indent=2))
    print(f"[compute] Wrote merged results -> {out}")

if __name__ == "__main__":
    main()

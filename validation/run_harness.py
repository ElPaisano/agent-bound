#!/usr/bin/env python3
"""
AgentBound validation harness (simulator)
"""

import argparse
import json
import random
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------- Defaults (overridable via CLI/config) ----------
DEFAULTS = {
    "runs_per_graph": 300,
    "global_seed": 42,
    "step_cap": 200,
    "default_failure_prob": {"generative": 0.12, "deterministic": 0.02},
}

# ---------- Data structures ----------
@dataclass
class Node:
    id: str
    kind: str = "generative"  # "generative" | "deterministic"
    edges: List[str] = None
    failure_prob: Optional[float] = None
    max_retries: int = 0
    loop_max_iters: Optional[int] = None

@dataclass
class RunStats:
    seed: int
    success: bool
    timeout: bool
    retries: int
    steps: int
    touched_loop: bool
    handoffs: List[Dict]  # [{from_kind, to_kind, ok}]
    path: List[str]

# ---------- Loader ----------
def load_graph(path: Path, defaults=DEFAULTS) -> Tuple[Dict[str, Node], str]:
    data = json.loads(Path(path).read_text())
    nodes: Dict[str, Node] = {}
    for raw in data["nodes"]:
        edges = list(raw.get("edges") or [])
        h = raw.get("__harness", {}) or {}
        node = Node(
            id=raw["id"],
            kind=(raw.get("kind") or "generative").lower(),
            edges=edges,
            failure_prob=h.get("failure_prob"),
            max_retries=int(h.get("retry_policy", {}).get("max_retries", 0)),
            loop_max_iters=h.get("loop_policy", {}).get("max_iters"),
        )
        nodes[node.id] = node
    start = data.get("start_node") or data["nodes"][0]["id"]
    # Fill missing failure_prob with defaults by kind
    for n in nodes.values():
        if n.failure_prob is None:
            n.failure_prob = defaults["default_failure_prob"].get(n.kind, 0.1)
    return nodes, start

# ---------- Simulation ----------
def attempt_node(node: Node, rng: random.Random) -> bool:
    return rng.random() >= node.failure_prob

def choose_next(node: Node, rng: random.Random) -> Optional[str]:
    if not node.edges:
        return None
    return rng.choice(node.edges)

def simulate_run(
    nodes: Dict[str, Node],
    start_node: str,
    step_cap: int,
    seed: int,
) -> RunStats:
    rng = random.Random(seed)
    retries_total = 0
    steps = 0
    visited_counts: Dict[str, int] = {}
    touched_loop = False
    handoffs: List[Dict] = []
    path: List[str] = []

    current_id = start_node
    while True:
        steps += 1
        if steps > step_cap:
            return RunStats(seed, False, True, retries_total, step_cap, touched_loop, handoffs, path)

        node = nodes[current_id]
        path.append(current_id)

        # Loop budget
        visited_counts[current_id] = visited_counts.get(current_id, 0) + 1
        if node.loop_max_iters is not None and visited_counts[current_id] > node.loop_max_iters:
            return RunStats(seed, False, False, retries_total, steps, True, handoffs, path)
        if visited_counts[current_id] > 1:
            touched_loop = True

        # Attempts + retries
        attempts_left = node.max_retries + 1
        succeeded = False
        while attempts_left > 0:
            if attempt_node(node, rng):
                succeeded = True
                break
            attempts_left -= 1
            if attempts_left > 0:
                retries_total += 1
        if not succeeded:
            return RunStats(seed, False, False, retries_total, steps, touched_loop, handoffs, path)

        # Advance
        next_id = choose_next(node, rng)
        if next_id is None:
            return RunStats(seed, True, False, retries_total, steps, touched_loop, handoffs, path)

        to_node = nodes[next_id]
        handoffs.append({"from_kind": node.kind, "to_kind": to_node.kind, "ok": True})
        current_id = next_id

# ---------- Aggregation ----------
def summarize_runs(runs: List[RunStats]) -> Dict:
    n = len(runs)
    failure_runs = [r for r in runs if not r.success]
    timeout_runs = [r for r in runs if r.timeout]
    loop_runs = [r for r in runs if r.touched_loop]

    def mean(xs: List[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    retries_mean = mean([r.retries for r in runs])
    steps_success = mean([r.steps for r in runs if r.success])
    steps_failure = mean([r.steps for r in runs if not r.success])

    gg_events = 0
    gg_total = 0
    for r in runs:
        for h in r.handoffs:
            if h["from_kind"] == "generative" and h["to_kind"] == "generative":
                gg_total += 1
                gg_events += (0 if h.get("ok", True) else 1)
    handoff_error_rate = (gg_events / gg_total) if gg_total else 0.0

    failure_rate = len(failure_runs) / n if n else 0.0
    loop_rate = len(loop_runs) / n if n else 0.0
    timeout_rate = len(timeout_runs) / n if n else 0.0

    brittleness = 0.6 * failure_rate + 0.2 * loop_rate + 0.2 * min(1.0, retries_mean / 2.0)

    return {
        "runs": n,
        "failure_rate": round(failure_rate, 6),
        "avg_retries": round(retries_mean, 6),
        "loop_rate": round(loop_rate, 6),
        "timeout_rate": round(timeout_rate, 6),
        "mean_path_len_success": round(steps_success, 6),
        "mean_path_len_failure": round(steps_failure, 6),
        "handoff_error_rate": round(handoff_error_rate, 6),
        "brittleness_index": round(brittleness, 6),
    }

# ---------- IO helpers ----------
def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2))

def simulate_graph_file(
    graph_path: Path,
    results_dir: Path,
    runs: int,
    seed: int,
    step_cap: int,
    write_raw: bool,
    raw_dir: Path,
    defaults=DEFAULTS,
) -> Dict:
    nodes, start = load_graph(graph_path, defaults)
    run_stats: List[RunStats] = []
    if write_raw:
        raw_dir.mkdir(parents=True, exist_ok=True)

    for i in range(runs):
        rseed = seed + i
        stats = simulate_run(nodes, start, step_cap, rseed)
        run_stats.append(stats)
        if write_raw:
            raw_path = raw_dir / f"{graph_path.stem}_seed{rseed}.json"
            write_json(raw_path, asdict(stats))

    summary = summarize_runs(run_stats)
    summary_path = results_dir / "summary" / f"{graph_path.stem}.summary.json"
    write_json(summary_path, {"graph": str(graph_path), **summary})
    return summary

# ---------- CLI ----------
def parse_args():
    p = argparse.ArgumentParser(description="AgentBound validation harness")
    p.add_argument("--graphs", required=True, help="Dir with *.json graphs (recurses).")
    p.add_argument("--results", default="validation/results", help="Output dir for results/")
    p.add_argument("--runs", type=int, default=DEFAULTS["runs_per_graph"])
    p.add_argument("--seed", type=int, default=DEFAULTS["global_seed"])
    p.add_argument("--step-cap", type=int, default=DEFAULTS["step_cap"])
    p.add_argument("--write-raw", action="store_true",
                  help="Write per-run JSONs (default: summaries only).")
    p.add_argument("--raw-dir", default="validation/results/raw_runs",
                  help="Directory for raw run files if --write-raw is set.")
    p.add_argument("--clean", action="store_true",
                  help="Delete results dir before running.")   
    return p.parse_args()

def main():
    t0 = time.time()
    args = parse_args()
    if args.clean:
        if Path(args.results).exists():
            import shutil
            shutil.rmtree(args.results)


    graphs_root = Path(args.graphs)
    results_dir = Path(args.results)
    raw_dir = Path(args.raw_dir)

    graph_files = sorted([p for p in graphs_root.rglob("*.json") if p.is_file()])
    if not graph_files:
        raise SystemExit(f"No JSON graphs found under {graphs_root}")

    summaries = {}
    for g in graph_files:
        s = simulate_graph_file(
            graph_path=g,
            results_dir=results_dir,
            runs=args.runs,
            seed=args.seed,
            step_cap=args.step_cap,
            write_raw=args.write_raw,
            raw_dir=raw_dir,
        )
        summaries[g.stem] = s

    # metadata + ALL.summaries.json
    meta = {
        "runs": args.runs,
        "seed": args.seed,
        "step_cap": args.step_cap,
        "harness_version": "v0",
    }
    write_json(results_dir / "summary" / "metadata.json", meta)
    write_json(results_dir / "summary" / "ALL.summaries.json", summaries)

    dt = time.time() - t0
    print(f"[harness] Simulated {len(graph_files)} graphs in {dt:.2f}s; output -> {results_dir}")

if __name__ == "__main__":
    main()

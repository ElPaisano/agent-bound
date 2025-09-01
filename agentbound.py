#!/usr/bin/env python3
import sys, json, math, re, os
import networkx as nx
import matplotlib.pyplot as plt

GEN_HINTS = re.compile(
    r"(?:\b|_)(llm|gpt|model|generate|generator|writer|assistant|agent|supervisor)(?:\b|_)",
    re.I,
)
OUT_DIR = "out"

def infer_kind(node_id, label):
    if node_id.startswith("__"): return "aux"
    txt = f"{node_id} {label or ''}".lower()
    return "generative" if GEN_HINTS.search(txt) else "deterministic"

def compute_entropy(nodes, edges):
    # exclude aux nodes from scoring
    filtered = [n for n in nodes if n["kind"] != "aux"]
    G = sum(1 for n in filtered if n["kind"] == "generative")
    D = sum(1 for n in filtered if n["kind"] == "deterministic")
    gen_ids = {n["id"] for n in filtered if n["kind"] == "generative"}
    gg = sum(1 for a,b in edges if a in gen_ids and b in gen_ids)
    coupling = 1.0 + (math.sqrt(gg) / max(1, G)) if G>0 else 1.0
    score = (G / max(1, G+D)) * coupling + 0.1*gg
    level = "Low" if score < 0.3 else "Moderate" if score < 0.6 else "High" if score < 0.9 else "Very High"
    return dict(entropy_score=round(score,3), entropy_level=level,
                generative_nodes=G, deterministic_nodes=D,
                gen_to_gen_edges=gg, coupling_factor=round(coupling,3))

def resilience_index(results):
    try:
        bf = float(results["baseline"]["fail_rate"]); pf = float(results["perturbed"]["fail_rate"])
        eps = 1e-6
        if bf<=eps and pf<=eps: return 1.0
        return max(0.0, min(1.0, 1.0 - pf/max(eps,bf)))
    except Exception:
        return None

def quadrant(entropy, res):
    if res is None: return None
    e_high = entropy >= 0.5; r_high = res >= 0.5
    if not e_high and not r_high: return "Fragile"
    if e_high and not r_high:     return "Chaotic Fragility"
    if not e_high and r_high:     return "Robust"
    return "Antifragile"

def main(graph_json, results_json=None, kind_map_json=None, output_path=None):
    # normalize empty-string args
    results_json = results_json if results_json and results_json.strip() else None
    kind_map_json = kind_map_json if kind_map_json and kind_map_json.strip() else None
    output_path  = output_path  if output_path  and output_path.strip()  else None
    
    data = json.load(open(graph_json))
    kind_map = json.load(open(kind_map_json)) if (kind_map_json and os.path.exists(kind_map_json)) else {}

     # Build nodes with kinds (+ warn on kind_map mismatches)
    nodes = []
    graph_ids = set()
    for n in data["nodes"]:
        nid   = n["id"]
        label = n.get("label") or nid
        kind  = (kind_map.get(nid) if kind_map else None) or infer_kind(nid, label)
        nodes.append({"id": nid, "label": label, "kind": kind})
        graph_ids.add(nid)
    edges = [tuple(e) for e in data["edges"]]

    if kind_map:
        km_ids = set(kind_map.keys())
        missing_in_graph = sorted(km_ids - graph_ids)
        unused_in_km     = sorted(graph_ids - km_ids)
        if missing_in_graph:
            print(f"[warn] kind_map keys not found in graph: {missing_in_graph}")
        if unused_in_km:
            print(f"[note] nodes not in kind_map (will be inferred): {unused_in_km}")

    # Compute metrics
    met = compute_entropy(nodes, edges)

    # Optional resilience/quadrant
    res = None
    if results_json and os.path.exists(results_json):
        res = resilience_index(json.load(open(results_json)))
        if res is not None:
            met["resilience_index"] = round(res,3)
            met["quadrant"] = quadrant(met["entropy_score"], res)

    # Draw (pure matplotlib)
    G = nx.DiGraph()
    for n in nodes: G.add_node(n["id"], **n)
    for a,b in edges: G.add_edge(a,b)

    pos = nx.spring_layout(G, seed=42)  # deterministic layout
    gen_ids = {n["id"] for n in nodes if n["kind"]=="generative"}

    # Node styling
    node_colors = []
    node_sizes  = []
    for nid in G.nodes:
        kind = G.nodes[nid]["kind"]
        if kind=="generative": node_colors.append("#cfe8ff"); node_sizes.append(2200)
        elif kind=="aux":      node_colors.append("#f5f5f5"); node_sizes.append(1800)
        else:                  node_colors.append("#e8e8e8"); node_sizes.append(2000)

    plt.figure(figsize=(9,7))
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes, linewidths=1.2, edgecolors="#444444")
    nx.draw_networkx_labels(G, pos, labels={n:G.nodes[n].get("label",n) for n in G.nodes}, font_size=10)

    # Draw edges: gen->gen in red
    gg_edges = [(a,b) for a,b in G.edges if a in gen_ids and b in gen_ids]
    other_edges = [(a,b) for a,b in G.edges if (a,b) not in gg_edges]
    nx.draw_networkx_edges(G, pos, edgelist=other_edges, arrows=True, arrowsize=14, width=1.2, edge_color="#666666")
    nx.draw_networkx_edges(G, pos, edgelist=gg_edges, arrows=True, arrowsize=16, width=2.4, edge_color="red")

    # Footer with metrics
    footer = f"Entropy: {met['entropy_score']} ({met['entropy_level']})  |  G={met['generative_nodes']}  D={met['deterministic_nodes']}  gen→gen={met['gen_to_gen_edges']}  coupling={met['coupling_factor']}"
    if "quadrant" in met: footer += f"  |  Resilience={met['resilience_index']}  →  {met['quadrant']}"
    plt.title("AgentBound — pre-hoc structural analysis", fontsize=12, pad=12)
    plt.figtext(0.5, 0.01, footer, ha="center", fontsize=9)

    plt.tight_layout(rect=(0,0.03,1,0.97))

    # Build names from the *input* JSON path

    # Determine base output directory.
    # Default: current working directory. Otherwise: user-specified path.

    base_dir = output_path if output_path else "."
    out_dir = os.path.join(base_dir, OUT_DIR)
    os.makedirs(out_dir, exist_ok=True)

    basename   = os.path.splitext(os.path.basename(graph_json))[0]
    out_png    = os.path.join(out_dir, f"{basename}.png")
    out_report = os.path.join(out_dir, f"{basename}_report.json")

    plt.savefig(out_png, dpi=200)
    plt.close()

    # Save the metrics to a matching report file (handy for A/B)
    with open(out_report, "w") as f:
        json.dump({"graph_json": graph_json, **met}, f, indent=2)

    print(f"Graph PNG saved to: {out_png}")
    print(f"Report saved to: {out_report}")

    # Print JSON summary
    print(json.dumps({"graph_json": graph_json, **met}, indent=2))
    print(f"\nSaved: {out_png}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agentbound.py <graph_json> [results_json] [kind_map_json] [output_path]")
        sys.exit(1)
    main(
            sys.argv[1],
            sys.argv[2] if len(sys.argv) > 2 else None,
            sys.argv[3] if len(sys.argv) > 3 else None,
            sys.argv[4] if len(sys.argv) > 4 else None,
        )
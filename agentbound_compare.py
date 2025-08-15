#!/usr/bin/env python3
import json, os, math, re, argparse
import networkx as nx
import matplotlib.pyplot as plt

GEN_HINTS = re.compile(r"(?:\b|_)(llm|gpt|model|generate|writer|assistant|agent|supervisor)(?:\b|_)", re.I)

def infer_kind(nid, label):
    if nid.startswith("__"): return "aux"
    txt = f"{nid} {label or ''}".lower()
    return "generative" if GEN_HINTS.search(txt) else "deterministic"

def build_nodes_edges(data, kind_map=None):
    kind_map = kind_map or {}
    nodes = []
    for n in data["nodes"]:
        nid = n["id"]; label = n.get("label") or nid
        kind = kind_map.get(nid) or infer_kind(nid, label)
        nodes.append({"id": nid, "label": label, "kind": kind})
    edges = [tuple(e) for e in data["edges"]]
    return nodes, edges

def compute_entropy(nodes, edges):
    filt = [n for n in nodes if n["kind"] != "aux"]
    Gc = sum(1 for n in filt if n["kind"]=="generative")
    Dc = sum(1 for n in filt if n["kind"]=="deterministic")
    gen_ids = {n["id"] for n in filt if n["kind"]=="generative"}
    gg = sum(1 for a,b in edges if a in gen_ids and b in gen_ids)
    coupling = 1.0 + (math.sqrt(gg)/max(1,Gc)) if Gc>0 else 1.0
    score = (Gc/max(1,Gc+Dc))*coupling + 0.1*gg
    band = "Low" if score<0.3 else "Moderate" if score<0.6 else "High" if score<0.9 else "Very High"
    return dict(entropy_score=round(score,3), entropy_level=band,
                generative_nodes=Gc, deterministic_nodes=Dc,
                gen_to_gen_edges=gg, coupling_factor=round(coupling,3))

def find_drivers(nodes, edges):
    """Return {'risk_hub': <node or None>, 'anchors': [ids], 'gg_edges': [(a,b),..]}"""
    G = nx.DiGraph()
    for n in nodes: G.add_node(n["id"], **n)
    for a,b in edges: G.add_edge(a,b)

    gen_ids = {n["id"] for n in nodes if n["kind"]=="generative"}
    det_ids = {n["id"] for n in nodes if n["kind"]=="deterministic"}

    # Risk hub: highest betweenness among generative nodes (if any)
    risk_hub = None
    if gen_ids:
        bc = nx.betweenness_centrality(G, normalized=True)
        # pick gen node with max centrality
        risk_hub = max(gen_ids, key=lambda nid: bc.get(nid, 0.0))

    # Anchors: deterministic nodes with degree >= 2 (fan-in/out)
    anchors = []
    for nid in det_ids:
        deg = G.in_degree(nid) + G.out_degree(nid)
        if deg >= 2:
            anchors.append(nid)

    gg_edges = [(a,b) for a,b in G.edges if a in gen_ids and b in gen_ids]
    return {"risk_hub": risk_hub, "anchors": anchors, "gg_edges": gg_edges, "G": G}

def draw_graph(ax, nodes, edges, title, metrics, drivers):
    G = drivers["G"]
    pos = nx.spring_layout(G, seed=42)
    gen_ids = {n["id"] for n in nodes if n["kind"]=="generative"}

    # Base node styling
    node_colors, node_sizes, node_ec = [], [], []
    for nid in G.nodes:
        k = G.nodes[nid]["kind"]
        if k=="generative":
            node_colors.append("#cfe8ff"); node_sizes.append(2200)
        elif k=="aux":
            node_colors.append("#f5f5f5"); node_sizes.append(1800)
        else:
            node_colors.append("#e8e8e8"); node_sizes.append(2000)
        node_ec.append("#444444")

    # Highlight risk hub (amber border)
    if drivers["risk_hub"] and drivers["risk_hub"] in G.nodes:
        idx = list(G.nodes).index(drivers["risk_hub"])
        node_ec[idx] = "#f59e0b"  # amber

    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=node_sizes,
                           linewidths=2.0, edgecolors=node_ec)
    nx.draw_networkx_labels(G, pos, ax=ax,
                            labels={n:G.nodes[n].get("label",n) for n in G.nodes}, font_size=9)

    # Edges (gen→gen in red)
    gg_edges = drivers["gg_edges"]
    other_edges = [(a,b) for a,b in G.edges if (a,b) not in gg_edges]
    nx.draw_networkx_edges(G, pos, ax=ax, edgelist=other_edges, arrows=True,
                           arrowsize=12, width=1.2, edge_color="#666666")
    nx.draw_networkx_edges(G, pos, ax=ax, edgelist=gg_edges, arrows=True,
                           arrowsize=14, width=2.6, edge_color="red")

    # Annotate drivers
    if drivers["risk_hub"]:
        x,y = pos[drivers["risk_hub"]]
        ax.text(x, y+0.08, "risk hub", color="#b45309", fontsize=9, ha="center", weight="bold")
    for aid in drivers["anchors"]:
        if aid in pos:
            x,y = pos[aid]
            ax.text(x, y-0.10, "anchor", color="#16a34a", fontsize=9, ha="center")

    # Footer
    footer = (f"Entropy: {metrics['entropy_score']} ({metrics['entropy_level']}) | "
              f"G={metrics['generative_nodes']} D={metrics['deterministic_nodes']} "
              f"gen→gen={metrics['gen_to_gen_edges']} coupling={metrics['coupling_factor']}")
    ax.set_title(title, fontsize=12)
    ax.text(0.5, -0.10, footer, transform=ax.transAxes, ha="center", fontsize=9)
    ax.axis("off")

def load_json(path): return json.load(open(path))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Side-by-side AgentBound comparison with driver labels")
    ap.add_argument("graphA_json")
    ap.add_argument("graphB_json")
    ap.add_argument("--kindA", help="JSON mapping node_id->kind for A")
    ap.add_argument("--kindB", help="JSON mapping node_id->kind for B")
    ap.add_argument("--out", default="out/compare.png")
    args = ap.parse_args()

    os.makedirs("out", exist_ok=True)

    dataA = load_json(args.graphA_json)
    dataB = load_json(args.graphB_json)
    kindA = json.load(open(args.kindA)) if args.kindA and os.path.exists(args.kindA) else {}
    kindB = json.load(open(args.kindB)) if args.kindB and os.path.exists(args.kindB) else {}

    nodesA, edgesA = build_nodes_edges(dataA, kindA)
    nodesB, edgesB = build_nodes_edges(dataB, kindB)

    metA = compute_entropy(nodesA, edgesA)
    metB = compute_entropy(nodesB, edgesB)

    drvA = find_drivers(nodesA, edgesA)
    drvB = find_drivers(nodesB, edgesB)

    # Δ summary
    def fmt(x): return f"{x:.3f}" if isinstance(x, float) else str(x)
    delta_entropy  = metB["entropy_score"] - metA["entropy_score"]
    delta_coupling = metB["coupling_factor"] - metA["coupling_factor"]
    delta_G = metB["generative_nodes"] - metA["generative_nodes"]
    delta_D = metB["deterministic_nodes"] - metA["deterministic_nodes"]
    delta_text = (f"Δ Entropy: {fmt(delta_entropy)}   |   Δ Coupling: {fmt(delta_coupling)}   |   "
                  f"Δ G: {delta_G}   Δ D: {delta_D}")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15,7))
    draw_graph(ax1, nodesA, edgesA, "Design A — High-entropy Supervisor", metA, drvA)
    draw_graph(ax2, nodesB, edgesB, "Design B — Anchored Supervisor",     metB, drvB)
    fig.suptitle("AgentBound — Pre-hoc Design Comparison (A vs B)\n" + delta_text, fontsize=14)
    plt.tight_layout()
    plt.savefig(args.out, dpi=200)

    print(json.dumps({"A": metA, "B": metB, "delta": {
        "entropy": delta_entropy, "coupling": delta_coupling, "G": delta_G, "D": delta_D
    }}, indent=2))
    print("Saved:", args.out)

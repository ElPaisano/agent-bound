import yaml
import argparse
import networkx as nx
from termcolor import colored

def parse_pipeline_yaml(filepath):
    with open(filepath, "r") as f:
        data = yaml.safe_load(f)
    agents = {node["id"]: node["entropy"] for node in data["agents"]}
    edges = [(edge["from"], edge["to"]) for edge in data["edges"]]
    return agents, edges

def build_entropy_graph(agents, edges):
    G = nx.DiGraph()
    for agent, entropy in agents.items():
        G.add_node(agent, entropy=entropy)
    G.add_edges_from(edges)
    return G

def analyze_entropy(G, budget=None):
    results = []
    for source in G.nodes:
        for target in G.nodes:
            if source != target and nx.has_path(G, source, target):
                path = nx.shortest_path(G, source=source, target=target)
                path_entropy = sum(G.nodes[n]['entropy'] for n in path)
                results.append((path, path_entropy))
    results.sort(key=lambda x: x[1], reverse=True)

    print("\n🔍 Entropy Analysis Report\n")
    for path, entropy in results:
        path_str = " → ".join(path)
        if entropy >= 15:
            flag = colored("🟥 HIGH", "red")
        elif entropy >= 10:
            flag = colored("🟦 MODERATE", "blue")
        else:
            flag = colored("🟩 OK", "green")
        budget_flag = ""
        if budget and entropy > budget:
            budget_flag = colored("⚠️ OVER BUDGET", "yellow")
        print(f"{flag}: Path [{path_str}] has entropy {entropy:.2f} {budget_flag}")
    
    if results:
        max_path, max_entropy = results[0]
        print("\n📊 Summary")
        print(f"Total agents: {len(G.nodes)}")
        print(f"Total paths analyzed: {len(results)}")
        print(f"Max path entropy: {max_entropy:.2f} on path: {' → '.join(max_path)}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AgentBound: Entropy analysis for agentic systems.")
    parser.add_argument("--analyze", type=str, required=True, help="Path to pipeline YAML file")
    parser.add_argument("--budget", type=float, help="Optional entropy budget to flag overages")
    args = parser.parse_args()

    agents, edges = parse_pipeline_yaml(args.analyze)
    G = build_entropy_graph(agents, edges)
    analyze_entropy(G, budget=args.budget)

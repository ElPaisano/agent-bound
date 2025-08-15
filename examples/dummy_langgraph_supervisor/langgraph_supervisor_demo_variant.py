# langgraph_supervisor_demo_variant.py
# Offline: builds a supervisor graph with deterministic anchors,
# then exports JSON + a kind-map that marks 'supervisor' deterministic.

import json, os
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langgraph.graph import StateGraph

# ---- Dummy LLM/tools (no API) ----
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.tools import tool

class DummyLLM(BaseChatModel):
    @property
    def _llm_type(self): return "dummy"
    @property
    def _identifying_params(self): return {}
    def bind_tools(self, tools, **kwargs): return self
    def _generate(self, messages, stop=None, **kwargs) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="(dummy)"))])

dummy_llm = DummyLLM()

@tool
def dummy_retriever(query: str) -> str:
    """Deterministic anchor for docs retrieval."""
    return f"[kb doc ids for: {query}]"

@tool
def schema_validator(payload: str) -> str:
    """Deterministic checker that returns 'OK'/'FAIL'."""
    return "OK"

# Agents
planner_llm = create_react_agent(
    model=dummy_llm,
    tools=[],  # pure planning LLM
    prompt="You are a planner. Break tasks into steps and propose tools.",
    name="planner_llm",
)

worker_llm = create_react_agent(
    model=dummy_llm,
    tools=[],  # pure execution LLM
    prompt="You are a worker. Produce answers from structured inputs.",
    name="worker_llm",
)

# “Supervisor” routes, but we’ll mark it *deterministic* via kind_map later.
supervisor = create_supervisor(
    agents=[planner_llm, worker_llm],  # two LLMs inside graph
    model=dummy_llm,
    prompt=("Route tasks deterministically to planner then worker. "
            "Prefer using retriever + validator anchors."),
).compile()

# Export graph JSON (using to_json for compatibility)
os.makedirs("out", exist_ok=True)
graph = supervisor.get_graph().to_json()

# Build a more anchored flow around supervisor by adding tool nodes into JSON:
# We'll inject extra deterministic nodes (retriever, validator) into edges around planner/worker.
# Minimal tweak: just add them as labeled nodes; edges already imply supervisor<->planner/worker.
nodes = [{"id": n["id"], "label": (n.get("data") or {}).get("name") or n["id"]} for n in graph["nodes"]]
edges = [[e["source"], e["target"]] for e in graph["edges"]]

# Ensure tool nodes exist
tool_nodes = [
    {"id": "retriever", "label": "retriever"},
    {"id": "schema_validator", "label": "schema_validator"},
]
# Add if missing
existing_ids = {n["id"] for n in nodes}
for t in tool_nodes:
    if t["id"] not in existing_ids:
        nodes.append(t)

# Wire planner -> retriever -> worker path (deterministic anchors cut gen→gen coupling)
if ["planner_llm","retriever"] not in edges:
    edges.append(["planner_llm","retriever"])
if ["retriever","worker_llm"] not in edges:
    edges.append(["retriever","worker_llm"])
# Add worker -> validator -> supervisor return path
if ["worker_llm","schema_validator"] not in edges:
    edges.append(["worker_llm","schema_validator"])
if ["schema_validator","supervisor"] not in edges:
    edges.append(["schema_validator","supervisor"])

out_json = "out/langgraph_supervisor_variant.json"
json.dump({"nodes": nodes, "edges": edges}, open(out_json, "w"), indent=2)
print("Exported:", out_json)

# Kind map: mark supervisor deterministic; tools deterministic; LLMs generative.
kind_map = {
    "supervisor": "deterministic",
    "planner_llm": "generative",
    "worker_llm": "generative",
    "retriever": "deterministic",
    "schema_validator": "deterministic",
}
json.dump(kind_map, open("out/kind_map_variant.json", "w"), indent=2)
print("Wrote kind map: out/kind_map_variant.json")

# Offline Supervisor demo: no API keys, no network calls.
# Builds a real LangGraph Supervisor graph using a Dummy LLM and a dummy tool,
# then exports nodes/edges to out/langgraph_supervisor.json.

import json
import os

from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langgraph.graph import StateGraph

# ---- Minimal Dummy LLM that satisfies BaseChatModel ----
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from typing import Iterable, Union
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.tools import BaseTool

class DummyLLM(BaseChatModel):
    """No-op chat model: satisfies LangChain interfaces and never calls external APIs."""

    @property
    def _llm_type(self) -> str:
        return "dummy"

    @property
    def _identifying_params(self) -> dict:
        return {}

    # <-- Add this: create_react_agent calls .bind_tools(...) unconditionally
    def bind_tools(
        self,
        tools: Iterable[Union[BaseTool, type]],
        **kwargs
    ) -> "DummyLLM":
        # No-op: return self so prebuilt agents can be constructed without tool-calling support.
        return self

    def _generate(self, messages, stop=None, **kwargs) -> ChatResult:
        msg = AIMessage(content="(dummy llm response)")
        return ChatResult(generations=[ChatGeneration(message=msg)])

dummy_llm = DummyLLM()

# ---- Dummy tool (no external deps) ----
from langchain_core.tools import tool

@tool
def dummy_search(query: str) -> str:
    """Fake search tool — returns a canned response."""
    return f"[dummy results for: {query}]"

# ---- Build worker agents with the dummy llm/tool ----
research_agent = create_react_agent(
    model=dummy_llm,
    tools=[dummy_search],
    prompt="You are a research agent (dummy). Answer research questions only.",
    name="research_agent",
)

math_agent = create_react_agent(
    model=dummy_llm,
    tools=[],
    prompt="You are a math expert (dummy). Do math tasks only.",
    name="math_agent",
)

# ---- Supervisor routes between agents (also uses DummyLLM) ----
supervisor = create_supervisor(
    agents=[research_agent, math_agent],
    model=dummy_llm,
    prompt=(
        "You are a supervisor managing two agents:\n"
        "- research agent for research tasks\n"
        "- math agent for math tasks\n"
        "Delegate tasks to one agent at a time based on user requests."
    ),
).compile()

# ---- Export the compiled graph (networkx DiGraph) to JSON for AgentBound ----
# ---- Export the compiled graph to JSON (no NetworkX needed) ----
os.makedirs("out", exist_ok=True)

graph_obj = supervisor.get_graph()          # drawable graph wrapper
data = graph_obj.to_json()                  # -> {"nodes":[...], "edges":[...]}

# nodes have "id" and "data" (type/metadata); edges have "source"/"target"
nodes = []
for n in data["nodes"]:
    nid = str(n.get("id"))
    # Try a few reasonable label fields, fallback to id
    label = (
        (n.get("data") or {}).get("name")
        or (n.get("data") or {}).get("label")
        or nid
    )
    nodes.append({"id": nid, "label": str(label)})

edges = [[str(e["source"]), str(e["target"])] for e in data["edges"]]

with open("out/langgraph_supervisor.json", "w") as f:
    json.dump({"nodes": nodes, "edges": edges}, f, indent=2)

print("Exported graph to: out/langgraph_supervisor.json")
print(f"Nodes: {len(nodes)}  Edges: {len(edges)}")

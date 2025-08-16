# Offline Supervisor demo: no API keys, no network calls.
# Builds a simple agent "supervisor" topology using a Dummy LLM and a dummy tool,
# then exports nodes/edges to out/langgraph_supervisor.json for AgentBound.

import json
import os
from typing import Iterable, Union

# LangGraph bits (agents are built but not executed)
from langgraph.prebuilt import create_react_agent

# ---- Minimal Dummy LLM that satisfies BaseChatModel ----
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.tools import BaseTool, tool

class DummyLLM(BaseChatModel):
    """No-op chat model: satisfies LangChain interfaces and never calls external APIs."""

    @property
    def _llm_type(self) -> str:
        return "dummy"

    @property
    def _identifying_params(self) -> dict:
        return {}

    # create_react_agent calls .bind_tools(...) unconditionally
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
@tool
def dummy_search(query: str) -> str:
    """Fake search tool — returns a canned response."""
    return f"[dummy results for: {query}]"

# ---- Build worker agents with the dummy llm/tool (for realism; not invoked here) ----
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

# ---- Define a minimal supervisor topology offline ----
# We do not import or compile a real LangGraph supervisor here.
# AgentBound only needs a {nodes, edges} JSON. We export a simple shape:
# supervisor <-> research_agent, supervisor <-> math_agent

os.makedirs("out", exist_ok=True)

nodes = [
    {"id": "supervisor", "label": "Supervisor"},
    {"id": "research_agent", "label": "Research Agent"},
    {"id": "math_agent", "label": "Math Agent"},
]

edges = [
    ["supervisor", "research_agent"],
    ["supervisor", "math_agent"],
    ["research_agent", "supervisor"],
    ["math_agent", "supervisor"],
]

with open("out/langgraph_supervisor.json", "w") as f:
    json.dump({"nodes": nodes, "edges": edges}, f, indent=2)

print("Exported graph to: out/langgraph_supervisor.json")
print(f"Nodes: {len(nodes)}  Edges: {len(edges)}")

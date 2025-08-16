# langgraph_supervisor_demo_variant.py
# Offline variant: adds deterministic anchors (retriever, schema_validator)
# and marks the supervisor node as deterministic via kind_map.

import json, os
from typing import Iterable, Union

from langgraph.prebuilt import create_react_agent

# ---- Dummy LLM (no API calls) ----
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.tools import BaseTool, tool

class DummyLLM(BaseChatModel):
    @property
    def _llm_type(self): return "dummy"
    @property
    def _identifying_params(self): return {}
    def bind_tools(self, tools: Iterable[Union[BaseTool, type]], **kwargs): return self
    def _generate(self, messages, stop=None, **kwargs) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="(dummy)"))])

dummy_llm = DummyLLM()

# ---- Deterministic tools ----
@tool
def dummy_retriever(query: str) -> str:
    """Deterministic anchor for docs retrieval."""
    return f"[kb doc ids for: {query}]"

@tool
def schema_validator(payload: str) -> str:
    """Deterministic checker that returns 'OK'/'FAIL'."""
    return "OK"

# ---- Two LLM-only worker agents ----
planner_llm = create_react_agent(
    model=dummy_llm,
    tools=[],
    prompt="You are a planner. Break tasks into steps and propose tools.",
    name="planner_llm",
)

worker_llm = create_react_agent(
    model=dummy_llm,
    tools=[],
    prompt="You are a worker. Produce answers from structured inputs.",
    name="worker_llm",
)

# ---- Offline supervisor topology ----
# Unlike the base demo, we hardcode the supervisor node and deterministic anchors.
os.makedirs("out", exist_ok=True)

nodes = [
    {"id": "supervisor", "label": "Supervisor"},
    {"id": "planner_llm", "label": "Planner LLM"},
    {"id": "worker_llm", "label": "Worker LLM"},
    {"id": "retriever", "label": "Retriever"},
    {"id": "schema_validator", "label": "Schema Validator"},
]

edges = [
    ["supervisor", "planner_llm"],
    ["planner_llm", "retriever"],
    ["retriever", "worker_llm"],
    ["worker_llm", "schema_validator"],
    ["schema_validator", "supervisor"],
]

out_json = "out/langgraph_supervisor_variant.json"
with open(out_json, "w") as f:
    json.dump({"nodes": nodes, "edges": edges}, f, indent=2)

print("Exported:", out_json)

# ---- Kind map: deterministic vs generative ----
kind_map = {
    "supervisor": "deterministic",
    "planner_llm": "generative",
    "worker_llm": "generative",
    "retriever": "deterministic",
    "schema_validator": "deterministic",
}

with open("out/kind_map_variant.json", "w") as f:
    json.dump(kind_map, f, indent=2)

print("Wrote kind map: out/kind_map_variant.json")

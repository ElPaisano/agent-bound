# Dummy LangGraph Supervisor

The following example demonstrates how AgentBound analyzes and compares two versions of the same multi-agent architecture (`langgraph_supervisor_demo.py` and `python langgraph_supervisor_demo_variant.py`) based on [LangGraph’s Supervisor pattern](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/). You’ll generate two pipeline graphs (`langgraph_supervisor.json` and `langgraph_supervisor_variant.json`), run design-time analysis on each using `agentbound.py`, and compare them side by side using `agentbound_compare.py`.

### Purpose of demo
This workflow shows how AgentBound can highlight structural differences between two designs (e.g. changes in complexity, potential stability risks, missing validation steps), all before the agentic system actually runs in production. It’s an example of how you can quickly assess the impact of architectural changes during the design phase.

### Expected output
- Individual reports and diagrams for each pipeline, showing metrics like agentic entropy, number of nodes, and risky patterns.
- A comparison diagram that visually contrasts the two architectures.
- JSON reports with detailed metrics you can integrate into your design review process.

## 1. Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r ../../requirements.txt
```

## 2. Generate pipeline graphs 

If you want to regenerate A/B JSON located in `\out`, run the following commands to create `langgraph_supervisor.json` and `langgraph_supervisor_variant.json`.

```bash
python langgraph_supervisor_demo.py
python langgraph_supervisor_demo_variant.py
```

## 3. Analyze each graph

```bash
python ../../agentbound.py langgraph_supervisor.json
python ../../agentbound.py langgraph_supervisor_variant.json
```

## 4. Compare A and B

```bash
python ../../agentbound_compare.py langgraph_supervisor.json langgraph_supervisor_variant.json
```

## 5. View the outputs
Outputs are located in ./out/.

```bash
- langgraph_supervisor.png 
- langgraph_supervisor_report.json
- langgraph_supervisor_variant.png 
- langgraph_supervisor_variant_report.json
- compare.png
```

For a detailed description of how to interpret the results, see [the Interpret AgentBound output section in the README](../../README.md#interpret-agentbound-output).
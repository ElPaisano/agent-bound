# AgentBound 

This is a minimal proof-of-concept for **AgentBound**, an **agentic entropy** analyzer for agentic AI systems.

It reads a YAML-defined agent pipeline and computes path-level entropy across the graph, flagging high-entropy or risky branches before you deploy.

---

## Theory 

For a deep-dive into the theory of **agentic entropy** and its applications, see [/docs/theory.md](/docs/theory.md).

If you just want a short explanation of why the idea is practically useful, see the [Explain it to me like I'm 5 doc](/docs/eitmli5.md).

## 🔧 What It Does

- Analyzes agent graphs (e.g., LLM → tool → LLM)
- Computes entropy across all valid paths
- Flags high-entropy or over-budget paths
- Prints a summary report with entropy classification

---

## 📦 Requirements

Install dependencies:

```bash
pip install pyyaml networkx termcolor
```

## Sample `pipeline.yaml` 

```
agents:
  - id: Planner
    entropy: 7.5
  - id: Retriever
    entropy: 0.5
  - id: Generator
    entropy: 7.5
  - id: Validator
    entropy: 0.0
  - id: Rewriter
    entropy: 6.0

edges:
  - from: Planner
    to: Retriever
  - from: Retriever
    to: Generator
  - from: Generator
    to: Validator
  - from: Validator
    to: Rewriter
```

## 🚀 How to Run

Run entropy analysis:

```bash
python agentbound.py --analyze pipeline.yaml
```

Optional: flag paths exceeding a given entropy budget:

```bash
python agentbound.py --analyze pipeline.yaml --budget 15.0
```

## Sample Output

```
🔍 Entropy Analysis Report

🟥 HIGH: Path [Planner → Retriever → Generator → Validator → Rewriter] has entropy 21.50 ⚠️ OVER BUDGET
🟦 MODERATE: Path [Retriever → Generator → Validator → Rewriter] has entropy 14.00
🟩 OK: Path [Validator → Rewriter] has entropy 6.00

📊 Summary
Total agents: 5
Total paths analyzed: 10
Max path entropy: 21.50 on path: Planner → Retriever → Generator → Validator → Rewriter
```

## What’s Next

- Graph visualizations
- Entropy diffing between versions
- Runtime feedback or modulator agent
- plugin(s) for popular agentic frameworks

# Changelog

All notable changes to this project will be documented in this file.  
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),  
and this project adheres to [Semantic Versioning](https://semver.org/).

---
## [Unreleased]
### Added
- Placeholder
### Changed
- Placeholder
### Fixed
- Placeholder

---

## [v0.2.0] - 2025-09-01
### Added
- **Customer Support Workflow demo** (`examples/customer_support_agent/`), including:
  - Three variants (A = Baseline, B = Doc Filter, C = Post-Summarizer Validator)
  - Input graphs + kind maps under `/inputs/`
  - Reference outputs (JSON reports + PNGs) under `/artifacts/`
  - `HOW_TO_RUN.md` walkthrough with metrics and interpretation
- Optional CLI argument to `agentbound.py` for **custom output location**  
  (defaults to `./out/`, can be overridden to any path)

### Changed
- **README.md**: 
    - Surfaced both demos in Quickstart and intro section  (Customer Support Workflow + Dummy LangGraph Supervisor)
    - Document optional custom output location 
- **agentbound.py**:
  - Normalized empty-string args (`""` → treated as `None`)
  - Added warnings for mismatched `kind_map` IDs  
  - Slight refactor for cleaner node-kind inference and reporting
- Updated `.gitignore` to ignore all nested `out/` folders (`**/out/`), so demo run outputs don’t show up as untracked
- Updated `.gitignore` to exclude all nested `out/` folders, preventing demo run outputs from appearing as untracked files


### Fixed
- Kind map application now consistently respects node IDs,  
  preventing generative nodes from being misclassified as deterministic

---

## [v0.1.0] - 2025-08-18
### Added
- Validation harness (`validation/`) with simulation experiments  
- CI-like summaries and plots for entropy vs brittleness  
- Updated README with validation results section

---

## [v0.0.1] - 2025-08-16
### Added
- Initial project scaffolding  
- Core AgentBound static analysis (entropy scoring)  
- Example: Dummy LangGraph Supervisor demo

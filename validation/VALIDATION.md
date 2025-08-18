# Validation

This directory contains simulation and analysis artifacts for AgentBound.

## Workflow

1. **Run the harness**  
   Simulates multiple graph variants with retries/loops/etc. 
    
   ```bash
   ./run_harness.py --graphs graphs/ --results validation/results
   ```

2. **Merge with entropy metrics**
   Computes AgentBound entropy scores and risk levels, merges with harness brittleness metrics.

   ```bash
   ./compute_entropy.py --graphs graphs/ --results validation/results
   ```

3. **Plot**
   Generates visualizations of entropy vs failure rate with confidence intervals.

   ```bash
   ./plot_entropy_vs_failure.py --results validation/results/summary/all_results.json
   ```

## Outputs

* `results/` — raw simulation outputs (ignored by git).
* `results/summary/` — tracked JSON summaries and plots.

  * `ALL.summaries.json`: harness brittleness metrics
  * `all_results.json`: merged brittleness + entropy metrics
  * figures (`*.png`): entropy vs failure rate plots

## Notes

* `.gitignore` ensures raw run artifacts are ignored.
* Only summaries and plots are tracked for reproducibility.
* This pipeline = **simulate → compute → visualize**.

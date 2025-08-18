#!/usr/bin/env python3
import argparse, json, math, fnmatch, re
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

DATA = Path("validation/results/summary/all_results.json")
DEFAULT_OUT = Path("validation/results/summary/entropy_vs_brittleness.png")
DEFAULT_CFG = Path("validation/config/families.json")
LETTER_RE = re.compile(r"^([A-Z])[_-]")  # matches A_, B-, etc.

def mean(xs): return sum(xs)/len(xs)
def std(xs):
    m = mean(xs); n = max(1, len(xs)-1)
    return (sum((t-m)**2 for t in xs)/n) ** 0.5

def ranks(vals):
    pairs = sorted((v,i) for i,v in enumerate(vals))
    r = [0]*len(vals); i = 0
    while i < len(pairs):
        j = i
        while j+1 < len(pairs) and pairs[j+1][0] == pairs[i][0]:
            j += 1
        avg = (i + j)/2 + 1
        for k in range(i, j+1): r[pairs[k][1]] = avg
        i = j+1
    return r

def load_family_map(cfg_path: Path):
    if cfg_path.exists():
        return json.loads(cfg_path.read_text())
    return None  # No config -> per-graph legend

def family_for(name: str, fam_map: dict | None):
    if not fam_map:
        return None
    for fam, patterns in fam_map.items():
        for pat in patterns:
            if any(ch in pat for ch in "*?[]"):
                if fnmatch.fnmatch(name, pat): return fam
            else:
                if name.startswith(pat): return fam
    return "other"

def letter_prefix(name: str) -> str:
    m = LETTER_RE.match(name)
    return m.group(1) if m else "?"

def build_letter_map(names, fams):
    grouped = {}
    flat = []
    for n, f in zip(names, fams):
        L = letter_prefix(n)
        key = f or "variant"
        grouped.setdefault(key, []).append(f"{L}: {n}")
        flat.append((L, n))
    for k in grouped: grouped[k].sort()
    flat.sort()
    return grouped, flat

def proxy_marker(color):
    return Line2D([0], [0], marker='o', color='none', markerfacecolor=color, markersize=8)

def handle_color_from_artist(h):
    """Works for scatter PathCollection and errorbar ErrorbarContainer."""
    try:
        # PathCollection (scatter)
        return h.get_facecolor()[0]
    except Exception:
        try:
            # ErrorbarContainer
            return h.lines[0].get_color()
        except Exception:
            return "black"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CFG),
                    help="Path to families.json (prefix or glob patterns). If missing, per-graph legend is used.")
    ap.add_argument("--out", default=str(DEFAULT_OUT),
                    help="Output PNG path.")
    ap.add_argument("--hide-letters", action="store_true",
                    help="Do not draw letter tags near points.")
    ap.add_argument("--figsize", default="13,6.5",
                    help="Figure size WxH in inches, e.g. 13,6.5")
    ap.add_argument("--y", choices=["brittleness_index","failure_rate"], default="brittleness_index",
                    help="Which metric to plot on the y-axis.")
    ap.add_argument("--with-ci", action="store_true",
                    help="If --y=failure_rate, draw 95% CI error bars (Wilson).")
    args = ap.parse_args()

    # load data FIRST
    data = json.loads(DATA.read_text())
    if not data:
        raise SystemExit("No data found in all_results.json")

    W, H = (float(s) for s in args.figsize.split(","))

    names = [d["graph"] for d in data]
    X = [d["entropy_score"] for d in data]

    # choose y-series
    if args.y == "failure_rate":
        Yvals = [d["failure_rate"] for d in data]
        Yerr_low, Yerr_high = [], []
        if args.with_ci:
            for d in data:
                lo, hi = d.get("failure_rate_ci95", [None, None])
                if lo is None or hi is None:
                    Yerr_low.append(0.0); Yerr_high.append(0.0)
                else:
                    y = d["failure_rate"]
                    Yerr_low.append(max(0.0, y - lo))
                    Yerr_high.append(max(0.0, hi - y))
    else:
        Yvals = [d["brittleness_index"] for d in data]

    fam_map = load_family_map(Path(args.config))
    fams = [family_for(n, fam_map) for n in names]

    # correlations/regression use the chosen Y series
    mx, my = mean(X), mean(Yvals); sx, sy = std(X), std(Yvals)
    cov = sum((x-mx)*(y-my) for x,y in zip(X,Yvals)) / max(1, len(X)-1)
    pearson = cov / (sx*sy) if sx>0 and sy>0 else float("nan")
    rx, ry = ranks(X), ranks(Yvals)
    mrx, mry = mean(rx), mean(ry)
    srx = std(rx); sry = std(ry)
    covr = sum((a-mrx)*(b-mry) for a,b in zip(rx,ry)) / max(1, len(rx)-1)
    spearman = covr / (srx*sry) if srx>0 and sry>0 else float("nan")

    b = cov / (sx*sx) if sx>0 else 0.0
    a = my - b*mx

    print("Points:")
    for n,x,y in zip(names,X,Yvals):
        print(f"  {n:>20s}  entropy={x:.3f}  y={y:.3f}")
    print(f"\nPearson r = {pearson:.3f}")
    print(f"Spearman rho = {spearman:.3f}")
    print(f"Fit: y = {a:.3f} + {b:.3f} x")

    # --- layout: 3 columns: left legend | center plot | right mapping ---
    fig = plt.figure(figsize=(W, H), constrained_layout=True)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 3.0, 1.2])
    ax_left  = fig.add_subplot(gs[0,0]); ax_left.axis("off")
    ax_plot  = fig.add_subplot(gs[0,1])
    ax_right = fig.add_subplot(gs[0,2]); ax_right.axis("off")

    # scatter (color by family or per-graph if no config)
    scatter_handles = {}
    if fam_map:
        fam_to_pts = {}
        for idx,(n,f,x,y) in enumerate(zip(names,fams,X,Yvals)):
            fam_to_pts.setdefault(f, []).append((x,y,idx))
        for fam, pts in fam_to_pts.items():
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            if args.y == "failure_rate" and args.with_ci:
                el = [Yerr_low[i] for _,_,i in pts]
                eh = [Yerr_high[i] for _,_,i in pts]
                h = ax_plot.errorbar(xs, ys, yerr=[el, eh], fmt='o', capsize=3, label=fam)
            else:
                h = ax_plot.scatter(xs, ys, s=50, label=fam)
            scatter_handles[fam] = h
    else:
        for i,(n,x,y) in enumerate(zip(names,X,Yvals)):
            if args.y == "failure_rate" and args.with_ci:
                h = ax_plot.errorbar([x],[y], yerr=[[Yerr_low[i]],[Yerr_high[i]]], fmt='o', capsize=3, label=n)
            else:
                h = ax_plot.scatter([x],[y], s=50, label=n)

    # letter tags at points
    if not args.hide_letters:
        for n,x,y in zip(names,X,Yvals):
            L = letter_prefix(n)
            ax_plot.annotate(L, (x,y), xytext=(4,4), textcoords="offset points", fontsize=9, weight="bold")

    # regression line
    xmin, xmax = min(X), max(X)
    ax_plot.plot([xmin, xmax], [a + b*xmin, a + b*xmax])

    ylabel = "Brittleness index" if args.y=="brittleness_index" else "Failure rate"
    title_suffix = "" if args.y=="brittleness_index" else " (with 95% CIs)" if args.with_ci else ""
    ax_plot.set_xlabel("AgentBound entropy score")
    ax_plot.set_ylabel(ylabel)
    ax_plot.set_title(f"Entropy vs {ylabel}{title_suffix}")

    # --- left sidebar: family legend ---
    if fam_map:
        fam_order = list(scatter_handles.keys())
        colors = [handle_color_from_artist(scatter_handles[f]) for f in fam_order]
        proxies = [proxy_marker(c) for c in colors]
        ax_left.legend(proxies, fam_order, title="family", loc="upper left", frameon=True)

    # --- right sidebar: letter -> name mapping, grouped by family ---
    grouped, flat = build_letter_map(names, fams)
    order = ["control","loop","chain","fork","other","variant"]
    lines = []
    for fam in order:
        if fam in grouped:
            lines.append(f"{fam}:")
            lines.extend([f"  {line}" for line in grouped[fam]])
    if not lines:
        lines = [f"{L}: {n}" for (L,n) in flat]
    mapping_text = "\n".join(lines)
    ax_right.text(0.02, 0.98, mapping_text, transform=ax_right.transAxes,
                  va="top", ha="left", fontsize=9,
                  bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="0.8"))

    fig.savefig(Path(args.out), dpi=200)
    print(f"Saved plot -> {args.out}")

if __name__ == "__main__":
    main()

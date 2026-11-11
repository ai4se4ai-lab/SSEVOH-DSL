#!/usr/bin/env python3
"""Regenerate the evaluation figures of the TSE manuscript from raw records.

Usage (from the repository root):
    python3 docs/TSE/figures/make_figures.py

Inputs are the committed raw cohorts; nothing is re-run or re-sampled.
Outputs: docs/TSE/figures/enforcement.pdf and docs/TSE/figures/cost.pdf
"""
import collections
import csv
import json
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[3]
RES = ROOT / "artifacts" / "benchmark-results"
OUT = Path(__file__).resolve().parent

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Nimbus Sans", "Helvetica", "Arial", "Liberation Sans", "DejaVu Sans"],
    "mathtext.fontset": "custom", "mathtext.rm": "Nimbus Sans", "mathtext.it": "Nimbus Sans:italic",
    "font.size": 7.5,
    "axes.titlesize": 8,
    "axes.labelsize": 7.5,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 6.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.6,
    "pdf.fonttype": 42,
})
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#d9d8d4"
GOOD, BAD, NEUTRAL, NA = "#cfe8cf", "#e34948", "#f1f0ec", "#ffffff"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # validated categorical slots 1-3


def load(path):
    with open(path) as handle:
        return [json.loads(line) for line in handle]


# ---------------------------------------------------------------- Figure: enforcement
FAMILIES = [  # (scenario id, label, permitted?)
    ("legitimate_script", "Script correction", True),
    ("legitimate_multifile", "Multifile correction", True),
    ("legitimate_skill", "Skill addition", True),
    ("protected_guardrails", "Protected guardrails", False),
    ("permission_expansion", "Permission expansion", False),
    ("unauthorized_principal", "Unauthorized principal", False),
    ("protected_verifier", "Protected verifier", False),
    ("dependency_conflict", "Missing dependency", False),
    ("invalid_python", "Invalid Python", False),
    ("missing_required_evidence", "Missing evidence", False),
    ("outside_executable_catalog", "Outside exec. catalog", False),
    ("missing_required_script", "Missing required script", False),
    ("withdrawal_provenance", "Withdrawn origin (L)", False),
    ("rollback_conflict", "Rollback conflict (L)", False),
    ("stale_approval", "Stale approval (L)", False),
    ("interrupted_publication", "Interrupted publish (L)", False),
]
COLUMNS = [("C0", "C0\norig."), ("C1", "C1\ntests"), ("C2", "C2\nstatic"), ("C3", "C3\nfull"),
           ("permissions", "$-$Perm"), ("dependencies", "$-$Dep"), ("provenance", "$-$Prov"),
           ("evidence", "$-$Evid"), ("formal_verification", "$-$FV"), ("withdrawal", "$-$Wdr"),
           ("rollback", "$-$Rb"), ("revalidation", "$-$Reval")]


def controlled_matrix():
    cells = collections.defaultdict(lambda: [0, 0])
    for r in load(RES / "harness2-full" / "controlled.jsonl"):
        col = r["condition"] if r["ablation"] == "full" else r["ablation"]
        hit = (r["accepted"] and not r["false_reject"]) if r["oracle_allowed"] else r["unsafe_deployed"]
        cells[(r["scenario"], col)][0] += bool(hit)
        cells[(r["scenario"], col)][1] += 1
    return cells


def model_outcomes():
    """Primary DSL cohort (100 responses/model): protocol failure, parse failure, allowed, disallowed."""
    rows = collections.defaultdict(collections.Counter)
    for r in load(RES / "full-campaign" / "records.jsonl"):
        c = rows[r["model"]]
        if r["oracle_safe"] is True:
            c["allowed"] += 1
        elif r["oracle_safe"] is False:
            c["disallowed"] += 1
        elif r["syntax_valid"]:
            c["parse"] += 1
        else:
            c["protocol"] += 1
    return rows


def enforcement_figure():
    cells = controlled_matrix()
    fig = plt.figure(figsize=(7.16, 3.05))
    ax = fig.add_axes([0.125, 0.10, 0.47, 0.76])
    nrow, ncol = len(FAMILIES), len(COLUMNS)
    for i, (sid, _, permitted) in enumerate(FAMILIES):
        for j, (col, _) in enumerate(COLUMNS):
            x0 = j + (0.25 if j >= 4 else 0)
            if (sid, col) not in cells:
                ax.add_patch(plt.Rectangle((x0, i), 0.94, 0.9, fc=NA, ec=GRID, lw=0.5, hatch="////"))
                continue
            k, n = cells[(sid, col)]
            if permitted:
                fc, tc = (GOOD, INK) if k == n else (BAD, "white")
            else:
                fc, tc = (NEUTRAL, MUTED) if k == 0 else (BAD, "white")
            ax.add_patch(plt.Rectangle((x0, i), 0.94, 0.9, fc=fc, ec="white", lw=0.8))
            ax.text(x0 + 0.47, i + 0.47, f"{k}/{n}", ha="center", va="center", fontsize=5.6,
                    color=tc, fontweight="bold" if fc == BAD else "normal")
    ax.set_xlim(-0.05, ncol + 0.3)
    ax.set_ylim(nrow + 0.05, -0.1)
    ax.set_yticks([i + 0.45 for i in range(nrow)])
    ax.set_yticklabels([f[1] for f in FAMILIES], fontsize=6.4)
    ax.set_xticks([j + 0.47 + (0.25 if j >= 4 else 0) for j in range(ncol)])
    ax.set_xticklabels([c[1] for c in COLUMNS], fontsize=5.8)
    ax.xaxis.tick_top()
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    for y in (2.95, 11.95):
        ax.axhline(y, color=MUTED, lw=0.6)
    ax.text(2.0, -2.15, "Comparison conditions", ha="center", fontsize=6.6, color=MUTED)
    ax.text(8.25, -2.15, "C3 with one gate removed", ha="center", fontsize=6.6, color=MUTED)
    fig.text(0.01, 1.02, "(a) Controlled Harness$^2$ fixtures (5 repeats per cell)",
             fontsize=7.8, fontweight="semibold")
    handles = [Patch(fc=GOOD, ec=GRID, label="Permitted, retained"),
               Patch(fc=NEUTRAL, ec=GRID, label="Disallowed, blocked"),
               Patch(fc=BAD, ec=GRID, label="Error (deployed or rejected)"),
               Patch(fc=NA, ec=GRID, hatch="////", label="No equivalent API")]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.005, -0.012), ncol=4, frameon=False,
               handlelength=1.2, columnspacing=0.9)

    # (b) model-generated outcomes
    rows = model_outcomes()
    order = [("qwen2.5-coder:7b", "Qwen2.5-C 7B"), ("phi4:14b", "Phi-4 14B"), ("gpt-oss:20b", "GPT-OSS 20B"),
             ("devstral:24b", "Devstral 24B"), ("qwen3-coder:30b", "Qwen3-C 30B")]
    cats = [("protocol", "Protocol failure", "#bdbcb6"), ("parse", "Parse failure", "#8e8d88"),
            ("allowed", "Allowed $\\rightarrow$ admitted", SERIES[2]),
            ("disallowed", "Disallowed $\\rightarrow$ blocked", SERIES[0])]
    bx = fig.add_axes([0.735, 0.24, 0.25, 0.62])
    for y, (m, _) in enumerate(order):
        left = 0
        for key, _, color in cats:
            v = rows[m][key]
            if v:
                bx.barh(y, v, left=left, height=0.62, color=color, edgecolor="white", linewidth=0.8)
                if v >= 9:
                    bx.text(left + v / 2, y, str(v), ha="center", va="center", fontsize=6,
                            color="white" if key in ("disallowed", "parse") else INK)
                left += v
    bx.set_yticks(range(len(order)))
    bx.set_yticklabels([o[1] for o in order])
    bx.invert_yaxis()
    bx.set_xlim(0, 100)
    bx.set_xlabel("Responses (of 100 per model)")
    bx.tick_params(axis="y", length=0)
    bx.grid(axis="x", color=GRID, lw=0.5)
    bx.set_axisbelow(True)
    fig.text(0.64, 1.02, "(b) Model-generated DSL requests (N = 500)", fontsize=7.8, fontweight="semibold")
    bx.legend(handles=[Patch(fc=c, label=l) for _, l, c in cats], loc="upper center",
              bbox_to_anchor=(0.42, -0.2), ncol=2, frameon=False, handlelength=1.0, columnspacing=0.8)
    fig.savefig(OUT / "enforcement.pdf", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


# ---------------------------------------------------------------- Figure: cost
def _style(ax, title):
    ax.set_title(title, loc="left", fontsize=7.8, fontweight="semibold", pad=6)
    ax.grid(color=GRID, lw=0.5)
    ax.set_axisbelow(True)


def cost_figure():
    rows = list(csv.DictReader(open(RES / "full-campaign" / "analysis" / "scaling.csv")))
    shapes = [("star", SERIES[0], "o"), ("random", SERIES[1], "s"), ("chain", SERIES[2], "^")]
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(7.16, 1.85), gridspec_kw={"wspace": 0.38})
    for shape, color, marker in shapes:
        pts = sorted((int(r["components"]), float(r["median_seconds"])) for r in rows
                     if r["shape"] == shape and r["contenders"] == "1")
        a.plot([p[0] for p in pts], [p[1] for p in pts], color=color, marker=marker, ms=4.5, lw=2,
               mec="white", mew=0.8, label=f"{shape} graph")
        a.annotate(f"{pts[-1][1]:.2f} s", pts[-1], xytext=(5, {"chain": 4, "random": 0, "star": -5}[shape]), textcoords="offset points",
                   va="center", fontsize=6.3, color=MUTED)
        pts = sorted((int(r["contenders"]), float(r["median_seconds"])) for r in rows
                     if r["shape"] == shape and r["components"] == "500")
        b.plot([p[0] for p in pts], [p[1] for p in pts], color=color, marker=marker, ms=4.5, lw=2,
               mec="white", mew=0.8)
        b.annotate(f"{pts[-1][1]:.1f}", pts[-1], xytext=(4, 0), textcoords="offset points",
                   va="center", fontsize=6.3, color=MUTED)
    a.set_xscale("log"); a.set_yscale("log")
    a.set_xticks([10, 100, 500]); a.set_xticklabels(["10", "100", "500"]); a.minorticks_off()
    a.set_yticks([0.01, 0.1, 1]); a.set_yticklabels(["0.01", "0.1", "1"])
    a.set_xlim(7, 1100)
    a.set_xlabel("Components in harness graph"); a.set_ylabel("Median transition time (s)")
    _style(a, "(a) Graph size (1 approval)")
    b.set_xticks([1, 2, 4, 8]); b.set_xlim(0.5, 9.3); b.set_ylim(0, 6.6)
    b.set_xlabel("Conflicting approvals (500 components)"); b.set_ylabel("Median total time (s)")
    _style(b, "(b) Contention (1 winner each)")

    aux = [r for r in load(RES / "full-campaign" / "auxiliary.jsonl") if r.get("benchmark")]
    levels = ["B0", "B1", "B2", "B3"]
    med = [1000 * statistics.median(r["seconds"] for r in aux if r["baseline"] == k) for k in levels]
    fa = [sum(bool(r["false_accept"]) for r in aux if r["baseline"] == k) for k in levels]
    c.plot(range(4), med, color=INK, marker="o", ms=4.5, lw=2, mec="white", mew=0.8)
    c.scatter([3], [med[3]], s=34, color=SERIES[0], zorder=3, edgecolor="white", linewidth=0.8)
    for i, (m, f) in enumerate(zip(med, fa)):
        c.annotate(f"{f}/60\nleaked", (i, m), xytext=(0, 7 if i == 3 else -9), textcoords="offset points",
                   ha="center", va="bottom" if i == 3 else "top", fontsize=6.2,
                   color=SERIES[0] if i == 3 else BAD, fontweight="semibold")
    c.set_xticks(range(4)); c.set_xticklabels(["B0\nsyntax", "B1\n+schema", "B2\n+policy", "B3\nfull"])
    c.set_xlim(-0.45, 3.45); c.set_ylim(0, 0.9)
    c.set_xlabel("Cumulative admission checks"); c.set_ylabel("Median admission time (ms)")
    _style(c, "(c) Price of each check level")
    fig.legend(*a.get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(0.36, 1.1), ncol=3,
               frameon=False, handlelength=2.2, columnspacing=1.6)
    fig.savefig(OUT / "cost.pdf", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


# ---------------------------------------------------------------- Figure: ToolRepair-12
# Natural unsafe proposals executed under the corrected label (experiments/toolrepair/DEVIATIONS.md, D1;
# computed by experiments/toolrepair/relabel_corrected.py over the per-stream archives).
CORRECTED_NATURAL = {"original": 298, "catalog": 0, "sandboxed_evidence": 0}
ARMS = [("original", "A1 original"), ("catalog", "A2 catalog"), ("sandboxed_evidence", "A3 sandboxed evidence")]


def toolrepair_figure():
    s = json.load(open(RES / "toolrepair-v1" / "analysis" / "summary.json"))
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(7.16, 1.75), gridspec_kw={"wspace": 0.55, "width_ratios": [1.45, 1, 0.9]})

    models = [("phi4:14b", "Phi-4\n14B"), ("qwen2.5-coder:7b", "Qwen2.5\n7B"), ("qwen3-coder:30b", "Qwen3\n30B"),
              ("devstral:24b", "Devstral\n24B"), ("gpt-oss:20b", "GPT-OSS\n20B")]
    w = 0.26
    for j, (arm, label) in enumerate(ARMS):
        vals = []
        for m, _ in models:
            k, n = s["per_model_success"][f"{m}|{arm}"].split("/")
            vals.append(int(k) / int(n))
        a.bar([i + (j - 1) * w for i in range(len(models))], vals, width=w - 0.03, color=SERIES[j], label=label)
    a.annotate("no\noutput", (4, 0), xytext=(0, 3), textcoords="offset points", ha="center",
               va="bottom", fontsize=6.0, color=MUTED)
    a.set_xticks(range(len(models))); a.set_xticklabels([l for _, l in models], fontsize=5.8, linespacing=0.95)
    a.set_ylim(0, 0.5); a.set_ylabel("Strict task success")
    _style(a, "(a) Success by model and arm")
    a.grid(axis="x", visible=False)

    fams = sorted(s["H3_noninferiority_A3_vs_A1"]["per_family"].items(), key=lambda kv: kv[1])
    ys = range(len(fams))
    b.axvline(0, color=MUTED, lw=0.6)
    b.axvline(-0.10, color=BAD, lw=1, ls=(0, (3, 2)))
    b.scatter([v for _, v in fams], ys, s=14, color=SERIES[2], edgecolor="white", linewidth=0.6, zorder=3)
    est, (lo, hi) = s["H3_noninferiority_A3_vs_A1"]["estimate"], s["H3_noninferiority_A3_vs_A1"]["ci95"]
    yp = len(fams) + 0.8
    b.plot([lo, hi], [yp, yp], color=INK, lw=2, solid_capstyle="round")
    b.scatter([est], [yp], s=22, color=INK, edgecolor="white", linewidth=0.6, zorder=3)
    b.set_yticks(list(ys) + [yp])
    b.set_yticklabels([f.replace("_", " ") for f, _ in fams] + ["pooled (95% CI)"], fontsize=5.6)
    b.text(-0.105, len(fams) - 0.1, "margin", color=BAD, fontsize=6, ha="right", va="center")
    b.set_xlim(-0.3, 0.12); b.set_ylim(-0.8, yp + 0.8)
    b.set_xlabel("Success difference A3 $-$ A1")
    _style(b, "(b) Non-inferiority by family")
    b.grid(axis="y", visible=False)

    h2 = s["H2_safety"]
    for j, (arm, label) in enumerate(ARMS):
        nat, inj, n = CORRECTED_NATURAL[arm], h2[arm]["injected_executed"], h2[arm]["injected_n"]
        y = 2 - j
        c.barh(y + 0.18, nat, height=0.32, color=SERIES[j])
        c.barh(y - 0.18, inj, height=0.32, color=SERIES[j], hatch="////", edgecolor="white", linewidth=0)
        c.text(nat + 6, y + 0.18, f"{nat} natural", va="center", fontsize=6.2, color=INK)
        c.text(inj + 6, y - 0.18, f"{inj}/{n} injected", va="center", fontsize=6.2, color=INK)
    c.set_yticks([2, 1, 0]); c.set_yticklabels(["A1", "A2", "A3"])
    c.set_xlim(0, 470); c.set_xlabel("Violating proposals executed")
    _style(c, "(c) Executed contract violations")
    c.grid(axis="y", visible=False)

    fig.legend(*a.get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(0.5, 1.1), ncol=3,
               frameon=False, handlelength=1.2, columnspacing=1.6)
    fig.savefig(OUT / "toolrepair.pdf", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


if __name__ == "__main__":
    enforcement_figure()
    cost_figure()
    toolrepair_figure()
    print("wrote", OUT / "enforcement.pdf", OUT / "cost.pdf", OUT / "toolrepair.pdf")

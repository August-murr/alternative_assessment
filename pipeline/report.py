"""Build the per-checkpoint reports, progress table, cost charts and run summary.

    python -m pipeline.report runs/<id> [--publish]

Reads run.json and checkpoints/cp_*/checkpoint.json (written by pipeline.run), writes
checkpoints/cp_*/CHECKPOINT_REPORT.md, progress.csv, cost_curve.png and SUMMARY.md.
--publish copies the reviewer-relevant files into results/<run-name>/ (runs/ is gitignored).
"""

import argparse
import csv
import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from pipeline.config import ROOT  # noqa: E402

# Reference palette (light mode), validated with the dataviz skill's validate_palette.js.
SURFACE, TEXT, TEXT_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]


def load(run_dir: Path) -> tuple[dict, list[dict]]:
    run = json.loads((run_dir / "run.json").read_text())
    cps = [json.loads(p.read_text()) for p in run_dir.glob("checkpoints/cp_*/checkpoint.json")]
    return run, sorted(cps, key=lambda c: c["k"])


def _test(cp: dict) -> dict:
    return ((cp.get("eval") or {}).get("test_scores")) or {}


def _val(cp: dict) -> dict:
    return (cp.get("validation") or {}).get("scores") or {}


def _delta(cur: float | None, prev: float | None, higher_is_better: bool = True) -> str:
    if cur is None or prev is None:
        return ""
    d = cur - prev
    if abs(d) < 5e-5:
        return " (= no change)"
    better = d > 0 if higher_is_better else d < 0
    return f" ({'▲' if d > 0 else '▼'} {d:+.4f}, {'better' if better else 'worse'})"


def progress_rows(cps: list[dict]) -> list[dict]:
    rows, cum = [], 0.0
    for cp in cps:
        cum += cp["total_cost"]
        t, v = _test(cp), _val(cp)
        rows.append({
            "checkpoint": cp["k"], "status": cp["status"], "fix_attempts": cp["fix_attempts"], "change": cp["change"],
            "val_pr_auc": v.get("pr_auc"), "test_pr_auc": t.get("pr_auc"), "test_roc_auc": t.get("roc_auc"),
            "test_brier": t.get("brier"), "api_cost": round(cp["api_cost"], 4),
            "modal_agent_cost": round(cp["modal_agent_cost"], 4), "modal_eval_cost": round(cp["modal_eval_cost"], 4),
            "total_cost": round(cp["total_cost"], 4), "cumulative_cost": round(cum, 4),
            "agent_minutes": round(cp["agent_seconds"] / 60, 1),
            "tool_calls": sum(c["tool_calls"] for c in cp["calls"]),
            "lines_added": cp["diff"]["lines_added"], "lines_removed": cp["diff"]["lines_removed"],
        })
    return rows


def checkpoint_report(cp: dict, prev: dict | None, row: dict, positive_rate: float | None) -> str:
    t, v = _test(cp), _val(cp)
    pt, pv = (_test(prev), _val(prev)) if prev else ({}, {})
    agent_md = Path(cp["_dir"]) / "submission" / "CHECKPOINT.md"
    lines = [
        f"# Checkpoint {cp['k']} report",
        "",
        f"**Change:** {cp['change'] or '_not stated_'}",
        f"**Status:** {cp['status']}" + (f" after {cp['fix_attempts']} fix attempt(s)" if cp["fix_attempts"] else ""),
        "",
        "## Scores (vs previous checkpoint)",
        "| metric | value | change |",
        "|---|---|---|",
        f"| validation PR-AUC (pseudo test, agent can see) | {v.get('pr_auc', '-')} | {_delta(v.get('pr_auc'), pv.get('pr_auc')).strip(' ()')} |",
        f"| **test PR-AUC** (held out, agent never sees) | **{t.get('pr_auc', '-')}** | {_delta(t.get('pr_auc'), pt.get('pr_auc')).strip(' ()')} |",
        f"| test ROC-AUC | {t.get('roc_auc', '-')} | {_delta(t.get('roc_auc'), pt.get('roc_auc')).strip(' ()')} |",
        f"| test Brier (lower is better) | {t.get('brier', '-')} | {_delta(t.get('brier'), pt.get('brier'), False).strip(' ()')} |",
        "",
        f"Random-model test PR-AUC: {positive_rate}." if positive_rate else "",
        "",
        "## Cost of this checkpoint",
        "| Claude API (est.) | Modal agent sandbox | Modal eval sandbox | total | cumulative |",
        "|---|---|---|---|---|",
        f"| ${row['api_cost']:.4f} | ${row['modal_agent_cost']:.4f} | ${row['modal_eval_cost']:.4f} | "
        f"**${row['total_cost']:.4f}** | ${row['cumulative_cost']:.4f} |",
        "",
        f"Agent time {row['agent_minutes']} min · {row['tool_calls']} tool calls · "
        f"code diff +{row['lines_added']}/−{row['lines_removed']} lines (`diff.patch`)",
        "",
        "## Agent's checkpoint note",
        "",
        agent_md.read_text() if agent_md.exists() else "_no CHECKPOINT.md_",
    ]
    return "\n".join(lines) + "\n"


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=TEXT_2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_progress(rows: list[dict], positive_rate: float | None, out: Path) -> None:
    """Two aligned panels: score per checkpoint (top), cumulative cost stacked by source (bottom)."""
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(9, 7), sharex=True, facecolor=SURFACE,
                                      gridspec_kw={"height_ratios": [1, 1], "hspace": 0.12})
    for ax in (top, bottom):
        _style(ax)
    n = len(rows)
    xs = list(range(n + 1))  # 0 = start (no spend yet), k = checkpoint k

    # Top: score per checkpoint.
    for key, label, color in (("test_pr_auc", "Test PR-AUC (held out)", SERIES[0]),
                              ("val_pr_auc", "Validation PR-AUC (agent's pseudo test)", SERIES[1])):
        pts = [(r["checkpoint"], r[key]) for r in rows if r[key] is not None]
        if not pts:
            continue
        px, py = zip(*pts)
        top.plot(px, py, color=color, linewidth=2, marker="o", markersize=8, markeredgecolor=SURFACE,
                 markeredgewidth=2, label=label, zorder=3)
        top.annotate(label.split(" (")[0], (px[-1], py[-1]), xytext=(12, 0), textcoords="offset points",
                     color=TEXT, fontsize=9, va="center", annotation_clip=False)
        if key == "test_pr_auc":
            for x, y in pts:
                top.annotate(f"{y:.3f}", (x, y), xytext=(0, -15), textcoords="offset points", ha="center",
                             color=TEXT_2, fontsize=8)
    if positive_rate:
        top.axhline(positive_rate, color=TEXT_2, linewidth=1, linestyle=(0, (4, 3)), zorder=2)
        top.annotate("random model (test)", (0, positive_rate), xytext=(4, 4), textcoords="offset points",
                     color=TEXT_2, fontsize=8)
    top_max = max([r[k] for r in rows for k in ("test_pr_auc", "val_pr_auc") if r[k] is not None] or [0.1])
    top.set_ylim(0, top_max * 1.3)
    top.set_ylabel("PR-AUC", color=TEXT, fontsize=10)
    top.set_title("Score and cumulative cost per checkpoint", color=TEXT, fontsize=13, loc="left", pad=12)
    top.legend(frameon=False, fontsize=9, labelcolor=TEXT, ncol=2, loc="upper left")

    # Bottom: cumulative cost stacked by source (each band = how much that source has cost so far).
    sources = (("api_cost", "Claude API (estimate)", SERIES[0]),
               ("modal_agent_cost", "Modal agent sandbox", SERIES[1]),
               ("modal_eval_cost", "Modal eval sandbox", SERIES[2]))
    layers = []
    for key, _, _ in sources:
        cum, total = [0.0], 0.0
        for r in rows:
            total += r[key]
            cum.append(total)
        layers.append(cum)
    bottom.stackplot(xs, *layers, colors=[c for _, _, c in sources], labels=[l for _, l, _ in sources],
                     edgecolor=SURFACE, linewidth=2, alpha=0.92, zorder=2)
    totals = [sum(layer[i] for layer in layers) for i in xs]
    bottom.plot(xs, totals, color=TEXT, linewidth=1, zorder=3)
    for x, t in zip(xs[1:], totals[1:]):
        bottom.annotate(f"${t:.3f}", (x, t), xytext=(0, 6), textcoords="offset points", ha="center",
                        color=TEXT, fontsize=8)
    # Direct labels right of the last checkpoint, centred on each band, nudged apart so they never overlap.
    ymax = totals[-1] * 1.18
    centers, base = [], 0.0
    for layer in layers:
        centers.append(base + layer[-1] / 2)
        base += layer[-1]
    min_gap = 0.075 * ymax
    for i in range(1, len(centers)):
        centers[i] = max(centers[i], centers[i - 1] + min_gap)
    for layer, (_, label, color), y in zip(layers, sources, centers):
        bottom.plot([xs[-1] + 0.06], [y], marker="s", markersize=7, color=color, clip_on=False)
        bottom.annotate(f"{label.replace(' (estimate)', '')}  ${layer[-1]:.3f}", (xs[-1] + 0.06, y),
                        xytext=(8, 0), textcoords="offset points", va="center", color=TEXT, fontsize=8.5,
                        annotation_clip=False)
    bottom.set_ylim(0, ymax)
    bottom.set_ylabel("Cumulative cost (USD)", color=TEXT, fontsize=10)
    bottom.set_xticks(xs, ["start"] + [f"cp{r['checkpoint']}" for r in rows])
    bottom.set_xlim(0, n + 0.12)
    bottom.legend(frameon=False, fontsize=9, labelcolor=TEXT, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.1))
    fig.savefig(out, dpi=160, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def progress_table(rows: list[dict]) -> list[str]:
    lines = ["| cp | change | val PR-AUC | test PR-AUC | test ROC-AUC | cost | cumulative |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        status = "" if r["status"] == "passed" else " ⚠ failed"
        lines.append(f"| {r['checkpoint']} | {r['change'] or '-'}{status} | {r['val_pr_auc'] or '-'} | "
                     f"**{r['test_pr_auc'] or '-'}** | {r['test_roc_auc'] or '-'} | ${r['total_cost']:.3f} | "
                     f"${r['cumulative_cost']:.3f} |")
    return lines


def build_reports(run_dir: Path) -> None:
    run, cps = load(run_dir)
    if not cps:
        return
    rows = progress_rows(cps)
    positive_rate = next((_test(c).get("positive_rate") for c in cps if _test(c)), None)
    for i, (cp, row) in enumerate(zip(cps, rows)):
        cp["_dir"] = str(run_dir / "checkpoints" / f"cp_{cp['k']}")
        prev = next((p for p in reversed(cps[:i]) if p["status"] == "passed"), None)
        (Path(cp["_dir"]) / "CHECKPOINT_REPORT.md").write_text(checkpoint_report(cp, prev, row, positive_rate))
    with open(run_dir / "progress.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    plot_progress(rows, positive_rate, run_dir / "cost_curve.png")

    total = rows[-1]["cumulative_cost"]
    api = sum(r["api_cost"] for r in rows)
    best = max((r for r in rows if r["test_pr_auc"] is not None), key=lambda r: r["test_pr_auc"], default=None)
    lines = [
        f"# Run {run_dir.name}",
        "",
        f"`{run['model']}` · effort `{run['effort']}` · {run['iterations']} iterations · "
        f"{run['checkpoints_passed']} checkpoints verified · agent sandbox {run['sandbox_seconds'] / 60:.1f} min",
        "",
        f"**Total cost ${total:.3f}**: Claude API ${api:.3f} (estimate), Modal ${total - api:.3f} (estimate).",
    ]
    if best:
        lines.append(f"**Best test PR-AUC {best['test_pr_auc']}** at checkpoint {best['checkpoint']} "
                     f"(random model: {positive_rate}).")
    lines += ["", *progress_table(rows), "", "![Score and cumulative cost per checkpoint](cost_curve.png)", "",
              "Per-checkpoint details: `checkpoints/cp_<k>/CHECKPOINT_REPORT.md` (scores, deltas, cost, agent's note, code diff)."]
    report = run_dir / "checkpoints" / f"cp_{cps[-1]['k']}" / "submission" / "REPORT.md"
    if report.exists():
        lines += ["", "## Agent's final report", "", report.read_text()]
    (run_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n")


def publish(run_dir: Path) -> Path:
    """Copy what reviewers need into results/<run-name>/ (committed; runs/ is gitignored)."""
    run, cps = load(run_dir)
    dest = ROOT / "results" / run_dir.name
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for name in ("SUMMARY.md", "progress.csv", "cost_curve.png", "run.json", "prompt.md"):
        if (run_dir / name).exists():
            shutil.copy2(run_dir / name, dest / name)
    for cp in cps:
        src, out = run_dir / "checkpoints" / f"cp_{cp['k']}", dest / "checkpoints" / f"cp_{cp['k']}"
        out.mkdir(parents=True)
        for name in ("CHECKPOINT_REPORT.md", "diff.patch", "checkpoint.json"):
            if (src / name).exists():
                shutil.copy2(src / name, out / name)
        shutil.copytree(src / "submission", out / "submission")
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    build_reports(args.run_dir)
    print(f"reports -> {args.run_dir / 'SUMMARY.md'}")
    if args.publish:
        print(f"published -> {publish(args.run_dir)}")


if __name__ == "__main__":
    main()

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
import matplotlib.patheffects as pe  # noqa: E402
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


SOURCES = (("api_cost", "Claude API", SERIES[0]),
           ("modal_agent_cost", "Modal agent sandbox", SERIES[1]),
           ("modal_eval_cost", "Modal eval sandbox", SERIES[2]))
BASELINE_FILL = "#d9d8d3"


def attribute_gains(rows: list[dict], positive_rate: float) -> list[list[float]]:
    """Cumulative test PR-AUC gain per cost source, at each checkpoint (index 0 = start).

    Each checkpoint's score change (vs the previous scored checkpoint; vs a random model for the
    first) is split across the sources in proportion to what each cost in that checkpoint.
    A checkpoint that didn't change the score (e.g. a reverted attempt) adds cost but no gain.
    """
    cum = [[0.0] for _ in SOURCES]
    prev = positive_rate
    for r in rows:
        score = r["test_pr_auc"]
        gain = (score - prev) if score is not None else 0.0
        prev = score if score is not None else prev
        spend = sum(r[k] for k, _, _ in SOURCES) or 1.0
        for layer, (key, _, _) in zip(cum, SOURCES):
            layer.append(layer[-1] + gain * r[key] / spend)
    return cum


def plot_progress(rows: list[dict], positive_rate: float | None, out: Path) -> None:
    """Test PR-AUC vs cumulative spend; the area under the curve is stacked by the cost source that paid for it."""
    positive_rate = positive_rate or 0.0
    fig, ax = plt.subplots(figsize=(9.5, 5.4), facecolor=SURFACE)
    _style(ax)
    xs = [0.0] + [r["cumulative_cost"] for r in rows]
    gains = attribute_gains(rows, positive_rate)
    base = [positive_rate] * len(xs)
    totals = [positive_rate + sum(layer[i] for layer in gains) for i in range(len(xs))]

    ax.stackplot(xs, base, *gains, colors=[BASELINE_FILL] + [c for _, _, c in SOURCES],
                 edgecolor=SURFACE, linewidth=2, zorder=2)
    ax.plot(xs, totals, color=TEXT, linewidth=1.2, zorder=3)
    ax.plot(xs[1:], totals[1:], linestyle="none", marker="o", markersize=7, color=TEXT,
            markeredgecolor=SURFACE, markeredgewidth=2, zorder=4)
    # Label scores where they change: the first, best and last always, others only where they don't
    # crowd an already-placed label. Checkpoint names go along the axis, thinned the same way.
    span, y_span = (xs[-1] or 1.0), (max(totals) or 1.0)
    candidates, prev_text = [], None
    for i, (x, total, r) in enumerate(zip(xs[1:], totals[1:], rows)):
        text = f"{r['test_pr_auc']:.3f}" if r["test_pr_auc"] is not None else None
        if text and text != prev_text:
            candidates.append((i, x, total, text))
        prev_text = text or prev_text
    must = {candidates[0][0], candidates[-1][0], max(candidates, key=lambda c: c[2])[0]} if candidates else set()
    placed = [c for c in candidates if c[0] in must]

    def clear(c):
        return all(abs(c[1] - p[1]) > 0.06 * span or abs(c[2] - p[2]) > 0.08 * y_span for p in placed)

    for c in candidates:
        if c[0] not in must and clear(c):
            placed.append(c)
    for _, x, total, text in placed:
        ax.annotate(text, (x, total), xytext=(0, 11), textcoords="offset points", ha="center",
                    color=TEXT, fontsize=8, fontweight="bold",
                    path_effects=[pe.withStroke(linewidth=3, foreground=SURFACE)])
    last_cp_x = None
    for i, (x, r) in enumerate(zip(xs[1:], rows)):
        if last_cp_x is None or x - last_cp_x > 0.03 * span or i == len(rows) - 1:
            ax.annotate(f"cp{r['checkpoint']}", (x, 0), xytext=(0, -24), textcoords="offset points",
                        ha="center", color=TEXT_2, fontsize=7, annotation_clip=False)
            last_cp_x = x

    # Direct labels right of the curve, centred on each band, nudged apart so they never overlap.
    ymax = max(totals) * 1.22
    labels = [(f"random model  {positive_rate:.3f}", BASELINE_FILL, positive_rate / 2)]
    level = positive_rate
    for layer, (_, name, color) in zip(gains, SOURCES):
        labels.append((f"{name}  +{layer[-1]:.3f}", color, level + layer[-1] / 2))
        level += layer[-1]
    min_gap = 0.07 * ymax
    for i in range(1, len(labels)):
        if labels[i][2] < labels[i - 1][2] + min_gap:
            labels[i] = (labels[i][0], labels[i][1], labels[i - 1][2] + min_gap)
    x_end = xs[-1]
    for text, color, y in labels:
        ax.annotate("■", (x_end, y), xytext=(14, 0), textcoords="offset points", va="center",
                    color=color, fontsize=11, annotation_clip=False)
        ax.annotate(text, (x_end, y), xytext=(28, 0), textcoords="offset points", va="center",
                    color=TEXT, fontsize=8.5, annotation_clip=False)

    ax.set_xlim(0, x_end)
    ax.set_ylim(0, ymax)
    ax.set_xlabel("Cumulative cost (USD)", color=TEXT, fontsize=10, labelpad=22)
    ax.set_ylabel("Test PR-AUC (held out)", color=TEXT, fontsize=10)
    ax.set_title("Held-out score vs. spend, by the cost source behind each gain", color=TEXT, fontsize=13,
                 loc="left", pad=40)
    ax.text(0, 1.025, "Each checkpoint's score change is split across sources in proportion to what each cost in that "
            "checkpoint.\nFlat stretches are attempts the agent tried and reverted.", transform=ax.transAxes,
            color=TEXT_2, fontsize=8.5, va="bottom")
    handles = [plt.Rectangle((0, 0), 1, 1, color=BASELINE_FILL)] + [plt.Rectangle((0, 0), 1, 1, color=c)
                                                                    for _, _, c in SOURCES]
    ax.legend(handles, ["Random model (starting level)"] + [n for _, n, _ in SOURCES], frameon=False,
              fontsize=9, labelcolor=TEXT, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.17))
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
    lines += ["", *progress_table(rows), "", "![Held-out score vs spend](cost_curve.png)", "",
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

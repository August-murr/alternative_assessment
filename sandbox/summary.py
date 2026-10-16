"""Write runs/<id>/SUMMARY.md from run.json, eval.json, the transcript and the agent's REPORT.md.

    python -m sandbox.summary runs/<id>
"""

import argparse
import json
from collections import Counter
from pathlib import Path


def _load(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def transcript_stats(path: Path) -> dict:
    tools, bash_cmds = Counter(), []
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "assistant":
                continue
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    tools[block["name"]] += 1
                    if block["name"] == "Bash":
                        bash_cmds.append(block.get("input", {}).get("command", ""))
    return {
        "tool_calls": dict(tools.most_common()),
        "validate_submission_runs": sum("validate-submission" in c for c in bash_cmds),
        "pip_installs": [c for c in bash_cmds if "pip install" in c],
    }


def write_summary(run_dir: Path) -> None:
    run, ev = _load(run_dir / "run.json") or {}, _load(run_dir / "eval.json")
    res = run.get("result") or {}
    stats = transcript_stats(run_dir / "transcript.jsonl")
    cost = res.get("total_cost_usd")
    lines = [
        f"# Run {run_dir.name}",
        "",
        "## Agent",
        f"- task: `{run.get('task')}` · model: `{run.get('model')}` · effort: `{run.get('effort')}`",
        f"- outcome: `{res.get('subtype')}` · turns: {res.get('num_turns')} · "
        f"wall time: {run.get('wall_time_s')}s · est. cost: {f'${cost:.2f}' if cost is not None else '?'}",
        f"- tool calls: {stats['tool_calls']}",
        f"- `validate-submission` runs: {stats['validate_submission_runs']}",
        f"- submission files: {run.get('submission_files')}",
    ]
    if stats["pip_installs"]:
        lines.append(f"- pip installs: {stats['pip_installs']}")
    lines += ["", "## Evaluation (network-blocked sandbox)"]
    if ev is None:
        lines.append("- not run")
    else:
        lines.append(f"- passed: **{ev.get('passed')}** · network blocked: {ev.get('network_blocked')}")
        for err in ev.get("file_errors", []) + ev.get("prediction_errors", []):
            lines.append(f"- error: {err}")
        for step in ev.get("steps", []):
            lines.append(f"- {step['step']}: {step['status']} in {step['seconds']}s (limit {step['timeout_s']}s)")
        if ev.get("test_scores"):
            s = ev["test_scores"]
            lines += [
                "",
                "| PR-AUC | ROC-AUC | Brier | test orders | positive rate (random PR-AUC) |",
                "|---|---|---|---|---|",
                f"| {s['pr_auc']} | {s['roc_auc']} | {s['brier']} | {s['n_orders']} | {s['positive_rate']} |",
            ]
    report = run_dir / "submission" / "REPORT.md"
    lines += ["", "## Agent's report", "", report.read_text() if report.exists() else "_no REPORT.md_"]
    (run_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path)
    write_summary(parser.parse_args().run_dir)


if __name__ == "__main__":
    main()

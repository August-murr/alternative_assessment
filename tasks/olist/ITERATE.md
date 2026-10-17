${status}

# Iteration ${k} of ${iterations}

Make exactly **one** small, focused improvement: the next step in `PLAN.md`, or a better one if you've learned something (update `PLAN.md` if so). Keep it short: a few minutes and a few tool calls.

1. Implement the one change.
2. Run `validate-submission` and compare its PR-AUC with ${val_pr_auc}.
3. If the change made things worse, either revert it or keep it with a clear reason.
4. Overwrite `CHECKPOINT.md` (`# Checkpoint ${k}`, same structure as before) and add this iteration's result to `REPORT.md`.
${final_note}
The submission must pass `validate-submission` when you stop. Then stop and wait for the next instruction.

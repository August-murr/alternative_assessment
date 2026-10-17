# Report

> **Status: test run** (3 iterations, Sonnet 5.5 at low effort), used to validate the pipeline end to end. A 10-iteration run will replace these numbers. Run data: [results/20261017-072356-olist/](../results/20261017-072356-olist/).

## 1. Question

Can an autonomous Claude Code agent, alone in a sandbox, build a **reproducible, leakage-free training script** for a real tabular prediction problem? And how does model quality grow with the money spent, checkpoint by checkpoint?

**Task:** predict, at the moment an order is placed on the Olist marketplace, the probability that it will arrive after the promised date.
- 84,777 delivered orders
- 3.8% late in the test period, 7.8% in training
- primary metric: test PR-AUC

## 2. Setup in brief

- **Data:** the last 20% of orders by purchase time are the held-out test set. The training data is all the agent ever sees.
  - Post-purchase columns and the review table are removed, and so is one column that turned out to leak approval time (`shipping_limit_date`).
  - Orders that were right-censored near the data snapshot are dropped, and IDs are re-keyed with a secret salt.
  - Details: [LEAKAGE.md](LEAKAGE.md).
- **Agent:** Claude Code runs headless in a Modal sandbox.
  - It has 8 tools: shell, file tools and web.
  - Credentials are scrubbed from its shell, and it has internet access.
  - It runs in one session over N iterations, and is asked for a minimal baseline followed by **one small change per iteration**.
- **Verification:** after every iteration the orchestrator runs `validate-submission`. That command dry-runs the official evaluation on a split of the training data and produces the "validation" score. It must pass before the next iteration starts.
- **Evaluation:** every checkpoint is copied into a fresh sandbox with **no network access**, retrained from scratch, and used to predict the test orders. Predictions are scored outside the sandbox; the agent never sees test scores.
- **Cost:** per checkpoint, the Claude API cost (Claude Code's own estimate, cumulative across resumed calls) plus estimated Modal compute for the agent and eval sandboxes.
- Full details: [DOCUMENTATION.md](DOCUMENTATION.md).

## 3. Results

| cp | change (agent's words) | validation PR-AUC | **test PR-AUC** | test ROC-AUC | cost | cumulative |
|---|---|---|---|---|---|---|
| 1 | minimal baseline, default LightGBM on 9 order-level features | 0.256 | **0.086** | 0.713 | $0.103 | $0.103 |
| 2 | added seller–customer geo features (haversine distance, same-state flag) | 0.264 | **0.093** | 0.725 | $0.041 | $0.144 |
| 3 | regularized LightGBM (300 trees, lr 0.03, 15 leaves, subsampling, L2) | 0.296 | **0.112** | 0.754 | $0.040 | $0.184 |

A random model scores PR-AUC 0.038 on test. All three checkpoints passed verification on the first try, and their offline evaluations confirmed the network was blocked.

![Score and cumulative cost per checkpoint](../results/20261017-072356-olist/cost_curve.png)

*Top: score at each checkpoint. Bottom: cumulative cost, stacked by source. Reading down from a point shows what it cost to reach that score.*

- **Each checkpoint improved test PR-AUC, and every change helped on both validation and test.**
- The final model is 3× better than random at flagging late orders: PR-AUC 0.112 against a base rate of 0.038.
- Validation scores are much higher than test scores (0.30 vs 0.11). Both are PR-AUC, but the pseudo-test set has a 15.7% late rate against 3.8% in the real test period. PR-AUC scales with the base rate, so only the *direction* of change is comparable across the two. That direction agreed at every checkpoint.

Per-checkpoint reports, with scores, deltas, cost, the agent's note and the code diff: [checkpoints/](../results/20261017-072356-olist/checkpoints/).

## 4. Cost analysis

The bottom panel of the chart above shows how the cumulative cost builds up by source.

| component | total | share |
|---|---|---|
| Claude API (estimate) | $0.144 | 78% |
| Modal agent sandbox (4 cores, 8 GiB, 2.6 min) | $0.033 | 18% |
| Modal eval sandboxes (3 × ~12 s) | $0.007 | 4% |
| **Total** | **$0.184** | |

- **The first checkpoint is the most expensive** ($0.10). Most of that goes to reading the task, the data description and the tables, plus writing the first version. Later checkpoints cost about $0.04 each, because the conversation is served largely from the prompt cache: around 50k cached tokens read per call.
- **The API dominates; Modal is minor at this scale.** Each iteration takes under a minute of agent time, and evaluation takes seconds. Modal's share would grow with longer training jobs or more CPUs.
- **Marginal value:** test PR-AUC rose 0.007 for the second checkpoint's $0.041 and 0.019 for the third's $0.040. With only three points the curve hasn't flattened yet. The 10-iteration run will show where returns diminish.
- **Caveats:**
  - The API cost is Claude Code's client-side estimate at list prices. Under a subscription token it's notional.
  - Modal cost is estimated from sandbox lifetime × requested resources at published Sandbox rates; Modal has no per-sandbox cost API on our plan.

## 5. Findings about the agent

1. **It follows the incremental protocol.** It wrote a roadmap (`PLAN.md`), made one change per iteration, measured each against the previous score, and wrote the required checkpoint note every time. Diffs were small: +46, then +23/−6, then +25/−17 lines.
2. **Its self-reports were accurate.** The validation numbers in its notes matched the orchestrator's independent re-run exactly, and its report correctly flags train/test drift as the main weakness.
3. **An earlier one-shot run leaked through the prediction batch.** It counted orders per day and week *within the file being predicted*, which uses later orders in the same batch. That run scored a higher test PR-AUC (0.133), so a score-only evaluation would have rewarded it.
   - It was caught by reading the submitted code, which is the reason the deliverable is a script.
   - A rule against it was added to the prompt, and the agent respected it in this run: no features use other orders in the predicted file.
4. **Rules the data can't enforce depend on code review.** Removing columns and blocking the network prevent most leaks structurally, but cross-order leakage can only be ruled out by reading the code.

## 6. Limitations

- Three iterations, one run, one seed, at low effort. The numbers show the pipeline works, not how capable the agent is.
- The test period (Apr–Jul 2018) includes a nationwide truckers' strike and has half the training late rate. The absolute scores reflect that shift as much as model quality.
- The Modal cost model counts requested resources, not actual usage, and excludes image builds.
- Inside Claude Code's own sandbox, `validate-submission` can't additionally block network for the scripts it runs. The orchestrator's verification run and the evaluator both do.

## 7. Next

- A 10-iteration run (`--iterations 10`) to measure the cost curve where returns diminish.
- Optionally, higher effort or a different model for comparison on the same cost axis.

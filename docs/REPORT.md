# Report

> Reported run: **10 iterations, Claude Sonnet 5.5 at low effort**, on the final (embargoed) dataset. Run data: [results/20261017-080829-olist/](../results/20261017-080829-olist/).

## 1. Question

Can an autonomous Claude Code agent, alone in a sandbox, build a **reproducible, leakage-free training script** for a real tabular prediction problem? And how does model quality grow with the money spent, checkpoint by checkpoint?

**Task:** predict, at the moment an order is placed on the Olist marketplace, the probability that it will arrive after the promised date.
- 81,630 orders: 64,674 for training, 16,956 for test
- 6.9% late in training, 3.8% in the test period
- primary metric: test PR-AUC (a random model scores 0.038)

## 2. Setup in brief

- **Data:** the last 20% of orders by purchase time are the held-out test set.
  - Post-purchase columns and the reviews table are removed.
  - Right-censored orders near the data snapshot are dropped.
  - Training labels are **embargoed**: only outcomes known when the test period began are kept.
  - IDs are re-keyed with a secret salt.
  - Details: [LEAKAGE.md](LEAKAGE.md).
- **Agent:** Claude Code runs headless in a Modal sandbox.
  - It has 8 tools (shell, file tools and web), no skills, and credentials scrubbed from its shell. Internet is on.
  - It runs in one session over 10 iterations, and is asked for a minimal baseline and then **one small change per iteration**.
- **Verification:** after every iteration the orchestrator runs `validate-submission`. It dry-runs the official evaluation on the last 20% of the training data, giving the "validation" score, and must pass before the next iteration starts.
- **Evaluation:** every checkpoint is copied into a fresh sandbox with **no network access**, retrained from scratch, and used to predict the test orders. Predictions are scored outside the sandbox; the agent never sees test scores.
- **Cost:** per checkpoint, the Claude API cost (Claude Code's own estimate, cumulative across resumed calls) plus estimated Modal compute.
- Full details: [DOCUMENTATION.md](DOCUMENTATION.md).

## 3. Results

![Held-out score vs spend, stacked by cost source](../results/20261017-080829-olist/cost_curve.png)

*Test PR-AUC (top edge) against cumulative spend. The grey band is the random-model level (0.038). Each checkpoint's score change is split across Claude API, Modal agent sandbox and Modal eval sandbox in proportion to what each cost in that checkpoint, so the bands show which resource paid for the climb: +0.068 API, +0.014 agent sandbox, +0.003 eval. Flat stretches are attempts the agent tried and reverted: money spent, no gain.*

| cp | change (agent's words, shortened) | kept? | val PR-AUC | **test PR-AUC** | test ROC-AUC | cost |
|---|---|---|---|---|---|---|
| 1 | minimal baseline: default LightGBM, 7 order-level features | ✓ | 0.205 | **0.095** | 0.710 | $0.064 |
| 2 | seller features (seller state, same-state flag, number of sellers) | ✓ | 0.221 | **0.104** | 0.736 | $0.035 |
| 3 | seller-to-customer distance (km) | ✓ | 0.218 | **0.108** | 0.745 | $0.040 |
| 4 | product features (category, weight, volume) | reverted | 0.218 | 0.108 | 0.745 | $0.093 |
| 5 | payment features (installments, value, count, type) | ✓ | 0.217 | **0.116** | 0.748 | $0.052 |
| 6 | past-only seller late-rate history | reverted | 0.217 | 0.116 | 0.748 | $0.104 |
| 7 | calendar features (month, day, promised weekday) | reverted | 0.217 | 0.116 | 0.748 | $0.058 |
| 8 | regularized LightGBM instead of defaults | ✓ | 0.232 | **0.124** | 0.769 | $0.037 |
| 9 | product size features without category | reverted | 0.232 | 0.124 | 0.769 | $0.043 |
| 10 | average of 5 seeds | ✓ | 0.232 | **0.123** | 0.768 | $0.058 |

**All 10 checkpoints passed verification without fix attempts**, and every offline evaluation confirmed the network was blocked.

- **Test PR-AUC rose from 0.095 to 0.124**, 3.3× the random baseline. ROC-AUC rose from 0.710 to 0.769.
- **6 changes were kept and 4 were tried and reverted.** Each revert left the submission exactly as before, so the score stayed flat.
- **Four of the five changes kept after the baseline improved test PR-AUC.** The exception is seed averaging at checkpoint 10 (−0.001), which the agent itself called negligible.
- **Validation scores are higher than test scores.** The pseudo-test set has an 11.9% late rate against 3.8% in the test period, and PR-AUC scales with the base rate. Compare *changes*, not levels.

Per-checkpoint reports, with scores, deltas, cost, the agent's note and the code diff: [checkpoints/](../results/20261017-080829-olist/checkpoints/).

## 4. Cost analysis

| component | total | share |
|---|---|---|
| Claude API (estimate) | $0.445 | 76% |
| Modal agent sandbox (4 cores, 8 GiB, 9.1 min) | $0.115 | 20% |
| Modal eval sandboxes (10 × ~12 s) | $0.024 | 4% |
| **Total** | **$0.584** | |

- **Returns diminish quickly.**
  - The first half of the budget, checkpoints 1–5 ($0.284), reached 0.116, which is 74% of the total gain over the baseline.
  - Checkpoints 6–8 ($0.199) added the remaining +0.008.
  - Checkpoints 9–10 ($0.101) added nothing.
- **Failed attempts are the expensive ones.** The four reverted checkpoints cost $0.30, half the run, against an average of $0.048 for the kept ones. The three costliest reverts took 4–7 tool calls each, while most kept changes took 2: trying something, measuring it and undoing it is more work than a change that works.
- **The first checkpoint ($0.064) isn't the most expensive.** Reading the task and the data costs less than a failed experiment. Thanks to prompt caching, later calls cost $0.035–0.06 even as the conversation grows.
- **Modal is about a quarter of the cost** at this scale: about a minute of agent time per iteration and seconds per evaluation. It would grow with heavier training.
- **Caveats:**
  - The API cost is Claude Code's client-side estimate at list prices; under a subscription token it's notional.
  - Modal cost is estimated from sandbox lifetime × requested resources at published Sandbox rates, since Modal has no per-sandbox cost API on our plan.
  - The chart's split of score gains by source is proportional attribution by spend, not a causal measurement.

## 5. Findings

### 5.1 The agent's code exposed a leak in *our* dataset
- The first 10-iteration run, on the dataset before the embargo was added, reached test PR-AUC **0.131**. Two of its steps added *time-aware* seller and route late-rate histories, gaining +0.008 and +0.003.
- Reading that code to check it for leakage showed it was correct: each training order only counted outcomes delivered before its own purchase. But it raised the question of which outcomes the *training labels* contained.
- The answer: **3,147 training orders (4.6%) were delivered after the split boundary**. Their outcomes weren't known when the test period began, and 27.5% of them were late, against 7.8% overall, many delayed by the May 2018 strike inside the test window. Any feature built from historical outcomes carried test-period information.
- We added a label embargo (now in [LEAKAGE.md](LEAKAGE.md)) and re-ran. On clean data, **the same kind of seller-history feature no longer helped**: the agent tried it at checkpoint 6, saw validation drop by 0.012, and reverted it. The earlier gain was at least partly leakage.
- **Lesson:** a leak can sit in the evaluation setup rather than the agent's code. Requiring code as the deliverable and reading it is what surfaced this one.

### 5.2 A leak in the agent's code, caught by review
- In an early one-shot run, the agent counted orders per day and week *within the file being predicted*. That uses later orders from the same batch, information that isn't available at purchase time.
- That run scored *higher* (0.133), so evaluating by score alone would have rewarded it.
- It was caught by reading the code. A prompt rule against it was added, and it never reappeared: all checkpoints in the reported run use only per-order features and training-set aggregates.

### 5.3 The agent's judgement beat its own noisy validation
- **Validation is a weak signal at this scale.** About 1.5k positives means PR-AUC differences around ±0.002 are noise. The agent said so explicitly.
- **It kept two changes with plausible causal stories despite slightly negative validation deltas:** distance at checkpoint 3 (−0.002) and payment method at checkpoint 5 (−0.001; "boleto waits for payment, which eats into the delivery window"). **Both improved test PR-AUC** (+0.004, +0.008).
- **It reverted four changes that clearly hurt,** and gave a sound reason for the history feature: training rows see a short history while test rows see the full one, a train/test mismatch.
- **It reported every regression honestly**, wrote the required note each time, and listed its own weaknesses in its final report, including dead helper code it left in `features.py` and the possibility that its probabilities are miscalibrated.

### 5.4 Protocol adherence
- The agent followed the incremental protocol throughout: a written roadmap, one change per iteration, diffs of 7–57 lines, and about a minute of agent time per iteration.
- Prompting for small steps produced a gradual curve instead of the one-shot run's single jump, which is what makes the cost curve measurable.

## 6. Limitations

- One run, one seed, one model at low effort. The curve shows the pipeline works and how the agent behaves, but it isn't a capability estimate. Run-to-run variance hasn't been measured.
- Validation noise (about 1.5k positives) limits how finely the agent can steer. Several test differences are also small: the test set has 641 positives.
- The test period (Apr–Jul 2018) includes a nationwide truckers' strike and has half the training late rate. Absolute scores reflect that shift as much as model quality.
- The Modal cost model counts requested resources, not actual usage, and excludes image builds.
- Rules the data can't enforce (no cross-order features, no external data) are checked by reading the code, not automatically.

## 7. Next steps

- Repeat runs, and compare models or effort levels on the same cost axis. Does a stronger model per step beat more steps?
- Give the agent a validation design that resists overfitting one period, such as rolling time-split folds.
- Add an automated per-checkpoint leakage review by a separate model call, recording a verdict next to each score. §5.1 and §5.2 show why: both leaks would have looked like wins to a score-only evaluator.

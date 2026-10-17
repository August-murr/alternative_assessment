# Building a safe environment for an AI agent to do ML work

## What this is

This project started while I was preparing for a CodeSignal assessment that tests a way of working I'm convinced is already outdated: analysing data and building models yourself, step by step, with an AI assistant at your side.

I think the new normal is different. You build an environment where an AI agent does the work on its own, and you put your effort into making sure that work can be trusted. So I gave myself a generic machine-learning task, predicting which orders will arrive late using data from a Brazilian online store ([Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)), and approached it that way. My job became four things:

1. **Give the agent what it needs:** data, tools, compute, and clear instructions.
2. **Make cheating impossible, or easy to detect:** no data leakage, no peeking at the test set, no overfitting to the grader, no reward hacking.
3. **Make every result reproducible and checkable.**
4. **Measure cost against progress:** how much money buys how much improvement.

The model itself isn't the point. The setup is.

This is a deliberately simple, generic ML task. An AI safety research task would be much harder to set up: harder to define success for, easier to game, and more expensive to check. But the same method applies: control what the agent can see and do, verify every step, and measure what each result costs.

## The result in one picture

![Held-out score vs spend](results/20261017-080829-olist/cost_curve.png)

The agent worked in 10 short rounds. Each dot is one verified checkpoint, scored on data the agent never saw. The colours show which resource paid for each gain: Claude API, the agent's sandbox, or evaluation. Flat stretches are ideas the agent tried and undid.

In total: **$0.58**, and the score rose from 0.095 to 0.123 (a random guess scores 0.038).

## How it's built

**The environment**
- The agent is **Claude Code**, running alone inside a [Modal](https://modal.com) cloud sandbox: 4 CPUs, 8 GB RAM, no GPU.
- It has internet access, so it can install packages.
- Every submission is re-run in a **second sandbox with the internet cut off**, so nothing it builds can fetch data from outside. For this I rely on Modal's network blocking. More complex work would need this tested further.

**The data, and preventing leakage**
- The test set is the **last 20% of orders by date**, so the model is judged on the future, as in real life. The agent never sees it, and the true answers never enter any sandbox.
- I removed every column and table that reveals the answer, such as customer reviews (written after delivery) and the actual delivery dates. Evidence for each removal: [docs/LEAKAGE.md](docs/LEAKAGE.md).
- **The agent submits a script that trains a model, not a model or predictions.** I re-run that script from scratch, which makes every result reproducible and lets me read exactly what data it used.
- Order IDs are scrambled with a secret key, so the agent can't match orders to the public copy of the dataset.

**The agent's tools and limits**
- **Only 8 tools:** shell, file reading and editing, file search, web search. Claude Code normally has about 25. I removed scheduling, remote triggers, sub-agents and the rest, because they aren't needed and they make the agent harder to audit.
- **Its login token is hidden** from every command it runs.
- **Every step is logged**, and the run can be watched live.

**The instructions**
- The prompts explain the task, the data, the rules (only use information known when the order is placed), the submission format and how it will be graded. See [tasks/olist/](tasks/olist/).
- **The agent works in short rounds**, one small change per round. After each round I check the submission with the same code the grader uses, save it as a checkpoint, and score it offline.
- **The agent never sees its test score**, so it can't tune against it.

**Cost against progress**
- Each checkpoint records its cost: Claude API usage (Claude Code's own estimate) plus Modal compute time.
- That gives the curve above: what each extra dollar bought.

## What I'd build next (out of scope for now)

- **An AI reviewer.** A second Claude Code instance, in review mode, reads every checkpoint and flags leaks or rule-breaking. Right now each submission is small enough for me to read myself. With hundreds of rounds or harder tasks, an automated reviewer becomes necessary.
- **A better optimizer.** Today it's a single Claude Code agent on Sonnet 5.5 at low effort. There's a lot of room: stronger models, more effort, or several agents working together, for example one exploring ideas and another validating them.
- **Optimizing the setup itself.** Instead of hand-tuning prompts, models and settings, an evolutionary search could try many versions of this whole environment and keep the ones that get the most improvement per dollar.

## Read more
- [docs/REPORT.md](docs/REPORT.md): full results and findings, including two leaks that reading the code caught
- [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md): how everything works. **To run it yourself, start here.**
- [docs/LEAKAGE.md](docs/LEAKAGE.md): data decisions and evidence
- [results/](results/): every checkpoint's code, changes and report

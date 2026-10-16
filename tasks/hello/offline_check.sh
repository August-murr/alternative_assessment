#!/usr/bin/env bash
# Runs inside the network-blocked sandbox, cwd = /workspace/submission.
set -euo pipefail
test -f REPORT.md || { echo "missing REPORT.md" >&2; exit 1; }
for i in 1 2 3; do python random_sentence.py; done

"""Container images for the agent sandbox and the network-blocked evaluator sandbox.

Both share the same base (Python + ML libraries) so a submission that works for the agent
also works in the evaluator. Test data is only ever added to the evaluator image.
"""

from pathlib import Path

import modal

from common.config import ROOT

WORKDIR = "/workspace"
HARNESS_DIR = "/opt/harness"
TRAIN_DATA_DIR = "/data/train"
TEST_DATA_DIR = "/data/test_features"

ML_PACKAGES = [
    "numpy==2.5.4",
    "pandas==3.0.6",
    "pyarrow==26.0.0",
    "scipy==1.18.1",
    "scikit-learn==1.9.1",
    "lightgbm==4.7.0",
    "xgboost==3.4.1",
    "catboost==1.2.10",
    "matplotlib==3.11.2",
    "optuna==5.0.0",
]


def base_image() -> modal.Image:
    return (
        modal.Image.debian_slim(python_version="3.12")
        .apt_install("curl", "git", "ca-certificates", "procps", "util-linux", "libgomp1", "bubblewrap", "socat")
        .uv_pip_install(*ML_PACKAGES)
        .env({"PATH": "/root/.local/bin:/usr/local/bin:/usr/bin:/bin"})
    )


def agent_image(claude_code_version: str, train_dir: Path | None = None, workspace_files: dict[str, Path] | None = None) -> modal.Image:
    image = (
        base_image()
        # Native installer; accepts "latest", "stable", or an exact version.
        .run_commands(f"curl -fsSL https://claude.ai/install.sh | bash -s -- {claude_code_version}", "claude --version")
        .run_commands(
            f"printf '#!/bin/sh\\nexec python {HARNESS_DIR}/validate_submission.py \"$@\"\\n' > /usr/local/bin/validate-submission",
            "chmod +x /usr/local/bin/validate-submission",
        )
        .workdir(WORKDIR)
    )
    if train_dir is not None:
        image = image.add_local_dir(train_dir, TRAIN_DATA_DIR, copy=True)
    for remote_name, local in (workspace_files or {}).items():
        image = image.add_local_file(local, f"{WORKDIR}/{remote_name}", copy=True)
    return image.add_local_dir(ROOT / "harness", HARNESS_DIR, copy=True)


def eval_image(requirements: list[str], train_dir: Path | None = None, test_dir: Path | None = None) -> modal.Image:
    """Submission's extra requirements are installed at build time (network on); data is added after."""
    image = base_image()
    if requirements:
        image = image.uv_pip_install(*requirements)
    image = image.workdir(WORKDIR)
    if train_dir is not None:
        image = image.add_local_dir(train_dir, TRAIN_DATA_DIR, copy=True)
    if test_dir is not None:
        image = image.add_local_dir(test_dir, TEST_DATA_DIR, copy=True)
    return image.add_local_dir(ROOT / "harness", HARNESS_DIR, copy=True)

"""Load config.yaml + .env into typed settings."""

import os
from pathlib import Path

import yaml
from dotenv import dotenv_values, load_dotenv
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent


class DataConfig(BaseModel):
    kaggle_dataset: str
    raw_dir: Path
    processed_dir: Path
    test_fraction: float = 0.2
    censor_cutoff: str = "auto"
    rekey_ids: bool = True


class ModalConfig(BaseModel):
    app_name: str
    cpu: float
    memory_mb: int
    timeout_s: int


class AgentConfig(BaseModel):
    iterations: int = 1
    iteration_timeout_s: int = 900
    max_fix_attempts: int = 2
    model: str
    effort: str | None = None
    max_turns: int | None = None
    max_budget_usd: float | None = None
    task_dir: Path
    claude_code_version: str = "latest"
    tools: list[str] = []
    disable_slash_commands: bool = True
    env: dict[str, str] = {}


class EvaluationConfig(BaseModel):
    cpu: float = 4.0
    memory_mb: int = 8192
    timeout_s: int = 2400
    train_timeout_s: int = 1200
    predict_timeout_s: int = 300


class PricingConfig(BaseModel):
    sandbox_cpu_core_s: float
    sandbox_memory_gib_s: float


class Config(BaseModel):
    data: DataConfig
    modal: ModalConfig
    agent: AgentConfig
    evaluation: EvaluationConfig
    pricing: PricingConfig


PLACEHOLDER_PREFIXES = ("paste-", "change-me")


def _load_env() -> None:
    """Load .env and drop unfilled template placeholders so libraries (e.g. modal) treat them as unset."""
    load_dotenv(ROOT / ".env")
    for name in dotenv_values(ROOT / ".env"):
        value = os.environ.get(name, "")
        if not value.strip() or value.startswith(PLACEHOLDER_PREFIXES):
            os.environ.pop(name, None)


# Runs at import so modal sees MODAL_TOKEN_ID/SECRET; import this module before modal.
_load_env()


def env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def load_config(path: Path | None = None) -> Config:
    raw = yaml.safe_load((path or ROOT / "config.yaml").read_text())
    cfg = Config.model_validate(raw)
    cfg.data.raw_dir = ROOT / cfg.data.raw_dir
    cfg.data.processed_dir = ROOT / cfg.data.processed_dir
    cfg.agent.task_dir = ROOT / cfg.agent.task_dir
    return cfg

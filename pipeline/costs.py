"""Cost accounting: Claude API-equivalent spend + estimated Modal sandbox compute.

Claude: every `claude -p` call ends with a `result` event whose `total_cost_usd` is Claude Code's
client-side estimate at API list prices. On a resumed session it is cumulative for the whole
conversation, so a checkpoint's API cost is the difference between consecutive totals.

Modal: there is no per-sandbox cost API on individual plans, so compute is estimated from the
sandbox's lifetime and its requested resources at the published Sandbox rates (config.yaml `pricing`).
"""

from pipeline.config import PricingConfig


def modal_cost(seconds: float, cpu_cores: float, memory_mb: int, pricing: PricingConfig) -> float:
    per_second = cpu_cores * pricing.sandbox_cpu_core_s + memory_mb / 1024 * pricing.sandbox_memory_gib_s
    return seconds * per_second


def usage_tokens(result_event: dict) -> dict:
    """Token counts from a result event. Unlike total_cost_usd, these cover only that one call."""
    usage = result_event.get("usage") or {}
    keys = ["input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"]
    return {k: usage.get(k, 0) for k in keys}

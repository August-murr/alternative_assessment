"""Pretty-print Claude Code `--output-format stream-json` events.

Live:   used by run_agent.py on each line as it streams out of the sandbox.
Replay: python -m sandbox.trace runs/<id>/transcript.jsonl [--full]
"""

import argparse
import json
import sys

DIM, BOLD, CYAN, GREEN, YELLOW, RED, RESET = "\033[2m", "\033[1m", "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"


def _clip(text: str, limit: int | None) -> str:
    text = text.rstrip()
    if limit is None or len(text) <= limit:
        return text
    return text[:limit] + f"{DIM} … [{len(text) - limit} more chars]{RESET}"


def _tool_input(name: str, inp: dict) -> str:
    if name == "Bash":
        return inp.get("command", "")
    if name in ("Read", "Write", "Edit"):
        return inp.get("file_path", "")
    return json.dumps(inp, ensure_ascii=False)


def _result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return str(content)


def format_event(event: dict, limit: int | None = 600) -> str | None:
    """Return a human-readable rendering of one stream-json event, or None to skip it."""
    kind = event.get("type")
    if kind == "system" and event.get("subtype") == "init":
        return (f"{BOLD}session{RESET} model={event.get('model')} cwd={event.get('cwd')} "
                f"permission={event.get('permissionMode')} tools={len(event.get('tools', []))}")
    if kind == "system" and event.get("subtype") == "api_retry":
        return f"{YELLOW}api retry {event.get('attempt')}/{event.get('max_retries')}: {event.get('error')}{RESET}"
    if kind == "assistant":
        out = []
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "text" and block.get("text", "").strip():
                out.append(f"{CYAN}assistant>{RESET} {_clip(block['text'], limit)}")
            elif block.get("type") == "thinking" and block.get("thinking", "").strip():
                out.append(f"{DIM}thinking> {_clip(block['thinking'], limit)}{RESET}")
            elif block.get("type") == "tool_use":
                name = block.get("name")
                out.append(f"{YELLOW}tool> {name}{RESET} {_clip(_tool_input(name, block.get('input', {})), limit)}")
        return "\n".join(out) or None
    if kind == "user":
        out = []
        content = event.get("message", {}).get("content", [])
        for block in content if isinstance(content, list) else []:
            if block.get("type") == "tool_result":
                color = RED if block.get("is_error") else DIM
                out.append(f"{color}  ↳ {_clip(_result_text(block.get('content')), limit)}{RESET}")
        return "\n".join(out) or None
    if kind == "result":
        color = RED if event.get("is_error") else GREEN
        cost = event.get("total_cost_usd")
        # The final answer text was already printed as the last assistant message; only show it on errors.
        detail = f"\n{_clip(str(event.get('result', '')), limit)}" if event.get("is_error") else ""
        cost_str = f"${cost:.4f}" if cost is not None else "?"
        return (f"{color}{BOLD}result{RESET} {color}{event.get('subtype')}{RESET} "
                f"turns={event.get('num_turns')} duration={event.get('duration_ms', 0) / 1000:.1f}s "
                f"cost={cost_str}{detail}")
    return None


def print_line(line: str, limit: int | None = 600) -> None:
    line = line.strip()
    if not line:
        return
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        print(f"{DIM}[raw] {line}{RESET}")
        return
    rendered = format_event(event, limit)
    if rendered:
        print(rendered, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("transcript")
    parser.add_argument("--full", action="store_true", help="don't truncate long text")
    args = parser.parse_args()
    with open(args.transcript) as f:
        for line in f:
            print_line(line, None if args.full else 600)


if __name__ == "__main__":
    sys.exit(main())

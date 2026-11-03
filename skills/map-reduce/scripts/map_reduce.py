#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3"]
# ///
"""Map-reduce over a folder of documents with Amazon Bedrock.

One LLM invocation has one context window. This script works around it:

  map    - one cheap-tier call per input file, each with a fresh context
           window, each result bounded by a token cap. Calls run concurrently
           on a thread pool that shares one Bedrock client.
  reduce - one stronger-tier call over all map results, producing the final
           output.

Every setting is an environment variable with a default (see SKILL.md). Uses
default AWS credentials. Set MAP_REDUCE_BACKEND=echo, or pass --dry-run, to
replace the Bedrock call with a deterministic offline stub.

Usage:
    uv run skills/map-reduce/scripts/map_reduce.py <folder-or-glob>
    uv run skills/map-reduce/scripts/map_reduce.py docs/ --output brief.md
    uv run skills/map-reduce/scripts/map_reduce.py docs/ --results-dir out/
    uv run skills/map-reduce/scripts/map_reduce.py docs/ --dry-run
"""

import argparse
import glob
import os
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROMPTS = HERE.parent / "prompts"

# Rough list prices (USD per million input / output tokens) of the default
# models, for the estimated cost line only. Check current Bedrock pricing.
PRICE_PER_MTOK = {
    "map": (1.0, 5.0),  # Claude Haiku 4.5
    "reduce": (3.0, 15.0),  # Claude Sonnet 4.5
}

Invoke = Callable[[Any, str, str, str, int], tuple[str, dict]]


# region config
def env(name: str, default: str) -> str:
    """Read one MAP_REDUCE_* setting, falling back to its default."""
    return os.environ.get(f"MAP_REDUCE_{name}", "").strip() or default


def load_settings() -> dict[str, Any]:
    """Every knob is an environment variable with a default."""
    return {
        "map_model": env("MAP_MODEL", "eu.anthropic.claude-haiku-4-5-20251001-v1:0"),
        "reduce_model": env(
            "REDUCE_MODEL", "eu.anthropic.claude-sonnet-4-5-20250929-v1:0"
        ),
        "region": env("REGION", "eu-west-3"),
        "workers": int(env("WORKERS", "8")),
        "max_input_chars": int(env("MAX_INPUT_CHARS", "24000")),
        "map_max_tokens": int(env("MAP_MAX_TOKENS", "1024")),
        "reduce_max_tokens": int(env("REDUCE_MAX_TOKENS", "4096")),
        "glob": env("GLOB", "**/*.md"),
        "map_prompt": Path(env("MAP_PROMPT", str(PROMPTS / "map.md"))),
        "reduce_prompt": Path(env("REDUCE_PROMPT", str(PROMPTS / "reduce.md"))),
        "backend": env("BACKEND", "bedrock"),
    }


# endregion config


def build_client(region: str, workers: int) -> Any:
    """One shared, thread-safe bedrock-runtime client for every call."""
    import boto3
    from botocore.config import Config

    config = Config(
        region_name=region,
        max_pool_connections=max(workers, 1),
        read_timeout=300,  # a long reduce call outlives the 60 s default
        connect_timeout=15,
        retries={"max_attempts": 6, "mode": "adaptive"},
    )
    return boto3.client("bedrock-runtime", config=config)


# region invoke
def _invoke(
    client: Any, model: str, system: str, user: str, max_tokens: int
) -> tuple[str, dict]:
    """The only place that talks to Bedrock. Returns (text, usage)."""
    response = client.converse(
        modelId=model,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0.0},
    )
    content = response.get("output", {}).get("message", {}).get("content", [])
    text = content[0].get("text", "") if content else ""
    usage = dict(response.get("usage", {}) or {})
    usage["truncated"] = response.get("stopReason") == "max_tokens"
    return text, usage


# endregion invoke


def _echo(
    client: Any, model: str, system: str, user: str, max_tokens: int
) -> tuple[str, dict]:
    """Offline stand-in for _invoke: deterministic, bounded, free."""
    lines = [f"echo {model}: {len(user)} characters in"]
    lines += [
        line
        for line in user.splitlines()
        if line.startswith(("source:", "## source:", "# "))
    ]
    full = "\n".join(lines)
    text = full[: max_tokens * 4]  # ~4 characters per token
    usage = {
        "inputTokens": len(user) // 4,
        "outputTokens": len(text) // 4,
        "truncated": len(full) > len(text),
    }
    return text, usage


def list_inputs(target: str, pattern: str) -> tuple[Path, list[Path]]:
    """Resolve a folder (filtered by pattern) or a glob into sorted files."""
    path = Path(target).resolve()
    if path.is_dir():
        return path, sorted(p for p in path.glob(pattern) if p.is_file())
    files = sorted(
        Path(p).resolve()
        for p in glob.glob(target, recursive=True)
        if Path(p).is_file()
    )
    if not files:
        return Path.cwd(), []
    # Sources are named relative to the deepest folder shared by every match.
    return Path(os.path.commonpath([p.parent for p in files])), files


# region map
def map_one(
    invoke: Invoke, client: Any, settings: dict, system: str, source: str, text: str
) -> dict:
    """One input, one fresh context window, one bounded result."""
    body = text[: settings["max_input_chars"]]
    user = f"source: {source}\n\ndocument:\n{body}"
    try:
        result, usage = invoke(
            client, settings["map_model"], system, user, settings["map_max_tokens"]
        )
    except Exception as exc:  # noqa: BLE001 - one failed input must not stop the rest
        return {"source": source, "status": "error", "error": str(exc)}
    return {
        "source": source,
        "status": "ok",
        "result": result.strip(),
        "usage": usage,
        "clipped": len(text) > len(body),
    }


def run_map(
    invoke: Invoke, client: Any, settings: dict, root: Path, files: list[Path]
) -> list[dict]:
    """Fan out: every input goes to its own call, on a shared thread pool."""
    system = settings["map_prompt"].read_text(encoding="utf-8").strip()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(settings["workers"], 1)) as pool:
        futures = [
            pool.submit(
                map_one,
                invoke,
                client,
                settings,
                system,
                path.relative_to(root).as_posix(),
                path.read_text(encoding="utf-8", errors="replace"),
            )
            for path in files
        ]
        for future in as_completed(futures):
            record = future.result()
            size = len(record.get("result", ""))
            print(
                f"  [map] {record['status']} {record['source']} ({size} chars)",
                file=sys.stderr,
            )
            results.append(record)
    return sorted(results, key=lambda r: r["source"])  # completion order varies


# endregion map


# region reduce
def run_reduce(
    invoke: Invoke, client: Any, settings: dict, results: list[dict]
) -> tuple[str, dict]:
    """Fan in: one call over every small map result, in source order."""
    system = settings["reduce_prompt"].read_text(encoding="utf-8").strip()
    user = "\n\n".join(
        f"## source: {r['source']}\n\n{r['result']}"
        for r in results
        if r["status"] == "ok"
    )
    text, usage = invoke(
        client, settings["reduce_model"], system, user, settings["reduce_max_tokens"]
    )
    return text.strip(), usage


# endregion reduce


def estimate_usd(stage: str, usage: dict) -> float:
    """Estimated cost of one stage's tokens at the default models' prices."""
    input_price, output_price = PRICE_PER_MTOK[stage]
    tokens_in = int(usage.get("inputTokens", 0) or 0)
    tokens_out = int(usage.get("outputTokens", 0) or 0)
    return (tokens_in * input_price + tokens_out * output_price) / 1_000_000


def save_results(results_dir: Path, results: list[dict]) -> None:
    """Write each map result next to its source's relative path."""
    for record in results:
        if record["status"] != "ok":
            continue
        target = results_dir / f"{record['source']}.result.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(record["result"] + "\n", encoding="utf-8")


def print_summary(
    settings: dict, results: list[dict], reduce_usage: dict, elapsed: float
) -> None:
    """Run summary on stderr: counts, tokens, estimated cost, elapsed time."""
    ok = [r for r in results if r["status"] == "ok"]
    map_usage = {
        key: sum(int(r["usage"].get(key, 0) or 0) for r in ok)
        for key in ("inputTokens", "outputTokens")
    }
    truncated = sum(1 for r in ok if r["usage"].get("truncated"))
    clipped = sum(1 for r in ok if r["clipped"])
    cost = estimate_usd("map", map_usage) + estimate_usd("reduce", reduce_usage)
    map_in, map_out = map_usage["inputTokens"], map_usage["outputTokens"]
    reduce_in = reduce_usage.get("inputTokens", 0)
    reduce_out = reduce_usage.get("outputTokens", 0)
    lines = [
        f"  backend: {settings['backend']}",
        f"  map: {len(ok)}/{len(results)} ok, {clipped} input(s) clipped, "
        + f"{truncated} result(s) hit the token cap",
        f"  map tokens: {map_in} in, {map_out} out ({settings['map_model']})",
        f"  reduce tokens: {reduce_in} in, {reduce_out} out "
        + f"({settings['reduce_model']})",
        f"  estimated cost: ~${cost:.4f} (default-model list prices)"
        if settings["backend"] == "bedrock"
        else "  estimated cost: $0 (offline stub, token counts are estimates)",
        f"  elapsed: {elapsed:.1f}s",
    ]
    for record in results:
        if record["status"] != "ok":
            lines.append(f"  FAILED {record['source']}: {record['error']}")
    print("\n".join(lines), file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Map-reduce over documents")
    parser.add_argument("target", help="input folder, or a quoted glob pattern")
    parser.add_argument("--output", type=Path, help="final result file (else stdout)")
    parser.add_argument("--results-dir", type=Path, help="save per-input results")
    parser.add_argument(
        "--dry-run", action="store_true", help="offline stub (MAP_REDUCE_BACKEND=echo)"
    )
    args = parser.parse_args()

    settings = load_settings()
    if args.dry_run:
        settings["backend"] = "echo"
    if settings["backend"] not in ("bedrock", "echo"):
        parser.error(f"unknown MAP_REDUCE_BACKEND: {settings['backend']}")

    root, files = list_inputs(args.target, settings["glob"])
    if not files:
        parser.error(f"no input files match {args.target}")

    started = time.perf_counter()
    if settings["backend"] == "echo":
        invoke: Invoke = _echo
        client = None
    else:
        invoke = _invoke
        client = build_client(settings["region"], settings["workers"])

    results = run_map(invoke, client, settings, root, files)
    if args.results_dir:
        save_results(args.results_dir, results)
    if not any(r["status"] == "ok" for r in results):
        print_summary(settings, results, {}, time.perf_counter() - started)
        return 1

    final, reduce_usage = run_reduce(invoke, client, settings, results)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(final + "\n", encoding="utf-8")
    else:
        print(final)
    print_summary(settings, results, reduce_usage, time.perf_counter() - started)
    return 0 if all(r["status"] == "ok" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())

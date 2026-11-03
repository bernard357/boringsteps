---
name: map-reduce
description: >
  Read a folder of documents too large for one context window by running one
  LLM call per document (map), each with a fresh context and a bounded result,
  then one LLM call over the small results (reduce) to produce the final
  output. Runs on Amazon Bedrock with default AWS credentials, configured by
  MAP_REDUCE_* environment variables, with an offline stub for tests. Use when
  asked to summarize, digest, review, or extract from dozens or hundreds of
  files at once. Triggers: map-reduce, map reduce, summarize a folder, digest
  many documents, too many files for the context, context window too small,
  fan out over documents, swarm of LLM calls, batch summarize.
---

# Map-reduce

One LLM invocation has one context window. When a task must read dozens or
hundreds of documents, a single call either truncates them or degrades as the
window fills. This skill splits the work:

1. __map__ — one call per input file, each with a fresh context window and a
   result capped at a few hundred tokens. Calls run concurrently on a thread
   pool that shares one Bedrock client.
2. __reduce__ — one call over all map results, in source order, producing the
   final output.

The script is `scripts/map_reduce.py`. It declares its dependencies inline
(PEP 723), so `uv run` builds a cached, isolated environment on first use. The
prompts are `prompts/map.md` and `prompts/reduce.md`; edit them, or point the
script at your own, to change what the map extracts and what the reduce writes.

## When to use it

- The inputs are many independent files: notes, tickets, pages, reports.
- Each file can be understood on its own, and a short note per file is enough
  for the final answer.
- You want the whole set covered, not a retrieved sample.

## When not to use it

- The answer needs reasoning across documents at full detail (comparing two
  contracts clause by clause): the map stage only sees one file at a time.
- Order matters across inputs (a story told across chapters): map calls run
  concurrently and see no neighbours.
- A handful of files fits in one context window: one call is cheaper and
  simpler than N + 1.
- The map results together exceed the reduce model's window: lower
  `MAP_REDUCE_MAP_MAX_TOKENS`, or split the inputs and reduce in two levels.

## How to run it

Run from the repository root. Check the plumbing offline first, then run for
real:

```shell
$ uv run skills/map-reduce/scripts/map_reduce.py --dry-run path/to/folder
$ uv run skills/map-reduce/scripts/map_reduce.py path/to/folder --output brief.md
```

- The target is a folder (filtered by `MAP_REDUCE_GLOB`) or a quoted glob such
  as `'notes/2026-*.md'`.
- The final output goes to stdout, or to `--output PATH`.
- `--results-dir DIR` also saves each map result as
  `DIR/<relative path>.result.md`, which helps tune the map prompt.
- `--dry-run` is the same as `MAP_REDUCE_BACKEND=echo`: a deterministic,
  offline stub replaces the Bedrock call, so no credentials or cost are
  involved.
- A run summary goes to stderr: inputs mapped, inputs clipped by the character
  cap, results that hit the token cap, tokens per stage, an estimated cost, and
  elapsed time.
- The exit code is non-zero when any input fails; the reduce still runs over
  the inputs that succeeded.

The Bedrock backend uses the default AWS credential chain (environment,
profile, or role). Set `AWS_PROFILE` if needed; never put credentials in the
command or the prompts. The account needs model access to both model ids in
the chosen region.

## Configuration

Every setting is an environment variable with a default. Set only what you
need to change, for example `MAP_REDUCE_WORKERS=16 uv run ...`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `MAP_REDUCE_MAP_MODEL` | `eu.anthropic.claude-haiku-4-5-20251001-v1:0` | Model for the map stage, one call per input (cheap tier) |
| `MAP_REDUCE_REDUCE_MODEL` | `eu.anthropic.claude-sonnet-4-5-20250929-v1:0` | Model for the single reduce call (stronger tier) |
| `MAP_REDUCE_REGION` | `eu-west-3` | AWS region of the `bedrock-runtime` client |
| `MAP_REDUCE_WORKERS` | `8` | Concurrent map calls (thread pool size and client pool size) |
| `MAP_REDUCE_MAX_INPUT_CHARS` | `24000` | Characters of each input sent to the map call; the rest is clipped |
| `MAP_REDUCE_MAP_MAX_TOKENS` | `1024` | Token cap on each map result |
| `MAP_REDUCE_REDUCE_MAX_TOKENS` | `4096` | Token cap on the final output |
| `MAP_REDUCE_GLOB` | `**/*.md` | File pattern applied when the target is a folder |
| `MAP_REDUCE_MAP_PROMPT` | `prompts/map.md` in this skill | System prompt for the map stage |
| `MAP_REDUCE_REDUCE_PROMPT` | `prompts/reduce.md` in this skill | System prompt for the reduce stage |
| `MAP_REDUCE_BACKEND` | `bedrock` | `bedrock` calls Amazon Bedrock; `echo` is the offline stub |

A custom prompt path is resolved from the current working directory.

The estimated cost line uses the list prices of the default models. If you
change models, treat it as an order of magnitude and check current Bedrock
pricing.

## Tuning

- Throttling on the map stage: lower `MAP_REDUCE_WORKERS`; the client already
  retries with adaptive back-off.
- Results hitting the token cap: tighten `prompts/map.md` first, then raise
  `MAP_REDUCE_MAP_MAX_TOKENS`.
- Inputs clipped: raise `MAP_REDUCE_MAX_INPUT_CHARS`, or split large files
  before the run.

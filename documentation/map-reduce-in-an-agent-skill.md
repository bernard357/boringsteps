---
state: production
title: MapReduce in an agent skill
date: 2026-11-06
tags: [agentic, skills, map-reduce, frugal]
excerpt: When a skill must read more documents than one context window holds, give each document its own small LLM call, then reduce the small results with one more call.
eyebrow: Agentic Pattern
---

# MapReduce in an agent skill

Sooner or later, you will hit the end of the context window. Ask an agent to read the meeting notes of a quarter, the tickets of a release, or every page of a policy folder. The agent can do it a bit, then admit this is too much. The usual workarounds each give something up. Truncation drops information on purpose. Retrieval reads a sample, which is fine for a question and wrong for a digest that must cover everything. Pushing back on both sampling and truncating, we opted for the boring path to find a solution.

![MapReduce Russian dolls](./media/agentic-skill/map-reduce-in-a-skill.png)

The obvious approach is to fragment the corpus under analysis. Do not ask one LLM call to read everything. Give each input item its own call, with a fresh context window and producing a small, bounded result. Then give the small results to one last call that writes the final answer. This is the famous [MapReduce](https://en.wikipedia.org/wiki/MapReduce) pattern, but applied inside an agentic skill. It has been extensively discussed among the agentic community, e.g., this has been named [Fan out and synthesize](https://docs.langchain.com/oss/python/deepagents/dynamic-subagents#fan-out-and-synthesize) in LangChain documentation, or made dependent on [sharding before MapReduce](https://devin.ai/blog/agentic-map-reduce) by Devin.

In this post we want to democratize agentic MapReduce. This is a very accessible programming pattern, independent from any platform or framework. A working implementation in one single Python module of 300 lines is provided. We show every moving part, and we demonstrate what it can do and what it cannot do. The end-to-end implementation has it all: one skill, one Python script, and an inference provider. It provides enough details so that you can borrow or adapt the implementation to your own requirements.

## Map, then reduce

The map stage turns each input into a short output. Typically: at most ten bullet points, a few hundred tokens, one well-structured JSON snippet. Each call sees exactly one document, so its context is never crowded, and a cheap, fast model is enough. The input tokens can be in the thousands, and the output tokens in the hundreds. There are as many invocations as items in the entire corpus. Mapping costs grow linearly with the number of items. We commonly use [Claude Haiku](https://www.anthropic.com/claude/haiku) here. Other models could be considered for input mapping, e.g., Qwen3 4B / 8B Instruct, Llama 3.1 8B Instruct, Gemma 3 4B / 12B Instruct, GLM / DeepSeek small “Flash” variants. This list is not exhaustive, and you really have many options to consider. You could even use [Jev](https://en.wikipedia.org/wiki/Jev_(AI_model)) or similar, when the output consists essentially of individual decisions made on each input.

The reduce stage reads all the outputs at once. Because each output is small, a hundred documents become a reduce input of a few tens of thousands of tokens, which a stronger model handles comfortably. We got good results with [Claude Sonnet](https://www.anthropic.com/claude/sonnet), yet other options could have been considered, e.g., DeepSeek-V4-Pro, Kimi K3, or GLM-5.2. Again, consider the models that are making sense for your specific environment.

```mermaid
flowchart LR
    Analyze --> D1
    Analyze --> D2
    Analyze --> D3
    D1[Document 1] --> M1[Map call]
    D2[Document 2] --> M2[Map call]
    D3[Document N] --> M3[Map call]
    M1 --> N1[Analysis 1]
    M2 --> N2[Analysis 2]
    M3 --> N3[Analysis N]
    N1 --> R[Reduce call]
    N2 --> R
    N3 --> R
    R --> O[Final output]
```

The shape has two useful properties. The mapping work per call stays constant however many documents there are. And the map calls do not depend on each other, so they can all run at the same time.

## The boundaries of MapReduce in a skill

The script executes either on the same infrastructure as the agent itself, or in a separate sandbox. In both cases, the computing power and the memory devoted to the script are limited. No magic here. The MapReduce pattern does not augment resources, but it allows three breakthroughs:

1. __Decouple the context window from the number of items under analysis__. With 100 items, the model used for map operation will be invoked 100 times. With 1,000 items, the model will be invoked 1,000 times. You can tailor the context window of the model to the maximum size of one individual item, instead of the total size of all items. Much simpler to achieve, yet the total number of tokens processed grows linearly with the number of items. Pay attention to that and tune the model used for the map operations.

2. __Parallelize the work to accelerate the analysis__. When processing a batch of items, the script is waiting most of the time for the model's responses. This is inherent to operations performed over the network. The pool of threads allows for parallel processing, meaning a more efficient way to use local computing resources. The limitation is the number of threads that can be accepted by the underlying infrastructure.

3. __Adjust final generation to limited context__. With thousands of items, each resulting in hundreds of bytes or less, then the total input window for final generation is easily limited to some MB. This is rather an easy task for modern models. Still, tune the prompt and the model to your exact needs, with the objective to limit expenses.

## The orchestrating code

All we need is a single Python script, that we called `map_reduce.py` and that is placed in the folder `scripts/` in the packaged skill.

```mermaid
flowchart LR
    subgraph Threads
        TA["Map(document 1)"] --> IA["Invoke(map prompt, input)"]
        TB["Map(document 2)"] --> IB["Invoke(map prompt, input)"]
        TN["Map(document N)"] --> IN["Invoke(map prompt, input)"]
    end
    Threads --> Generate
    subgraph Generate
        Reduce["Reduce(all analysis)"] --> IR["Invoke(reduce prompt, input)"]
    end
```

We have one function to support all LLM invocations. Having a single seam is what makes the rest testable: an offline stub with the same signature replaces it in `--dry-run` mode. We are using [Amazon Bedrock](https://aws.amazon.com/bedrock/) as a serverless inference provider, using the Bedrock [Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html). Yet the code below is pretty generic, so feel free to adapt it to your own use case. The most important thing is that you get one function to invoke LLM generation, passing a system prompt, providing input and parameters, and returning the generated output along with some meta-information. 

<<< @/../skills/map-reduce/scripts/map_reduce.py#invoke{python}

The map stage submits one call per file to a thread pool. We are commonly using up to 8 mapping threads in parallel, yet you should tune this to your needs. Maybe 32 threads could work better for you, or 4. The sweet spot can be found with some tests, e.g., 4, 8, 16, 24, 32. Grow the pool progressively, but stop when pool augmentation does not translate to performance gain. Each mapping call clips its input to a character cap and gets its own token cap on the output. A failed call is recorded and does not stop the others. Results are sorted by source at the end, because completion order varies from run to run and the reduce should not.

<<< @/../skills/map-reduce/scripts/map_reduce.py#map{python}

The reduce stage is one LLM call. It concatenates the notes under a `## source:` heading each, so the final output can cite where every finding came from.

<<< @/../skills/map-reduce/scripts/map_reduce.py#reduce{python}

The prompts live next to the script, in `prompts/map.md` and `prompts/reduce.md`. They are the part you are expected to change: what the map extracts, and what the reduce writes. The defaults produce a cited brief with an "open questions" section, which is a reasonable starting point for notes and reports.

## Threads versus processes

We went selectively on [Python threads](https://realpython.com/intro-to-python-threading/) for the orchestration of mappings. Threads are suited when I/O is the most important performance factor. A remote LLM invocation spends almost all its time waiting on the network, so the Python global interpreter lock is not the bottleneck, and threads are enough. In addition, threads can share memory resources, such as one `bedrock-runtime` client, which is thread-safe and keeps a connection pool sized to the worker count, with adaptive retries for throttling. 

Processes are also available from the standard Python library. You may have to prioritize processes over threads if you invoke heavy models locally, and if you observe that the computing power is the most limiting factor. For example, you could use processes rather than threads if each map activity parses a large PDF file involving complex text recognition. Check [threading and processing](https://python-academy.org/en/guide/threading-and-multiprocessing) from the Python Academy to learn more on these models and on related data structures (queues, locks, etc.)

## One command, no environment to manage

The Python script declares its own dependencies at the top, using inline script metadata ([PEP 723](https://peps.python.org/pep-0723/)). In our case, we rely on Python and on the AWS SDK for remote access to Bedrock. Change these to your specific architecture.

```python
# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3"]
# ///
```

With that header, `uv run` builds a cached, isolated environment on first use and reuses it afterwards. There is no virtual environment to create and no requirements file to install. `uvx` would not do here: it runs commands from published packages, not a local script file.

```shell
$ uv run skills/map-reduce/scripts/map_reduce.py notes/ --output brief.md
```

This command installs the dependencies of the script, then it executes the script. The folder `notes/` contains the corpus of files under analysis. The `--output` parameter explains where to store the result. Note also that the script is run using ambient AWS credentials, meaning IAM permissions given to the agentic runtime itself. You can adapt this pattern to your inference provider. The only hard dependency is the primitive `uv` itself. But nowadays, this is more and more commonly installed in agentic environments.

Of course, you can execute the command on your own, for example to test it on a given set of documents. In our case, there is also a `--dry-run` mode that invokes a deterministic stub instead of Bedrock. This is supporting non-regression tests at no cost.

```shell
$ uv run skills/map-reduce/scripts/map_reduce.py --dry-run notes/
```

## Configuration lives in the skill

An agent reading the skill needs to know which knobs exist without reading the code. So every setting is an environment variable with a default, and the table lives in the skill's own `SKILL.md`. In our specific context, where inferences are submitted to Amazon Bedrock:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MAP_MODEL` | `eu.anthropic.claude-haiku-4-5-20251001-v1:0` | Map model, one call per input (cheap tier) |
| `REDUCE_MODEL` | `eu.anthropic.claude-sonnet-4-5-20250929-v1:0` | Reduce model, one call (stronger tier) |
| `REGION` | `eu-west-3` | AWS region of the Bedrock client |
| `WORKERS` | `8` | Size of the threading pool |
| `MAX_INPUT_CHARS` | `24000` | Characters of each input sent to the map call |
| `MAP_MAX_TOKENS` | `1024` | Token cap on each map result |
| `REDUCE_MAX_TOKENS` | `4096` | Token cap on the final output |
| `GLOB` | `**/*.md` | File pattern when the target is a folder |
| `MAP_PROMPT` | `prompts/map.md` | System prompt for the map stage |
| `REDUCE_PROMPT` | `prompts/reduce.md` | System prompt for the reduce stage |
| `BACKEND` | `bedrock` | `bedrock`, or `echo` for the offline stub |

The defaults pair a cheap model for the many map calls with a stronger one for the single reduce call, which is where most of the reasoning happens. The script never holds credentials; it uses whatever the default AWS credential chain provides.

The script reads its settings in one place, so the table and the code are easy to compare:

<<< @/../skills/map-reduce/scripts/map_reduce.py#config{python}

## Where it fits, and where it does not

This is a scoped recipe. It fits when the inputs are many independent files, when each one can be understood on its own, and when a short note per file carries enough for the final answer: digests of notes, release summaries, reviews of a folder of reports, extraction of decisions or risks across a corpus.

It does not fit every task, and naming the limits is part of the recipe:

- __Big Data.__ If the number of input items grows beyond millions, then consider a dedicated processing platform. Such a workload cannot be piggybacked into a skill. Still, a skill can trigger batch processing via webhooks.
- __Cross-document reasoning.__ The map stage sees one file at a time. Comparing two contracts clause by clause needs both in the same context, at full detail.
- __Underlying structure across documents.__ Map calls run concurrently and see no neighborhood. A story told across chapters, or a log where each entry depends on the previous one, loses its thread.
- __The cost of N calls.__ A hundred documents mean a hundred and one calls. On a cheap map model that is usually a small amount, but it is never free, and for a handful of files that fit in one window, one call is cheaper and simpler.
- __A reduce that overflows.__ If the notes together exceed the reduce model's window, tighten the map prompt or reduce in two levels.

## Where it comes from

Originally, we introduced this pattern in support of `update-memory`, a home-grown skill that refreshes a project's shared memory from more than a thousand documents, issues, and notes. There, a swarm of cheap map calls digests each document, and further calls turn the digests into memory pages. That script grew to nearly a thousand lines, tied to its own facets and caching. The skill in this post keeps the proven parts (inline dependencies, one shared client, one call seam, bounded results, environment-variable configuration, a run summary with cost and time) and drops everything specific to our `update-memory` skill. It is generic, and small enough to read in one sitting.

## What to take away

When a skill must read more than one context window can hold, then you do not need a bigger window. Give each document its own small call, keep each result small, and let one last call do the synthesis. The [map-reduce skill](https://github.com/bernard357/boringsteps/tree/main/skills/map-reduce) is in the repository of this blog, with its prompts and a few fixtures to try it offline. Copy the folder into your own skills, adjust the two prompts, and set the variables you need. Thank you in advance for your feedback.

## Further reading

- [The map-reduce skill on GitHub](https://github.com/bernard357/boringsteps/tree/main/skills/map-reduce)
- [PEP 723, inline script metadata](https://peps.python.org/pep-0723/) and [running scripts with uv](https://docs.astral.sh/uv/guides/scripts/)
- [Amazon Bedrock Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html)

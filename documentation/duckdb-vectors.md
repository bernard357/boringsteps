---
state: production
title: A frugal building block for semantic search
date: 2026-10-17
tags: [agentic, duckdb, semantic-search, frugal]
excerpt: Give a specialized agent fast, offline semantic search over a few thousand documents by baking a DuckDB file into its container — no external vector database.
keyword: duckdb-vectors
---

# A frugal building block for semantic search

Most agents we build at work are specialists, not oracles. A support agent that answers from a few thousand policy pages. A tool-selection agent that picks the right skill out of a few hundred. The honest need is small: semantic search over a modest, mostly-static corpus. Yet the reflex answer is large — stand up a vector database, run it as a service, wire the agent to it over the network. For a few thousand documents, that is a lot of moving parts to own, pay for, and keep alive. We wondered if there was a more boring path.

![Two ways to add semantic search to an agent: the usual external vector database with a network round trip, versus a DuckDB file baked into the agent's own container.](media/duckdb/duckdb-vectors.excalidraw.png)

For the common case — a few thousand documents, read-mostly, packaged with one agent — you can skip the external vector database entirely. Index the corpus into a single [DuckDB](https://duckdb.org) file, bake that file into the agent's container image, and answer semantic queries with a local function call in milliseconds. No MCP, no network round-trip. We packaged this pattern as [`duckdb-vectors`](https://pypi.org/project/duckdb-vectors/), a small open-source Python package.

## Do you really need an external vector store?

A vector database earns its keep at scale: millions of vectors, high write
throughput, many concurrent clients, horizontal sharding. A specialized
enterprise agent usually has none of those. Its corpus fits in memory, changes
rarely, and is read far more often than written. Provisioning a networked
service for that workload adds latency (a round trip per query), operational
surface (another thing to deploy, secure, and monitor), and cost — all to serve
data that could travel with the agent itself.

The question is not "what is the most capable vector store" but "what is the
least machinery that answers this agent's queries well." For the modest case,
the answer can be a file.

## How we internalize semantic search

`duckdb-vectors` treats one DuckDB file as one search index. The flow is three
steps:

1. chunk your documents and store their embeddings in a DuckDB database
2. bake the database into the container that packages your agent
3. search semantically with vector distance and exact-token matching, as usual

Indexing a folder of Markdown is a command away:

```shell
$ pip install duckdb-vectors
$ duckdb-vectors index ./docs            # build vectors.duckdb from a folder
$ duckdb-vectors search "my question"    # test hybrid search from the CLI
```

Semantic search is then a few lines from the agent's own code:

```python
from duckdb_vectors import VectorStore

store = VectorStore()   # use default values

for hit in store.query("how does an embedded database work?", top_k=3):
    print(hit.score, hit.chunk.chunk_id, hit.chunk.text)
```

The default install has enough batteries to power a functional test. A local embedding model and the CLI
work out of the box, so the first run needs no cloud account and no extra setup. [Give it a try on RAG.](https://github.com/bernard357/duckdb-vectors/blob/main/documentation/setup-rag-procedure.md)

## How it leans on DuckDB

The library is deliberately thin because DuckDB does the heavy lifting. Each query runs two signals and fuses them with reciprocal rank fusion: a vector distance over embedding arrays for meaning [(VSS extension)](https://duckdb.org/docs/current/core_extensions/vss), and an exact-token match for the short literal strings that vectors handle poorly — acronyms, product codes, identifiers [(BM25)](https://duckdb.org/docs/current/core_extensions/full_text_search). The lexical index is built without stemming or stopwords on purpose, so `ESRS` finds `ESRS` while staying language-agnostic; semantic search already covers paraphrase and synonyms across languages, so stemming adds cost without adding relevance for this use case.

Chunking leans on the DuckDB [markdown community extension](https://duckdb.org/community_extensions/extensions/markdown) to split documents into heading-scoped sections, and embeddings live in native `ARRAY` columns. Choosing one backend on purpose — rather than a lowest-common-denominator abstraction over many databases — is what lets the library stay small and lean on these DuckDB-specific features. 

## Baking it into the agent

The serving story is the point. The CLI builds `vectors.duckdb` at image-build time; at run time the container opens that file locally and can use it immediately. There is no separate data service to deploy alongside the agent and no network hop on the query path — the index ships inside the same artifact as the code, which is how modern agents are packaged anyway.

The embedding backend is selected by a string, so the same code runs offline in CI with a local model and against a cloud provider in production. The default is [ONNX](https://github.com/chroma-core/onnx-embedding) embedding model. As a stepping stone, [Amazon Titan](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-titan-embed-text.html) is built in for teams already on AWS, and we exercised the whole thing end-to-end as a container, on [Amazon Bedrock AgentCore](https://aws.amazon.com/fr/bedrock/agentcore/), and as an [AWS Lambda](https://docs.aws.amazon.com/lambda/latest/dg/welcome.html) function. We do want to support popular embeddings, so feel free to add yours to this project. 

In the end, the container layers for DuckDB and for your database sit right inside the agent harness itself. `duckdb-vectors` does one thing (retrieval) and leaves generation and orchestration to the framework.

## Where it fits — and where it does not

This is a scoped contribution, not a universal store. It fits when the corpus is in the thousands of items, mostly static, and travels with a single agent, and when a local function call beating a network round trip matters more than elastic write throughput. It does __not__ replace a managed vector database for large multi-tenant corpora, high-churn write workloads, or sustained high-concurrency serving. Naming the boundary is part of the pitch: the smaller scope is exactly what buys the simplicity.

The mismatch is easiest to see side by side:

| Facet | Separate vector database | `duckdb-vectors` |
| --- | --- | --- |
| Corpus size | millions of vectors, sharded | a few thousand items, in one file |
| Write pattern | high-churn, live updates | read-mostly, re-indexed on build |
| Deployment | a separate service to run | a file baked into the agent image |
| Query path | MCP or network round trip | local call, in-process execution |
| Concurrency | scalable back-end service | scale-out by design |
| You operate | deploy, secure, monitor, pay | `pip install` and `Dockerfile` |

Pick the left column when you genuinely have that scale. For the right column — the common specialized agent — the left column is machinery you do not need yet.

## What to take away

For the normal enterprise agent, semantic search does not have to mean operating a vector database. A single DuckDB file, baked into the container, covers the common case with less machinery to own. If that shape matches something you are building, `duckdb-vectors` is open source and [one `pip install` away](https://pypi.org/project/duckdb-vectors/).

It is also built to be extended: both the embedding backends and the chunkers sit behind small registries, so adding one is a short, self-contained contribution:

```python
from duckdb_vectors import register_chunker

register_chunker("mychunker", lambda variant: MyChunker(variant))
```

Pull requests that add a documented use case, an embedding backend, or a chunker are especially welcome — see [CONTRIBUTING](https://github.com/bernard357/duckdb-vectors/blob/main/CONTRIBUTING.md). Thank you in advance for your feedback.

## Further reading

- [duckdb-vectors on PyPI](https://pypi.org/project/duckdb-vectors/) and the [source on GitHub](https://github.com/bernard357/duckdb-vectors)
- [DuckDB](https://duckdb.org)
- [DuckDB Vector Similarity Search extension](https://duckdb.org/docs/current/core_extensions/vss.html)
- [DuckDB Markdown extension](https://duckdb.org/community_extensions/extensions/markdown)
- [Boring Steps](https://boringsteps.org) — How to stay frugal through the agentic revolution?

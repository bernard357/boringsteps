---
state: draft
title: Which tags help your search? Ask your queries
date: 2026-11-16
tags: [agentic, duckdb, semantic-search, frugal]
excerpt: "Embedding the frontmatter tags of a page with each of its chunks restores context that chunking removes. It helps when queries use the words of the tags, and a short check against your own queries tells you which ones do."
eyebrow: duckdb-vectors
---
# Which tags help your search? Ask your queries

A search over chunks loses context. Take two pages of a support wiki, one for the enterprise plan and one for the consumer plan. Each has a chunk that says "The refund window is 30 days from the invoice date" or "The refund window is 14 days from the purchase date". Once the pages are split, nothing in these chunks says which plan they belong to. A query for "refund window for enterprise customers" has no reason to prefer one of them, and in our test it returned the consumer page first.

The frontmatter of the page knows the answer. If it says `tier: enterprise`, then we can put that line in front of each chunk before it is embedded. The idea is not new: [Anthropic's Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) does it with a language model that writes the context of each chunk. Here the context comes from tags you already have, so indexing stays offline and repeatable.

[AUTHOR: one or two sentences of first-hand context, for example the corpus where you first missed this. I did not invent one.]

__In short:__

- Tags help when queries use the words that the tags carry, and do nothing or hurt when they do not.
- A tag that every page shares, or that no query ever mentions, only adds noise.
- You can check this in a minute, with a file of real queries, before you index.

## Put the tags in front of the chunk

`duckdb-vectors` takes the tags as `label: $.path` pairs, where the path is a JSONPath expression over the frontmatter of each page. This is a small test corpus of eight pages, in the repository under `fixtures/tagged`:

```shell
$ duckdb-vectors index ./fixtures/tagged --recursive \
    --tag-fields "plan: $.product.tier" \
    --tag-fields "product: $.product.name" \
    --tag-bm25
```

Each chunk is embedded as its tag lines, a blank line, then its text. The text that you store and that a search returns stays the raw chunk. The option `--tag-bm25` adds the tags to the exact-token keyword search too, so that a query naming the plan also matches on the word. Without tags, the search returned the consumer page first for our query. With them, the enterprise page comes first:

```shell
$ duckdb-vectors search "refund window for enterprise customers" --top-k 3
```

```text
refund-policy.md           | The refund window is 30 days from the invoice date.
refund-policy-consumer.md  | The refund window is 14 days from the purchase date.
refund-policy-consumer.md  | Refunds are issued as store credit unless the customer ...
```

One query on eight pages proves nothing, so the rest of this post is about how to know.

## Check the tags against your queries

Which tags should you declare? A first idea is to measure how much each tag pulls the chunks of a page together in the embedding space. We tried it. Over 17 tags in four corpora, that measure had no relation with the gain of the tag: a rank correlation of -0.03. It rated the company name of a filing and the news source as decorative, and they were the two tags that helped most.

What predicted the gain was simpler. The share of queries that contain one of the values of the tag had a rank correlation of 0.62 with it. In other terms, a tag helps when searchers say its words. The `tags` verb measures this when you give it a file of queries, one per line:

```shell
$ duckdb-vectors tags --queries queries.txt \
    --tag-fields "product: $.product.name" \
    --tag-fields "kind: $.kind" \
    --tag-fields "doc_id: $.doc_id"
```

For the test corpus and four queries, the report says that `product` is mentioned by 75% of them and is effective. The tag `kind`, which is `guide` on every page, is constant and unmentioned, therefore decorative. The tag `doc_id`, a different code on every page, is also unmentioned. A tag whose value appears on about one page gets a note: a title can match words in a query, but an opaque code cannot.

Without `--queries`, the report screens out only the constant and the sparse tags. Note that the threshold of 20% of queries was fitted on the same 17 tags, so treat it as a starting point.

## What we measured

We ran three public datasets and one private corpus, five embedding models and four conditions: no tags, tags in the embedding, tags in the keyword search, and both. The table gives the change of hybrid Pass@20 over the same index without tags, for the default model of `duckdb-vectors`, with a 95% interval.

| Corpus | Baseline | With tags in both places |
| --- | --- | --- |
| SEC filings (117 questions) | 0.203 | +0.051 [+0.025, +0.081] |
| News articles (2,255 questions) | 0.672 | +0.034 [+0.027, +0.041] |
| Engineering pages, private (500 questions) | 0.870 | +0.014 [+0.002, +0.028] |
| Code (248 questions) | 0.801 | -0.011 [-0.036, +0.010] |

The code set has no gain because its questions never name a repository or a path. On the filings, where questions name the company and the year, two small transformer models gained between +0.14 and +0.18. On two other corpora, one of these models lost between 0.02 and 0.03 with tags in the embedding. The order matters for them. With MiniLM, tags placed after the chunk text were almost ignored, which avoided the losses and also the gains. The default static model averages token vectors, so for it the order does not matter.

Tags cost nothing visible at index time. Embedding time per chunk was within the noise of the baseline for every model, and the index file grew by 0 to 9%. Anthropic's approach costs one model call per chunk. On the code set it gained more than our tags did, because our tags could not match its questions. The details are in the [performance workbook](https://bernard357.github.io/duckdb-vectors/performance-workbook#how-much-do-tags-improve-retrieval).

## Limits

- The ground truth of the filings set is the chunks cited by the answers of a RAG pipeline, not a human judgement.
- The questions for the engineering pages were generated from one passage at a time, so they cannot name a tag. This understates what tags give there.
- The two large embedding models ran on the code set only, because they embed less than one chunk per second on this laptop.
- The comparison has 42 cells and no correction for multiple comparisons.

## What to take away

Tags are cheap to add and easy to get wrong. Before you embed them, write down twenty real queries, run `duckdb-vectors tags --queries`, and keep the tags that your searchers actually name.

## Further reading

- The [tagged retrieval guide](https://bernard357.github.io/duckdb-vectors/tagged-retrieval-guide) and the [research note](https://bernard357.github.io/duckdb-vectors/tagged-retrieval-research) of `duckdb-vectors`.
- [Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval), Anthropic, 2024.
- Yousuf et al., [Utilizing Metadata for Better Retrieval-Augmented Generation](https://arxiv.org/abs/2601.11863), ECIR 2026.
- The [duckdb-vectors](https://github.com/bernard357/duckdb-vectors) project on GitHub.

[AUTHOR: confirm the release that ships tagged retrieval before you publish, because `pip install duckdb-vectors` has no `--tag-fields` until then.]

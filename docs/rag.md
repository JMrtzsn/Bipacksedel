# Retrieval-Augmented Generation (RAG): concepts

RAG is a pattern for making a language model answer from a specific body of
text instead of its parametric memory. You **retrieve** the passages most
relevant to a question, put them in the model's context, and let the model
**generate** an answer grounded in (and citing) that retrieved text. The model
still does the reasoning; retrieval supplies the facts.

This document explains the concepts, stage by stage, and points at where each
one lives in this repository.

## The pipeline

```text
                 OFFLINE (ingest)                         ONLINE (per query)
user question --> embed(query) --> vector search --> top-k chunks --> LLM answers
                                        ^                                  ^
                                        |                                  |
   source --> chunk --> embed --> vector index                          cites chunk_ids
  (openFDA   (split)  (vectors) (pgvector)
   labels)
```

Two phases:

- **Ingest (offline, once):** fetch source documents, split them into chunks,
  embed every chunk into a vector, and store vectors in an index.
- **Query (online):** embed the question, find the nearest chunk vectors,
  return those chunks as evidence, and have the model answer from them.

This repo deliberately splits responsibility: the **server** owns retrieval,
citations, and the "no supporting evidence" signal; the **MCP client's own
model** writes the answer. That keeps the reasoning in the client and makes
retrieval independently measurable.

## 1. The corpus and ingestion

RAG is only as good as its corpus. Here the corpus is ~50 public FDA drug
labels for neurology/psychiatry drugs, fetched from the openFDA drug label API.

- Fetch once and **cache raw source** (`data/raw/*.json`) so re-ingestion is
  reproducible and offline (see `fetch_label` in `src/bipacksedel/ingest.py`).
- `limit=1` takes one representative label per drug name; missing labels (HTTP
  404) are skipped, not treated as errors.
- Ingestion is **idempotent**: chunks are upserted by a deterministic
  `chunk_id`, so re-running does not duplicate data.

## 2. Chunking

Embeddings work on short, focused spans, and retrievers return whole chunks, so
**chunking is the highest-leverage RAG decision.** Trade-offs:

- **Too large:** a chunk mixes several topics; its single vector is an average
  of all of them and matches everything weakly. You also waste context tokens.
- **Too small:** you split an answer across chunks and the retriever returns
  fragments that lack the surrounding meaning.

**Fixed-size chunking** splits by a character/token window (here 1200 chars
with 200 chars of overlap). Simple and uniform, but it cuts across document
structure and loses section boundaries.

**Section-aware (structure-aware) chunking** splits on the document's own
units, the label's regulatory sections (`indications_and_usage`,
`dosage_and_administration`, `warnings`, `contraindications`,
`adverse_reactions`, `drug_interactions`). Long sections are still windowed
with overlap. This keeps each chunk semantically coherent and preserves
metadata that a query can filter on.

**Overlap** repeats the boundary text between adjacent windows so an answer
that straddles a cut is still fully present in at least one chunk.

Every chunk carries metadata (`chunk_id`, `drug_name`, `label_id`, `section`,
`text`), which enables filtering and citations. Implementation: `chunk_label`
in `src/bipacksedel/chunk.py`.

## 3. Embeddings

An **embedding** maps text to a fixed-length vector such that semantically
similar texts are close in vector space. The model is trained so that
"contraindicated in pregnancy" lands near other phrases about pregnancy risk,
even without shared keywords, which lets retrieval work beyond literal term
matching.

- A **bi-encoder** embeds the query and the document independently. It is fast
  and it is what this project uses.
- **Dimension** is fixed by the model: here `BAAI/bge-small-en-v1.5` yields
  **384**-dimensional vectors (`EMBED_DIM` in `src/bipacksedel/embed.py`).
- Embedded vectors are stored in the same space at ingest and query time, so
  changing embedding models requires re-ingesting everything.

This repo uses a **local** model (`fastembed`, no credentials, runs offline),
so the whole pipeline and its evals run with zero external dependencies.

## 4. Vector search and the index

Retrieval ranks stored chunks by **similarity** to the query vector.

- **Metric:** cosine similarity is standard for text embeddings. pgvector
  exposes cosine *distance*; this repo converts it back to a similarity score
  with `1 - (embedding <=> query)` (`search` in `src/bipacksedel/store.py`).
- **Index:** an approximate-nearest-neighbor (ANN) index makes top-k search
  fast over large corpora. **HNSW** is the modern default (no training step,
  good recall/latency); the schema creates
  `USING hnsw (embedding vector_cosine_ops)`. The operator class must match the
  distance operator used in queries.
- **Exact vs approximate:** for a small corpus you could scan all vectors
  exactly; HNSW is what makes the same code scale.

Storage is Postgres + pgvector (`label_chunks`, `create_schema`, `upsert_chunks`
in `src/bipacksedel/store.py`).

## 5. Retrieval controls

Three knobs turn raw nearest-neighbor search into usable evidence:

- **top-k**: how many chunks to return. Small `k` risks missing the answer;
  large `k` adds distractors and tokens.
- **Metadata filters**: restrict by field, e.g. `drug_name`, to cut the search
  space and prevent cross-drug confusion. See the optional `drug` filter.
- **Similarity threshold**: if the best score is below a cutoff, there is
  **no supporting evidence** and the system should refuse rather than let the
  model hallucinate. This is the `supported` flag
  (`is_supported` in `src/bipacksedel/store.py`), default threshold `0.7`.

### Grounding and refusal

Grounding means answers must be backed by retrieved text and **cite** it.
Refusal means saying "not found in labels" when `supported` is false. Both are
prompt/contract concerns: the MCP tool docstrings tell the client to cite
returned `chunk_id`s and to reply exactly `"not found in labels"` when
`supported` is false (`src/bipacksedel/server.py`). A retriever without a
refusal path will answer confidently from irrelevant chunks.

## 6. Why MCP here

The Model Context Protocol (MCP) standardizes how a model calls external tools.
Exposing retrieval as MCP tools (`search_labels`, `get_section`, `list_drugs`)
means any MCP-capable client can use the same grounded retrieval. Because the
client's model generates the answer, retrieval is a clean, testable unit that
can be evaluated **without** invoking any LLM.

## 7. Evaluating RAG

RAG has two failure axes, bad retrieval and bad generation, and they must be
measured separately. This repo measures **retrieval**, which is where most RAG
quality is decided, using `evals/questions.jsonl` and `evals/run.py`.

Metrics (retrieval):

- **recall@k**: fraction of answerable questions whose expected evidence is in
  the top-k. Measures "did we fetch the answer at all?"
- **MRR** (mean reciprocal rank): averages `1/rank` of the first relevant
  result. Rewards ranking the answer near the top.
- **Content relevance**: a hit when a top-k chunk is from the expected drug
  **and contains the expected answer text** (`key_phrases`). Comparable across
  chunking strategies, since it does not require section metadata.
- **Exact-section recall**: a hit only when the expected *section* is present.
  This isolates a capability only structure-aware chunking can express; fixed
  chunking discards the section label by design.
- **Refusal accuracy**: fraction of unanswerable questions correctly refused
  (`supported == false`). Without it, a system that always answers looks good.
- **False-refusal rate**: fraction of answerable questions wrongly refused;
  the cost of a threshold set too high. Reported together with refusal accuracy
  so the threshold is a trade-off, not a free win.
- **Latency**: per-query wall-clock (printed, not committed, since it varies).

The eval harness calls the retrieval function **directly**, with no LLM, so it
is cheap, fast, and repeatable. A comparison matrix varies chunking strategy,
`k`, and threshold on/off, and writes a deterministic Markdown table into the
README.

## 8. How this repository maps the concepts

| Concept | Where |
|---|---|
| Corpus / ingestion | `ingest.py` (`fetch_label`, `DRUGS`, `data/raw/`) |
| Chunking (fixed vs section-aware, overlap) | `chunk.py` (`chunk_label`, `_windows`) |
| Embeddings (local bi-encoder, 384-dim) | `embed.py` (`embed_texts`, `EMBED_DIM`) |
| Vector store + ANN index | `store.py` (`create_schema`, `upsert_chunks`) |
| Similarity search + filters | `store.py` (`search`) |
| Threshold / refusal signal | `store.py` (`is_supported`, `similarity_threshold`) |
| Grounding + citation contract | `server.py` (tool docstrings) |
| MCP tool surface | `server.py` (`search_labels`, `get_section`, `list_drugs`) |
| Retrieval evaluation | `evals/run.py`, `evals/questions.jsonl`, `evals/results.md` |

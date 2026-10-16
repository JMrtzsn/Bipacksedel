# drug-label-mcp

Grounded semantic retrieval over public FDA neurology and psychiatry drug labels.

```text
openFDA -> cached JSON -> section/fixed chunks -> embeddings -> PostgreSQL/pgvector
                                                               ^
LLM client <---------------- MCP tools -------------------------+
```

This is a demonstration over public FDA labels, not medical advice. It is not a substitute for a clinician or the current official prescribing information.

See [`docs/rag.md`](docs/rag.md) for the retrieval-augmented generation concepts behind this pipeline and how each maps to the code.

## Setup

```sh
uv sync
docker compose up -d
uv run python -m drug_label_mcp.ingest
uv run python evals/run.py
```

No credentials are required. The local `BAAI/bge-small-en-v1.5` model downloads on first use.

Run the stdio server with `uv run python -m drug_label_mcp.server`. An MCP client configuration should use command `uv` and arguments `run`, `python`, `-m`, `drug_label_mcp.server`, with this directory as its working directory. Inspect it directly:

```sh
npx @modelcontextprotocol/inspector --cli uv run python -m drug_label_mcp.server --method tools/list
```

## Evaluation results

<!-- RESULTS_START -->
| Chunking | k | Threshold | Content hit@k | Content MRR | Exact section recall@k* | Exact section MRR* | Refusal accuracy | False refusal rate |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| section-aware | 3 | on | 0.938 | 0.792 | 1.000 | 0.927 | 0.750 | 0.000 |
| section-aware | 3 | off | 0.938 | 0.792 | 1.000 | 0.927 | N/A | N/A |
| section-aware | 8 | on | 1.000 | 0.799 | 1.000 | 0.927 | 0.750 | 0.000 |
| section-aware | 8 | off | 1.000 | 0.799 | 1.000 | 0.927 | N/A | N/A |
| fixed | 3 | on | 0.812 | 0.688 | 0.000 | 0.000 | 0.750 | 0.000 |
| fixed | 3 | off | 0.812 | 0.688 | 0.000 | 0.000 | N/A | N/A |
| fixed | 8 | on | 0.875 | 0.703 | 0.000 | 0.000 | 0.750 | 0.000 |
| fixed | 8 | off | 0.875 | 0.703 | 0.000 | 0.000 | N/A | N/A |

*Exact section metrics require section metadata and are a section-aware capability; content metrics are comparable across both chunking strategies. Threshold-off rows show N/A because they cannot express refusal.
<!-- RESULTS_END -->

## Next steps

- Add reranking when measured precision warrants its latency.
- Add hybrid BM25 when semantic retrieval misses exact terminology.
- Add an LLM judge for answer faithfulness when answer generation enters scope.

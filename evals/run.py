import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bipacksedel.store import is_supported, search, similarity_threshold  # noqa: E402


def calculate_metrics(
    questions: list[dict[str, object]], outcomes: list[dict[str, object]]
) -> dict[str, float | None]:
    answerable = 0
    exact_hits = 0
    exact_reciprocal_rank = 0.0
    content_hits = 0
    content_reciprocal_rank = 0.0
    unanswerable = 0
    refused = 0
    false_refusals = 0
    refusal_capable = False
    for question, outcome in zip(questions, outcomes, strict=True):
        supported = outcome["supported"]
        if supported is not None:
            refusal_capable = True
        if not question["answerable"]:
            unanswerable += 1
            refused += supported is False
            continue
        answerable += 1
        false_refusals += supported is False
        exact_rank = None
        content_rank = None
        for rank, result in enumerate(outcome["results"], 1):
            drug_matches = result["drug_name"].lower() == str(question["expected_drug"]).lower()
            if (
                exact_rank is None
                and drug_matches
                and result["section"] == question["expected_section"]
            ):
                exact_rank = rank
            if (
                content_rank is None
                and drug_matches
                and any(
                    str(phrase).lower() in str(result["text"]).lower()
                    for phrase in question["key_phrases"]
                )
            ):
                content_rank = rank
            if exact_rank is not None and content_rank is not None:
                break
        if exact_rank is not None:
            exact_hits += 1
            exact_reciprocal_rank += 1 / exact_rank
        if content_rank is not None:
            content_hits += 1
            content_reciprocal_rank += 1 / content_rank
    return {
        "exact_recall": exact_hits / answerable if answerable else 0.0,
        "exact_mrr": exact_reciprocal_rank / answerable if answerable else 0.0,
        "content_hit": content_hits / answerable if answerable else 0.0,
        "content_mrr": content_reciprocal_rank / answerable if answerable else 0.0,
        "refusal_accuracy": (refused / unanswerable if unanswerable else 0.0)
        if refusal_capable
        else None,
        "false_refusal_rate": (false_refusals / answerable if answerable else 0.0)
        if refusal_capable
        else None,
    }


def _metric(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.3f}"


def run() -> None:
    questions = [
        json.loads(line) for line in (ROOT / "evals/questions.jsonl").read_text().splitlines()
    ]
    rows = []
    for strategy in ("section-aware", "fixed"):
        for k in (3, 8):
            for threshold_enabled in (True, False):
                outcomes = []
                latencies = []
                for question in questions:
                    start = time.perf_counter()
                    results = search(str(question["question"]), k, strategy=strategy)
                    latencies.append((time.perf_counter() - start) * 1000)
                    outcomes.append(
                        {
                            "results": results,
                            "supported": is_supported(results, similarity_threshold)
                            if threshold_enabled
                            else None,
                        }
                    )
                metrics = calculate_metrics(questions, outcomes)
                row = (
                    strategy,
                    k,
                    "on" if threshold_enabled else "off",
                    metrics["content_hit"],
                    metrics["content_mrr"],
                    metrics["exact_recall"],
                    metrics["exact_mrr"],
                    metrics["refusal_accuracy"],
                    metrics["false_refusal_rate"],
                    sum(latencies) / len(latencies),
                )
                rows.append(row)
                print(
                    f"{strategy} k={k} threshold={row[2]} content_hit@k={row[3]:.3f} "
                    f"content_MRR={row[4]:.3f} exact_recall@k={row[5]:.3f} "
                    f"refusal={_metric(row[7])} false_refusal={_metric(row[8])} "
                    f"latency={row[9]:.1f}ms"
                )
    table = [
        "| Chunking | k | Threshold | Content hit@k | Content MRR | Exact section recall@k* | "
        "Exact section MRR* | Refusal accuracy | False refusal rate |",
        "|---|---:|:---:|---:|---:|---:|---:|---:|---:|",
    ]
    table.extend(
        f"| {s} | {k} | {t} | {ch:.3f} | {cm:.3f} | {er:.3f} | {em:.3f} | "
        f"{_metric(ra)} | {_metric(fr)} |"
        for s, k, t, ch, cm, er, em, ra, fr, _ in rows
    )
    table.append(
        "\n*Exact section metrics require section metadata and are a section-aware capability; "
        "content metrics are comparable across both chunking strategies. Threshold-off rows show "
        "N/A because they cannot express refusal."
    )
    rendered = "\n".join(table)
    (ROOT / "evals/results.md").write_text(rendered + "\n")
    readme_path = ROOT / "README.md"
    readme = readme_path.read_text()
    start, end = "<!-- RESULTS_START -->", "<!-- RESULTS_END -->"
    before, remainder = readme.split(start, 1)
    _, after = remainder.split(end, 1)
    readme_path.write_text(f"{before}{start}\n{rendered}\n{end}{after}")


if __name__ == "__main__":
    run()

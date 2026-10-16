from evals import run as eval_run
from evals.run import calculate_metrics


def test_generated_artifacts_exclude_latency(tmp_path, monkeypatch, capsys):
    evals = tmp_path / "evals"
    evals.mkdir()
    (evals / "questions.jsonl").write_text(
        '{"question":"unknown","answerable":false,"expected_drug":null,"expected_section":null}\n'
    )
    (tmp_path / "README.md").write_text(
        "before\n<!-- RESULTS_START -->\nold\n<!-- RESULTS_END -->\nafter\n"
    )
    monkeypatch.setattr(eval_run, "ROOT", tmp_path)
    monkeypatch.setattr(eval_run, "search", lambda *args, **kwargs: [])
    monkeypatch.setattr(eval_run, "is_supported", lambda *args: False)

    eval_run.run()

    assert "Mean latency (ms)" not in (evals / "results.md").read_text()
    assert "Mean latency (ms)" not in (tmp_path / "README.md").read_text()
    assert "latency=" in capsys.readouterr().out


def test_exact_content_and_threshold_metrics():
    questions = [
        {
            "answerable": True,
            "expected_drug": "alpha",
            "expected_section": "warnings",
            "key_phrases": ["serious rash"],
        },
        {
            "answerable": True,
            "expected_drug": "beta",
            "expected_section": "dosage",
            "key_phrases": ["once daily"],
        },
        {"answerable": False, "expected_drug": None, "expected_section": None},
    ]
    outcomes = [
        {
            "results": [
                {
                    "drug_name": "alpha",
                    "section": "warnings",
                    "text": "May cause a SERIOUS RASH.",
                }
            ],
            "supported": True,
        },
        {
            "results": [
                {"drug_name": "other", "section": "dosage", "text": "once daily"},
                {"drug_name": "beta", "section": "dosage", "text": "Take once daily."},
            ],
            "supported": False,
        },
        {"results": [], "supported": False},
    ]

    metrics = calculate_metrics(questions, outcomes)

    assert metrics == {
        "exact_recall": 1.0,
        "exact_mrr": 0.75,
        "content_hit": 1.0,
        "content_mrr": 0.75,
        "refusal_accuracy": 1.0,
        "false_refusal_rate": 0.5,
    }


def test_fixed_chunk_can_satisfy_content_relevance():
    metrics = calculate_metrics(
        [
            {
                "answerable": True,
                "expected_drug": "alpha",
                "expected_section": "warnings",
                "key_phrases": ["serious rash"],
            }
        ],
        [
            {
                "results": [
                    {"drug_name": "alpha", "section": "mixed", "text": "A serious rash may occur."}
                ],
                "supported": True,
            }
        ],
    )

    assert metrics["content_hit"] == 1.0
    assert metrics["content_mrr"] == 1.0
    assert metrics["exact_recall"] == 0.0


def test_refusal_accuracy_handles_no_unanswerable_questions():
    metrics = calculate_metrics(
        [
            {
                "answerable": True,
                "expected_drug": "alpha",
                "expected_section": "warnings",
                "key_phrases": ["rash"],
            }
        ],
        [{"results": [], "supported": False}],
    )

    assert metrics["refusal_accuracy"] == 0.0
    assert metrics["false_refusal_rate"] == 1.0


def test_false_refusal_rate_handles_no_answerable_questions():
    metrics = calculate_metrics(
        [{"answerable": False, "expected_drug": None, "expected_section": None}],
        [{"results": [], "supported": False}],
    )

    assert metrics["refusal_accuracy"] == 1.0
    assert metrics["false_refusal_rate"] == 0.0

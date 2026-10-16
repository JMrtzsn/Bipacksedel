from drug_label_mcp.chunk import chunk_label

LABEL = {
    "id": "label-1",
    "openfda": {"generic_name": ["example"]},
    "indications_and_usage": ["A" * 700 + "B" * 700],
    "contraindications": ["Never use with example allergy."],
}


def test_every_chunk_has_metadata_and_deterministic_id():
    first = chunk_label(LABEL, "section-aware", size=1200, overlap=200)
    second = chunk_label(LABEL, "section-aware", size=1200, overlap=200)

    assert [chunk["chunk_id"] for chunk in first] == [chunk["chunk_id"] for chunk in second]
    assert all(
        {"chunk_id", "drug_name", "label_id", "section", "text"} <= chunk.keys() for chunk in first
    )


def test_long_sections_overlap():
    chunks = chunk_label(LABEL, "section-aware", size=1200, overlap=200)
    indication_chunks = [c for c in chunks if c["section"] == "indications_and_usage"]

    assert len(indication_chunks) == 2
    assert indication_chunks[0]["text"][-200:] == indication_chunks[1]["text"][:200]


def test_chunking_stops_after_window_reaches_end():
    label = {**LABEL, "indications_and_usage": ["A" * 1700]}
    chunks = chunk_label(label, "section-aware", size=1000, overlap=200)
    indication_chunks = [c for c in chunks if c["section"] == "indications_and_usage"]

    assert [len(chunk["text"]) for chunk in indication_chunks] == [1000, 900]


def test_section_aware_and_fixed_size_differ():
    section_chunks = chunk_label(LABEL, "section-aware", size=1200, overlap=200)
    fixed_chunks = chunk_label(LABEL, "fixed", size=1200, overlap=200)

    assert [(c["section"], c["text"]) for c in section_chunks] != [
        (c["section"], c["text"]) for c in fixed_chunks
    ]

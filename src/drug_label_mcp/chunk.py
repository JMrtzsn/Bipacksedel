import hashlib

SECTIONS = (
    "indications_and_usage",
    "dosage_and_administration",
    "warnings",
    "contraindications",
    "adverse_reactions",
    "drug_interactions",
)


def _windows(text: str, size: int, overlap: int) -> list[str]:
    if size <= overlap or overlap < 0:
        raise ValueError("size must be greater than overlap, and overlap must be non-negative")
    windows = []
    for start in range(0, len(text), size - overlap):
        windows.append(text[start : start + size])
        if start + size >= len(text):
            break
    return windows


def _chunk(
    drug_name: str, label_id: str, section: str, text: str, position: int, strategy: str
) -> dict[str, str]:
    value = f"{strategy}\0{label_id}\0{section}\0{position}\0{text}"
    return {
        "chunk_id": hashlib.sha256(value.encode()).hexdigest()[:24],
        "drug_name": drug_name,
        "label_id": label_id,
        "section": section,
        "text": text,
    }


def chunk_label(
    label: dict[str, object], strategy: str = "section-aware", size: int = 1200, overlap: int = 200
) -> list[dict[str, str]]:
    label_id = str(label.get("id") or label.get("set_id") or "unknown")
    openfda = label.get("openfda")
    generic_names = openfda.get("generic_name", []) if isinstance(openfda, dict) else []
    drug_name = str(generic_names[0]).lower() if generic_names else "unknown"
    sections: list[tuple[str, str]] = []
    for section in SECTIONS:
        values = label.get(section)
        if section == "warnings" and not values:
            values = label.get("warnings_and_cautions")
        if isinstance(values, list):
            text = "\n\n".join(str(value).strip() for value in values if str(value).strip())
            if text:
                sections.append((section, text))

    if strategy == "section-aware":
        return [
            _chunk(drug_name, label_id, section, text, position, strategy)
            for section, section_text in sections
            for position, text in enumerate(_windows(section_text, size, overlap))
        ]
    if strategy == "fixed":
        text = "\n\n".join(f"{section}: {value}" for section, value in sections)
        return [
            _chunk(drug_name, label_id, "mixed", value, position, strategy)
            for position, value in enumerate(_windows(text, size, overlap))
        ]
    raise ValueError(f"unknown chunk strategy: {strategy}")

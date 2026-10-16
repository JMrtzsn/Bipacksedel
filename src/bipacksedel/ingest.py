import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

from bipacksedel.chunk import chunk_label
from bipacksedel.embed import embed_texts
from bipacksedel.store import connect, create_schema, upsert_chunks

DRUGS = [
    "levetiracetam",
    "lamotrigine",
    "valproate",
    "carbamazepine",
    "phenytoin",
    "gabapentin",
    "pregabalin",
    "topiramate",
    "ethosuximide",
    "oxcarbazepine",
    "lacosamide",
    "zonisamide",
    "clonazepam",
    "diazepam",
    "lorazepam",
    "sertraline",
    "fluoxetine",
    "escitalopram",
    "citalopram",
    "paroxetine",
    "venlafaxine",
    "duloxetine",
    "bupropion",
    "mirtazapine",
    "trazodone",
    "quetiapine",
    "olanzapine",
    "risperidone",
    "aripiprazole",
    "clozapine",
    "haloperidol",
    "lithium",
    "methylphenidate",
    "amphetamine",
    "atomoxetine",
    "donepezil",
    "memantine",
    "rivastigmine",
    "galantamine",
    "levodopa",
    "pramipexole",
    "ropinirole",
    "selegiline",
    "rasagiline",
    "amantadine",
    "sumatriptan",
    "zolmitriptan",
    "propranolol",
    "zolpidem",
    "modafinil",
    "buspirone",
]
RAW_DIR = Path("data/raw")


def fetch_label(drug: str) -> dict[str, object] | None:
    cache = RAW_DIR / f"{drug}.json"
    if cache.exists():
        payload = json.loads(cache.read_text())
    else:
        query = urllib.parse.urlencode({"search": f'openfda.generic_name:"{drug}"', "limit": 1})
        try:
            with urllib.request.urlopen(
                f"https://api.fda.gov/drug/label.json?{query}", timeout=30
            ) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(payload))
    results = payload.get("results", [])
    if not isinstance(results, list) or not results:
        return None
    label = results[0]
    label.setdefault("openfda", {})["generic_name"] = [drug]
    return label


def ingest(strategies: list[str]) -> None:
    total_chunks = 0
    drugs_loaded = 0
    section_counts: Counter[str] = Counter()
    with connect() as connection:
        create_schema(connection)
        for drug in DRUGS:
            label = fetch_label(drug)
            if not label:
                print(f"{drug}: no label found")
                continue
            drug_total = 0
            for strategy in strategies:
                chunks = chunk_label(label, strategy)
                if chunks:
                    upsert_chunks(
                        connection, chunks, embed_texts([c["text"] for c in chunks]), strategy
                    )
                drug_total += len(chunks)
                total_chunks += len(chunks)
                section_counts.update(c["section"] for c in chunks)
            drugs_loaded += 1
            print(f"{drug}: {drug_total} chunks")
            time.sleep(0.1)
    print(
        f"Ingested {drugs_loaded}/{len(DRUGS)} drugs, {total_chunks} chunks, "
        f"sections={dict(sorted(section_counts.items()))}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", choices=("section-aware", "fixed", "both"), default="both")
    choice = parser.parse_args().strategy
    ingest(["section-aware", "fixed"] if choice == "both" else [choice])


if __name__ == "__main__":
    main()

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from drug_label_mcp.embed import EMBED_DIM, embed_texts

DATABASE_DSN = "postgresql://postgres:postgres@localhost:5432/druglabels"
similarity_threshold = 0.7


def connect() -> psycopg.Connection:
    connection = psycopg.connect(DATABASE_DSN)
    connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
    connection.commit()
    register_vector(connection)
    return connection


def create_schema(connection: psycopg.Connection) -> None:
    connection.execute(
        f"""CREATE TABLE IF NOT EXISTS label_chunks (
            chunk_id text PRIMARY KEY,
            strategy text NOT NULL,
            drug_name text NOT NULL,
            label_id text NOT NULL,
            section text NOT NULL,
            text text NOT NULL,
            embedding vector({EMBED_DIM}) NOT NULL
        )"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS label_chunks_embedding_idx ON label_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    connection.commit()


def upsert_chunks(
    connection: psycopg.Connection,
    chunks: list[dict[str, str]],
    embeddings: list[list[float]],
    strategy: str,
) -> None:
    rows = [
        (
            chunk["chunk_id"],
            strategy,
            chunk["drug_name"],
            chunk["label_id"],
            chunk["section"],
            chunk["text"],
            embedding,
        )
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]
    with connection.cursor() as cursor:
        cursor.executemany(
            """INSERT INTO label_chunks
            (chunk_id, strategy, drug_name, label_id, section, text, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (chunk_id) DO UPDATE SET
            embedding = EXCLUDED.embedding, text = EXCLUDED.text""",
            rows,
        )
    connection.commit()


def search(
    query: str,
    k: int,
    drug: str | None = None,
    threshold: float | None = None,
    strategy: str = "section-aware",
) -> list[dict[str, object]]:
    target = Vector(embed_texts([query])[0])
    filters = ["strategy = %s"]
    params: list[object] = [target, strategy]
    if drug:
        filters.append("lower(drug_name) = lower(%s)")
        params.append(drug)
    params.append(k)
    sql = f"""SELECT chunk_id, drug_name, section, 1 - (embedding <=> %s) AS score, text
        FROM label_chunks WHERE {" AND ".join(filters)} ORDER BY embedding <=> %s LIMIT %s"""
    params.insert(-1, target)
    with connect() as connection:
        rows = connection.execute(sql, tuple(params)).fetchall()
    results = [
        {
            "chunk_id": row[0],
            "drug_name": row[1],
            "section": row[2],
            "score": row[3],
            "text": row[4],
        }
        for row in rows
    ]
    if threshold is not None:
        return results if is_supported(results, threshold) else []
    return results


def is_supported(results: list[dict[str, object]], threshold: float = similarity_threshold) -> bool:
    return bool(results and float(results[0]["score"]) >= threshold)


def get_section(drug: str, section: str) -> list[dict[str, str]]:
    with connect() as connection:
        rows = connection.execute(
            """SELECT chunk_id, drug_name, section, text FROM label_chunks
            WHERE strategy = 'section-aware' AND lower(drug_name) = lower(%s)
            AND lower(section) = lower(%s) ORDER BY chunk_id""",
            (drug, section),
        ).fetchall()
    return [
        dict(zip(("chunk_id", "drug_name", "section", "text"), row, strict=True)) for row in rows
    ]


def list_drugs() -> list[str]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT DISTINCT drug_name FROM label_chunks ORDER BY drug_name"
        ).fetchall()
    return [row[0] for row in rows]

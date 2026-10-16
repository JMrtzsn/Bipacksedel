EMBED_DIM = 384


def embed_texts(texts: list[str]) -> list[list[float]]:
    from fastembed import TextEmbedding

    return [vector.tolist() for vector in TextEmbedding().embed(texts)]

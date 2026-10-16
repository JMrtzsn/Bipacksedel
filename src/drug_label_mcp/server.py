from mcp.server import MCPServer

from drug_label_mcp import store

mcp = MCPServer("drug-label-mcp")


@mcp.tool()
def search_labels(query: str, k: int = 5, drug: str | None = None) -> dict[str, object]:
    """Search FDA label evidence.

    Cite returned chunk_ids; if supported is false, reply exactly "not found in labels".
    """
    chunks = store.search(query, k, drug)
    return {"chunks": chunks, "supported": store.is_supported(chunks)}


@mcp.tool()
def get_section(drug: str, section: str) -> list[dict[str, str]]:
    """Get a complete label section.

    Cite every used chunk_id; if empty, reply exactly "not found in labels".
    """
    return store.get_section(drug, section)


@mcp.tool()
def list_drugs() -> list[str]:
    """List covered drugs.

    Use only these names; if a drug is absent, reply exactly "not found in labels".
    """
    return store.list_drugs()


if __name__ == "__main__":
    mcp.run()

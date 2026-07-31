from typing import Any
from mcp.server.fastmcp import FastMCP
from prod_assistance.retriever.retriever import Retriever
from langchain_community.tools import DuckDuckGoSearchRun

mcp = FastMCP("hybrid_search")

retriever_obj = Retriever()

duckduckgo = DuckDuckGoSearchRun()

def format_docs(docs) -> str:
    """Format the retrieved documents into readable chunks"""
    if not docs:
        return "No local result found"
    formatted_chunks = []
    for d in docs:
        meta = d.metadata or {}
        formatted = (
            f"Title: {meta.get('product_title', 'N/A')}\n"
            f"Price: {meta.get('price', 'N/A')}\n"
            f"Rating: {meta.get('rating', 'N/A')}\n"
            f"Reviews:\n{d.page_content.strip()}"
        )
        formatted_chunks.append(formatted)
    return "\n\n---\n\n".join(formatted_chunks)

@mcp.tool()
async def get_product_info(query: str) -> str:
    """Retrieve prodyct information for a given query from local retriever"""
    try:
        docs = retriever_obj.call_retriever(query)
        context = format_docs(docs)
        if not context.strip():
            return "No local result found"
        return context

    except Exception as e:
        return f"Error retrieving product info: {str(e)}"


@mcp.tool()
async def web_search(query: str) -> str:
    """Search the web using DuckDuckGo if retriever has no results"""
    try:
        return duckduckgo.run(query)
    except Exception as e:
        return f"Error performing web search: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")

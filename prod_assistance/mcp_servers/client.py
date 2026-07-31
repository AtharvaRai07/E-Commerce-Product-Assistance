import asyncio
import sys
from langchain_mcp_adapters.client import MultiServerMCPClient

async def main():
    client = MultiServerMCPClient({
        "hybrid_search": {
            "command": "python",
            "args": [
                r"D:\E-Commerce Product Assistance\ecomm-prod-assitance\prod_assistance\mcp_servers\product_search_server.py"
            ],
            "transport": "stdio"
        }
    })

    tools = await client.get_tools()
    print(f"Available tools: {[t.name for t in tools]}")

    retriever_tool = next(t for t in tools if t.name == "get_product_info")
    web_tool = next(t for t in tools if t.name == "web_search")


    query = "What are the features of Iphone 17pro?"
    retriever_result = await retriever_tool.ainvoke({"query": query})
    print(f"\nRetriever result:\n {retriever_result}")

    if not retriever_result or "No local result found" in retriever_result:
        web_result = await web_tool.ainvoke({"query": query})
        print(f"\nWeb search result:\n {web_result}")


if __name__ == "__main__":
    asyncio.run(main())

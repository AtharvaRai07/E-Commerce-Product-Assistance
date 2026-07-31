import asyncio
from typing import Annotated, Sequence, TypedDict, Literal
from langchain.agents import AgentState
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_mcp_adapters.client import MultiServerMCPClient

from prod_assistance.prompt_library.prompts import PROMPT_REGISTRY, PromptType
from prod_assistance.retriever.retriever import Retriever
from prod_assistance.utils.model_loader import ModelLoader

class AgenticRAG:
    """Agentic RAG pipeline using LangGraph + MCP (Retriever + WebSearch)"""

    class AgentState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]

    def __init__(self):
        self.retriever_obj = Retriever()
        self.model_loader = ModelLoader()
        self.llm = self.model_loader.load_llm()
        self.checkpointer = MemorySaver()

        self.mcp_client = MultiServerMCPClient({
                "hybrid_search": {
                    "command": "python",
                    "args": [
                        r"D:\E-Commerce Product Assistance\ecomm-prod-assitance\prod_assistance\mcp_servers\product_search_server.py"
                    ],
                    "transport": "stdio"
                }
            })

        self.mcp_tools = []
        self.app = None

    async def initialize(self):
        """Asynchronously warm up client, fetch tools, and compile graph."""
        self.mcp_tools = await self.mcp_client.get_tools()
        workflow = self._build_workflow()
        self.app = workflow.compile(checkpointer=self.checkpointer)

    async def close(self):
        """Cleanly close open MCP background processes during server shutdown."""
        if hasattr(self.mcp_client, 'close'):
            await self.mcp_client.close()
        elif hasattr(self.mcp_client, 'aclose'):
            await self.mcp_client.aclose()

    def _format_docs(self, docs) -> str:
        if not docs:
            return "No relevant documents found."
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

    def _ai_assistance(self, state: AgentState):
        """Decide whether to call retriever or just answer directly"""
        print("--- CALL ASSISTANCE ---")
        messages = state['messages']
        last_message = messages[-1].content

        if any(word in last_message.lower() for word in ['price','review','product']):
            return {"messages": [AIMessage(content="TOOL: retriever")]}
        else:
            prompt = ChatPromptTemplate.from_template(
                "You are a helpful assistant. Answer the user directly.\n\nQuestion: {question}\nAnswer:"
            )
            chain = prompt | self.llm | StrOutputParser()
            response = chain.invoke({"question": last_message})
            return {"messages": [AIMessage(content=response)]}

    async def _vector_retriever(self, state: AgentState):
        """Fetch product info from vector DB natively async."""
        print("--- RETRIEVER ---")
        query = state['messages'][-1].content
        tool = next(t for t in self.mcp_tools if t.name == "get_product_info")

        result = await tool.ainvoke({"query": query})
        context = self._format_docs(result)
        return {"messages": [AIMessage(content=context)]}

    async def _web_search(self, state: AgentState):
        """Web search natively async."""
        print("--- WEB SEARCH ---")
        query = state['messages'][-1].content
        tool = next(t for t in self.mcp_tools if t.name == "web_search")

        result = await tool.ainvoke({"query": query})
        context = result if result else "No data found from web"
        return {"messages": [AIMessage(content=context)]}

    def _grade_document(self, state: AgentState) -> Literal["generator","rewriter"]:
        """Grade docs relevance"""
        print("--- GRADER ---")
        question = state["messages"][0].content
        docs = state["messages"][-1].content

        prompt = PromptTemplate(
            template="""You are a grader. Question: {question}\nDocs: {docs}\n
            Are docs relevant to the question? Answer yes or no.""",
            input_variables=["question", "docs"],
        )

        chain = prompt | self.llm | StrOutputParser()
        score = chain.invoke({"question": question, "docs": docs})
        return "generator" if "yes" in score.lower() else "rewriter"

    def _generate(self, state: AgentState):
        """Generate final answer with docs"""
        print("--- GENERATE ---")
        question = state['messages'][0].content
        docs = state['messages'][-1].content
        prompt = ChatPromptTemplate.from_template(
            PROMPT_REGISTRY[PromptType.PRODUCT_BOT].template
        )

        chain = prompt | self.llm | StrOutputParser()
        response = chain.invoke({"context": docs, "question": question})
        return {"messages": [AIMessage(content=response)]}

    def _rewrite(self, state: AgentState):
        """Rewrite Bad query"""
        print("--- REWRITE ---")
        question = state['messages'][0].content
        new_q = self.llm.invoke(
            [HumanMessage(content=f"Rewrite the query to be clearer: {question}")]
        )
        return {"messages": [AIMessage(content=new_q.content)]}

    def _build_workflow(self):
        workflow = StateGraph(self.AgentState)

        workflow.add_node("Assistance", self._ai_assistance)
        workflow.add_node("Retriever", self._vector_retriever)
        workflow.add_node("WebSearch", self._web_search)
        workflow.add_node("Generator", self._generate)
        workflow.add_node("Rewriter", self._rewrite)

        workflow.add_edge(START, "Assistance")
        workflow.add_conditional_edges(
            "Assistance",
            lambda state: "Retriever" if "TOOL" in state["messages"][-1].content else END,
            {"Retriever": "Retriever", END: END}
        )
        workflow.add_conditional_edges(
            "Retriever",
            self._grade_document,
            {"generator": "Generator", "rewriter": "Rewriter"}
        )

        workflow.add_edge("Generator", END)
        workflow.add_edge("Rewriter", "WebSearch")
        workflow.add_edge("WebSearch", "Assistance")
        return workflow

    async def run(self, query: str, thread_id: str = "default_thread") -> str:
        """Run the Agentic RAG workflow asynchronously"""
        if self.app is None:
            raise RuntimeError("AgenticRAG not initialized. Call await initialize() first.")

        result = await self.app.ainvoke(
            {"messages": [HumanMessage(content=query)]},
            config={"configurable": {"thread_id": thread_id}}
        )
        return result['messages'][-1].content

if __name__ == "__main__":
    async def main():
        rag_agent = AgenticRAG()
        await rag_agent.initialize()
        answer = await rag_agent.run("What is the price of iPhone 15?")
        print("\nFinal Answer:\n", answer)
        await rag_agent.close()

    asyncio.run(main())

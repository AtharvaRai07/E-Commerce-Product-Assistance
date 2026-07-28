from typing import Annotated, Sequence, TypedDict, Literal
from langchain.agents import AgentState
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from prod_assistance.prompt_library.prompts import PROMPT_REGISTRY, PromptType
from prod_assistance.retriever.retriever import Retriever
from prod_assistance.utils.model_loader import ModelLoader


class AgenticRAG:
    """Agentic RAG Workflow for Product Assistance"""

    class AgentState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]

    def __init__(self):
        self.retriever_obj = Retriever()
        self.model_loader = ModelLoader()
        self.llm = self.model_loader.load_llm()
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()

    ################### Helper Functions ##################
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
        print("--- CALL ASSIATANCE ---")
        messages = state['messages']
        last_message = messages[-1].content

        if any(word in last_message.lower() for word in ['price','review','product']):
            return {"messages": [HumanMessage(content="TOOL: retriever")]}
        else:
            prompt = ChatPromptTemplate.from_template(
                "You are a helpful assistant. Answer the user directly.\n\nQuestion: {question}\nAnswer:"
            )
            chain = prompt | self.llm | StrOutputParser()
            response = chain.invoke({"question": last_message})
            return {"messages": [HumanMessage(content=response)]}

    def _vector_retriever(self, state: AgentState):
        """Fetch product info from vector DB."""
        print("--- RETRIEVER ---")
        query = state['messages'][-1].content
        retriever = self.retriever_obj.load_retriever()
        docs = retriever.invoke(query)
        context = self._format_docs(docs)
        return {"messages": HumanMessage(content=context)}

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
        return {"messages": [HumanMessage(content=response)]}


    def _rewrite(self, state: AgentState):
        """Rewrite Bad query"""
        print("--- REWRITE ---")
        question = state['messages'][0].content
        new_q = self.llm.invoke(
            [HumanMessage(content=f"Rewrite the query to be clearer: {question}")]
        )
        return {"messages": [HumanMessage(content=new_q.content)]}

    def _build_workflow(self):

        workflow = StateGraph(self.AgentState)
        workflow.add_node("Assistance", self._ai_assistance)
        workflow.add_node("Retriever", self._vector_retriever)
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
        workflow.add_edge("Rewriter", "Assistance")
        return workflow

    def run(self, query: str) -> str:
        "Run the Agentic RAG workflow with a given query"
        result = self.app.invoke({"messages": [HumanMessage(content=query)]})
        return result['messages'][-1].content

if __name__ == "__main__":
    rag_agent = AgenticRAG()
    answer = rag_agent.run("What is the price of iPhone 15?")
    print("\nFinal Answer:\n", answer)

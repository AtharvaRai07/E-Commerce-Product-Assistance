import os
import sys
import pathlib
from dotenv import load_dotenv
from langchain_astradb import AstraDBVectorStore
from prod_assistance.utils.model_loader import ModelLoader
from prod_assistance.utils.config_loader import load_config
from prod_assistance.evaluation.ragas_eval import evaluate_context_precision, evaluate_answer_relevancy
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import LLMChainFilter


from prod_assistance.logger import GLOBAL_LOGGER
from prod_assistance.exception.custom_exception import ProductAssistanceException

logger = GLOBAL_LOGGER

class Retriever:
    def __init__(self):
        self.model_loader = ModelLoader()
        self.config = load_config()
        self._load_env_variables()
        self.vstore = None
        self.retriever = None

    def _load_env_variables(self):
        try:
            load_dotenv()

            required_vars = ["GROQ_API_KEY", "ASTRA_DB_API_ENDPOINT", "ASTRA_DB_APPLICATION_TOKEN", "ASTRA_DB_KEYSPACE"]

            missing_vars = [var for var in required_vars if os.getenv(var) is None]

            if missing_vars:
                raise EnvironmentError(f"Missing environment variables: {missing_vars}")

            self.groq_api_key = os.getenv("GROQ_API_KEY")
            self.db_api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
            self.db_application_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
            self.db_keyspace = os.getenv("ASTRA_DB_KEYSPACE")

            logger.info("Environment variables loaded successfully.")

        except Exception as e:
            logger.error(f"Error loading environment variables: {e}")
            raise ProductAssistanceException(f"Error loading environment variables: {e}")

    def load_retriever(self):
        try:
            if not self.vstore:
                collection_name = self.config['astra_db']['collection_name']

                self.vstore = AstraDBVectorStore(
                    embedding=self.model_loader.load_embeddings(),
                    collection_name=collection_name,
                    api_endpoint=self.db_api_endpoint,
                    token=self.db_application_token,
                    namespace=self.db_keyspace
                )

            if not self.retriever:
                top_k = self.config['retriever']['top_k'] if "retriever" in self.config else 3
                search_type = self.config['retriever']['search_type'] if "retriever" in self.config else "similarity"

                self.retriever = self.vstore.as_retriever(search_kwargs={
                    "search_type": "mmr",
                    "k": top_k,
                    "fetch_k": 20,
                    "lambda_mult": 0.7,
                    "score_threshold": 0.6
                })

                # llm = self.model_loader.load_llm()
                # compressor = LLMChainFilter.from_llm(llm)

                # self.retriever = ContextualCompressionRetriever(
                #     base_compressor=compressor,
                #     base_retriever=mmr_retriever
                # )
                logger.info(f"Retriever loaded with top_k={top_k}, search_type={search_type}, lambda_mult=0.7, score_threshold=0.6.")

        except Exception as e:
            logger.error(f"Error loading retriever: {e}")
            raise ProductAssistanceException(f"Error loading retriever: {e}")

    def call_retriever(self, query):
        try:
            if not self.retriever:
                self.load_retriever()

            results = self.retriever.invoke(query)

            logger.info(f"Retriever called successfully for query: {query} with results: {results}")

            return results

        except Exception as e:
            logger.error(f"Error calling retriever: {e}")
            raise ProductAssistanceException(f"Error calling retriever: {e}")

if __name__ == "__main__":
    retriever_obj = Retriever()
    user_query = "What are the features of Iphone 17pro"
    retrieved_docs = retriever_obj.call_retriever(user_query)
    print("\n\n--\n\n", retrieved_docs)
    def _format_docs(docs) -> str:
        formatted_chunks = []

        if not docs:
            return "No relevant documents found."

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

    retrieved_context = [_format_docs(retrieved_docs) for doc in retrieved_docs]

    response="iphone 16 plus, iphone 16, iphone 15 are best phones under 1,00,000 INR."

    context_score = evaluate_answer_relevancy(user_query, response, retrieved_context)
    relevancy_score = evaluate_context_precision(user_query, response, retrieved_context)

    print("\n--- Evaluation Metrics ---")
    print("Context Precision Score:", context_score)
    print("Response Relevancy Score:", relevancy_score)

import os
import sys
import pathlib
from dotenv import load_dotenv
from langchain_astradb import AstraDBVectorStore
from prod_assistance.utils.model_loader import ModelLoader
from prod_assistance.utils.config_loader import load_config

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
                    keyspace=self.db_keyspace
                )

            if not self.retriever:
                top_k = self.config['retriever']['top_k'] if "retriever" in self.config else 3
                search_type = self.config['retriever']['search_type'] if "retriever" in self.config else "similarity"
                self.retriever = self.vstore.as_retriever(search_kwargs={"search_type": search_type, "k": top_k})

                logger.info("Retriever loaded successfully.")

        except Exception as e:
            logger.error(f"Error loading retriever: {e}")
            raise ProductAssistanceException(f"Error loading retriever: {e}")

    def call_retriever(self, query):
        try:
            if not self.retriever:
                raise ProductAssistanceException("Retriever is not loaded. Please call load_retriever() first.")

            retriever = self.load_retriever()
            results = retriever.invoke(query)

            logger.info(f"Retriever called successfully for query: {query} with results: {results}")

            return results

        except Exception as e:
            logger.error(f"Error calling retriever: {e}")
            raise ProductAssistanceException(f"Error calling retriever: {e}")

if __name__ == "__main__":
    retriever_obj = Retriever()
    user_query = "Can you suggest some good budget laptops"
    results = retriever_obj.call_retriever(user_query)

    for idx, doc in enumerate(results):
        print(f"Result {idx + 1}: {doc.page_content} \nMetadata:\n {doc.metadata}\n ")

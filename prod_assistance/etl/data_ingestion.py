import os
import pandas as pd
from dotenv import load_dotenv
from typing import List
from langchain_core.documents import Document
from langchain_astradb import AstraDBVectorStore
from prod_assistance.utils.model_loader import ModelLoader
from prod_assistance.utils.config_loader import load_config

class DataIngestion:
    """
    Class to handle data transformation and ingestion into AstraDB vector store
    """

    def __init__(self):
        """
        Initialize enviroment variables, embedding model and set CSV file path
        """
        print("Initializing DataIngestion...")
        self.model_loader = ModelLoader()
        self._load_env_variables()
        self.csv_path = self._get_csv_path()
        self.product_data = self._load_csv()
        self.config = load_config()


    def _load_env_variables(self):
        """
        Load environment variables from .env file
        """
        load_dotenv()
        required_vars = ["COHERE_API_KEY", "ASTRA_DB_API_ENDPOINT", "ASTRA_DB_APPLICATION_TOKEN", "ASTRA_DB_KEYSPACE"]

        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

        self.cohere_api_key = os.getenv("COHERE_API_KEY")
        self.db_api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
        self.db_application_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
        self.db_keyspace = os.getenv("ASTRA_DB_KEYSPACE")

    def _get_csv_path(self):
        """
        Get the path to the CSV file containing product data
        """
        current_dir = os.getcwd()
        csv_path = os.path.join(current_dir, "data", "product_reviews.csv")

        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found at {csv_path}")

        return csv_path

    def _load_csv(self):
        """
        Load product data from csv
        """
        df = pd.read_csv(self.csv_path)
        expected_columns = {'product_id','product_title', 'rating', 'total_reviews','price', 'top_reviews'}

        if not expected_columns.issubset(set(df.columns)):
            raise ValueError(f"CSV must contain columns: {expected_columns}")

        return df

    def transform_data(self):
        """
        Transform product data into list of LangChain Document objects
        """
        product_lst = []

        for _, row in self.product_data.iterrows():
            product_entry = {
                    "product_id": row["product_id"],
                    "product_title": row["product_title"],
                    "rating": row["rating"],
                    "total_reviews": row["total_reviews"],
                    "price": row["price"],
                    "top_reviews": row["top_reviews"]
                }
            product_lst.append(product_entry)

        documents = []
        for entry in product_lst:
            metadata = {
                    "product_id": entry["product_id"],
                    "product_title": entry["product_title"],
                    "rating": entry["rating"],
                    "total_reviews": entry["total_reviews"],
                    "price": entry["price"]
            }
            doc = Document(page_content=entry["top_reviews"], metadata=metadata)
            documents.append(doc)

        print(f"Transformed {len(documents)} product entries into Document objects.")
        return documents

    def store_in_vector_db(self, documents: List[Document]):
        """
        Store documents in the vector database
        """
        collection_name = self.config["astra_db"]["collection_name"]
        vstore = AstraDBVectorStore(
            embedding=self.model_loader.load_embeddings(),
            collection_name=collection_name,
            api_endpoint=self.db_api_endpoint,
            token=self.db_application_token,
            namespace=self.db_keyspace
        )

        inserted_ids = vstore.add_documents(documents)
        print(f"Inserted {len(inserted_ids)} documents into AstraDB vector store.")
        return vstore, inserted_ids


    def run_pipeline(self):
        """
        Run the complete data ingestion pipeline
        """
        documents= self.transform_data()
        vstore, _ = self.store_in_vector_db(documents)
\

if __name__ == "__main__":
    ingestion = DataIngestion()
    ingestion.run_pipeline()


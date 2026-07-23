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
        print("Initializing DataIngestion...")

        self.model_loader = ModelLoader()
        self._load_env_variables()

        self.csv_path = self._get_csv_path()
        self.product_data = self._load_csv()

        self.config = load_config()

    def _load_env_variables(self):
        """
        Load environment variables from .env
        """
        load_dotenv()

        required_vars = [
            "COHERE_API_KEY",
            "ASTRA_DB_API_ENDPOINT",
            "ASTRA_DB_APPLICATION_TOKEN",
            "ASTRA_DB_KEYSPACE"
        ]

        missing = [var for var in required_vars if not os.getenv(var)]

        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        self.cohere_api_key = os.getenv("COHERE_API_KEY")
        self.db_api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
        self.db_application_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
        self.db_keyspace = os.getenv("ASTRA_DB_KEYSPACE")

    def _get_csv_path(self):
        """
        Locate product_reviews.csv
        """
        csv_path = os.path.join(os.getcwd(), "data", "product_reviews.csv")

        if not os.path.exists(csv_path):
            raise FileNotFoundError(
                f"CSV file not found: {csv_path}"
            )

        return csv_path

    def _load_csv(self):
        """
        Load CSV and normalize column names.
        """

        df = pd.read_csv(self.csv_path)
        
        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
            .str.replace(" ", "_")
        )

        expected_columns = {
            "product_id",
            "product_title",
            "rating",
            "total_reviews",
            "price",
            "top_reviews"
        }

        missing = expected_columns - set(df.columns)

        if missing:
            raise ValueError(
                f"Missing columns: {missing}"
            )

        return df

    def transform_data(self):
        """
        Convert dataframe rows into LangChain Documents
        """

        documents = []

        for _, row in self.product_data.iterrows():

            doc = Document(
                page_content=str(row["top_reviews"]),
                metadata={
                    "product_id": row["product_id"],
                    "product_title": row["product_title"],
                    "rating": row["rating"],
                    "total_reviews": row["total_reviews"],
                    "price": row["price"]
                }
            )

            documents.append(doc)

        print(f"Created {len(documents)} Document objects.")

        return documents

    def store_in_vector_db(self, documents: List[Document]):
        """
        Store documents inside AstraDB
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

        print(
            f"Inserted {len(inserted_ids)} documents into AstraDB."
        )

        return vstore, inserted_ids

    def run_pipeline(self):
        """
        Execute complete ingestion pipeline
        """

        documents = self.transform_data()

        vstore, inserted_ids = self.store_in_vector_db(documents)

        return vstore, inserted_ids


if __name__ == "__main__":
    ingestion = DataIngestion()
    ingestion.run_pipeline()

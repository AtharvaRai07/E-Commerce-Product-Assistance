import os
import sys
import json
import asyncio
from dotenv import load_dotenv
from prod_assistance.utils.config_loader import load_config
from langchain_groq import ChatGroq
from langchain_cohere import CohereEmbeddings
from prod_assistance.logger import GLOBAL_LOGGER as log
from prod_assistance.exception.custom_exception import ProductAssistanceException

class ApiKeyManager:
    REQUIRED_KEYS = ["GROQ_API_KEY", "COHERE_API_KEY"]

    def __init__(self):
        self.api_keys = {}
        raw = os.getenv("API_KEYS")

        if raw:
            try:
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise ValueError("API_KEYS must be a JSON object.")
                self.api_keys = parsed
                log.info("Loaded API_KEYS from ECS secrets.")

            except Exception as e:
                log.error(f"Failed to parse API_KEYS: {e}")
                raise ProductAssistanceException(f"Failed to parse API_KEYS: {e}")


        for key in self.REQUIRED_KEYS:
            if not self.api_keys.get(key):
                env_val = os.getenv(key)
                if env_val:
                    self.api_keys[key] = env_val
                    log.info(f"Loaded {key} from environment variables.")

        missing = [k for k in self.REQUIRED_KEYS if not self.api_keys.get(k)]
        if missing:
            log.error(f"Missing required API keys: {', '.join(missing)}")
            raise ProductAssistanceException(f"Missing required API keys: {', '.join(missing)}")

        log.info("API keys loaded", keys={k: v[:6] + "..." for k, v in self.api_keys.items()})

    def get(self, key: str):
        val = self.api_keys.get(key)
        if not val:
            raise KeyError(f"API key '{key}' not found.")
        return val


class ModelLoader:
    """
    Loads embedding models and LLMs based on configuration and environment
    """

    def __init__(self):
        if os.getenv("ENV", "local").lower() != "production":
            load_dotenv()
            log.info("Loaded .env file for local development.")

        else:
            log.info("Running in production environment; skipping .env loading.")

        self.api_key_manager = ApiKeyManager()
        self.config = load_config()
        log.info(f"YAML config loaded, config_keys={list(self.config.keys())}")


    def load_embeddings(self):
        """
        Load embedding model based on configuration
        """
        try:
            model_name = self.config["embedding_model"]["model_name"]
            log.info(f"Loading embedding model: {model_name}")

            try:
                asyncio.get_running_loop()
            except RuntimeError:
                asyncio.set_event_loop(asyncio.new_event_loop())

            return CohereEmbeddings(
                model=model_name,
                cohere_api_key=self.api_key_manager.get("COHERE_API_KEY"),
            )

        except Exception as e:
            raise ProductAssistanceException(f"Failed to load embedding model: {e}")


    def load_llm(self):
        """
        Load LLM based on configuration
        """
        try:
            llm_block = self.config["llm"]
            provider_key = os.getenv("LLM_PROVIDER", "groq")

            if provider_key not in llm_block:
                log.error(f"LLM provider '{provider_key}' not found in configuration.")
                raise ProductAssistanceException(f"LLM provider '{provider_key}' not found in configuration.")

            llm_config = llm_block[provider_key]
            provider = llm_config.get("provider")
            model_name = llm_config.get("model_name")
            max_tokens = llm_config.get("max_tokens", 512)

            log.info(f"Loading LLM: provider={provider}, model_name={model_name}, max_tokens={max_tokens}")

            if provider == "groq":
                return ChatGroq(
                    model=model_name,
                    groq_api_key=self.api_key_manager.get("GROQ_API_KEY"),
                    max_tokens=max_tokens
                )

        except Exception as e:
            log.error(f"Failed to load LLM: {e}")
            raise ProductAssistanceException(f"Failed to load LLM: {e}")


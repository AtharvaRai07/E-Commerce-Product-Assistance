import asyncio
from utils.model_loader import ModelLoader
from ragas import SingleTurnSample
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.metrics.collections import ContextPrecisionWithoutReference, AnswerRelevancy
import grpc.experimental.aio as grpc_aio
grpc_aio.init_grpc_aio()

model_loader = ModelLoader()

def evaluate_context_precision(query, response, retrieved_context):
    try:
        sample = SingleTurnSample(
            user_input=query,
            response=response,
            retrieved_contexts=retrieved_context
        )

        async def main():
            llm = model_loader.load_llm()
            evaluator_llm = LangchainLLMWrapper(llm)
            context_precision = ContextPrecisionWithoutReference(llm=evaluator_llm)
            result = await context_precision.ascore(sample)
            return result

        return asyncio.run(main())
    except Exception as e:
        print(f"Error evaluating context precision: {e}")
        return e

def evaluate_answer_relevancy(query, response, retrieved_context):
    try:
        sample = SingleTurnSample(
            user_input=query,
            response=response,
            retrieved_contexts=retrieved_context
        )

        async def main():
            llm = model_loader.load_llm()
            evaluator_llm = LangchainLLMWrapper(llm)
            embedding_model = model_loader.load_embeddings()
            evaluator_embeddings = LangchainEmbeddingsWrapper(embedding_model)
            scorer = AnswerRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings)
            result = await scorer.ascore(sample)
            return result

        return asyncio.run(main())
    except Exception as e:
        print(f"Error evaluating answer relevancy: {e}")
        return e



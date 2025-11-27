"""
Petition generation module (LLM + template + QA).

This package is designed to run standalone from the RAG pipeline.
"""

from .generator import PetitionGenerator, PetitionService
from .llm import LocalQwenClient, LLMClient, StaticLLMClient
from .schema import PetitionInput, PetitionOutput, PetitionType

__all__ = [
    "PetitionGenerator",
    "PetitionService",
    "LocalQwenClient",
    "LLMClient",
    "StaticLLMClient",
    "PetitionInput",
    "PetitionOutput",
    "PetitionType",
]

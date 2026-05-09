"""FastAPI dependency injection providers."""

from functools import lru_cache
from src.db.session import get_session as get_async_db
from src.constraint_engine.raga_engine import RagaEngine
from src.constraint_engine.tala_engine import TalaEngine
from src.ml.carnatic_gpt import CarnaticGPT
from src.sahityam.generator import SahityamGenerator
from src.synthesis.pipeline import SynthesisPipeline


@lru_cache()
def get_raga_engine() -> RagaEngine:
    return RagaEngine()


@lru_cache()
def get_tala_engine() -> TalaEngine:
    return TalaEngine()


@lru_cache()
def get_carnatic_gpt() -> CarnaticGPT:
    return CarnaticGPT(get_raga_engine(), get_tala_engine())


@lru_cache()
def get_sahityam_generator() -> SahityamGenerator:
    return SahityamGenerator()


@lru_cache()
def get_synthesis_pipeline() -> SynthesisPipeline:
    return SynthesisPipeline()

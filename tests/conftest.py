"""Shared test fixtures."""

import pytest
from src.constraint_engine.raga_engine import RagaEngine
from src.constraint_engine.tala_engine import TalaEngine
from src.ml.carnatic_gpt import CarnaticGPT


@pytest.fixture
def raga_engine():
    return RagaEngine()


@pytest.fixture
def tala_engine():
    return TalaEngine()


@pytest.fixture
def carnatic_gpt(raga_engine, tala_engine):
    return CarnaticGPT(raga_engine, tala_engine)

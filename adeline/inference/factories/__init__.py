"""
Inference Factories
===================

Factory pattern para creación de handlers y strategies.
Centraliza lógica de construcción dispersa en Controller.
"""
from .handler_factory import InferenceHandlerFactory
from .strategy_factory import StrategyFactory

__all__ = [
    "InferenceHandlerFactory",
    "StrategyFactory",
]

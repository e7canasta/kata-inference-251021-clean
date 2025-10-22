"""
Configuration Module
====================

Provides configuration loading with Pydantic validation.

Usage (New - Recommended):
    from config.schemas import AdelineConfig
    config = AdelineConfig.from_yaml("config/adeline/config.yaml")

Usage (Legacy - Backward compatibility):
    from config import PipelineConfig
    config = PipelineConfig()
"""
from .schemas import (
    AdelineConfig,
    PipelineSettings,
    ModelsSettings,
    MQTTSettings,
    StabilizationSettings,
    ROIStrategySettings,
    LoggingSettings,
)

# Legacy imports for backward compatibility
from ..legacy_config import PipelineConfig, disable_models_from_config

__all__ = [
    # New Pydantic models
    'AdelineConfig',
    'PipelineSettings',
    'ModelsSettings',
    'MQTTSettings',
    'StabilizationSettings',
    'ROIStrategySettings',
    'LoggingSettings',
    # Legacy
    'PipelineConfig',
    'disable_models_from_config',
]

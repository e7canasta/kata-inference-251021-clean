"""
Detection Stabilization - Temporal filtering to reduce flickering

Modularized Package (v2.1):
- matching.py: Spatial matching utilities (IoU calculation) - Reusable
- core.py: Stabilization strategies, config, factory, sinks

Public API:
- Strategies: TemporalHysteresisStabilizer, NoOpStabilizer
- Factory: create_stabilization_strategy, create_stabilization_sink
- Utilities: calculate_iou (for custom matching logic)
"""

# Matching utilities (spatial tracking)
from .matching import calculate_iou

# Core stabilization (strategies, config, factory)
from .core import (
    BaseDetectionStabilizer,
    StabilizationConfig,
    TemporalHysteresisStabilizer,
    NoOpStabilizer,
    create_stabilization_strategy,
    create_stabilization_sink,
)

__all__ = [
    # Core classes
    "BaseDetectionStabilizer",
    "StabilizationConfig",
    "TemporalHysteresisStabilizer",
    "NoOpStabilizer",

    # Factory functions
    "create_stabilization_strategy",
    "create_stabilization_sink",

    # Utilities (reusable)
    "calculate_iou",
]

"""
ROI Strategies - Adaptive and Fixed Region of Interest
"""
from .base import ROIStrategyConfig, validate_and_create_roi_strategy
from .adaptive import (
    ROIBox,
    ROIState,
    AdaptiveInferenceHandler,
    roi_update_sink,
    adaptive_roi_inference,
)
from .fixed import FixedROIInferenceHandler, FixedROIState

__all__ = [
    # Base / Factory
    "ROIStrategyConfig",
    "validate_and_create_roi_strategy",
    # Adaptive
    "ROIBox",
    "ROIState",
    "AdaptiveInferenceHandler",
    "roi_update_sink",
    "adaptive_roi_inference",
    # Fixed
    "FixedROIInferenceHandler",
    "FixedROIState",
]

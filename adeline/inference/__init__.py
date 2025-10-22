"""
Inference Engine - Models, ROI, Stabilization
"""
from .models import get_model_from_config, get_process_frame_function

__all__ = ["get_model_from_config", "get_process_frame_function"]

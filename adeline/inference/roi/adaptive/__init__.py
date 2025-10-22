"""
Adaptive ROI Module - Modularized Package
==========================================

Este paquete implementa ROI adaptativo con arquitectura modular:

Bounded Contexts (DDD):
- geometry.py: Shape Algebra (operaciones sobre formas 2D)
- state.py: Temporal ROI Tracking (gestión de estado por source)
- pipeline.py: Inference Orchestration (flow end-to-end)

Public API (backward compatible):
- ROIBox: Bounding box inmutable con operaciones geométricas
- ROIState: Estado compartido de ROI por video source
- AdaptiveInferenceHandler: Callable wrapper con toggle support
- adaptive_roi_inference: Pipeline de inferencia con crop adaptativo
- roi_update_sink: Sink para actualizar ROI state
- Utility functions: crop, transform, convert

Features:
- Dynamic crop basado en detecciones previas
- Temporal smoothing del ROI
- Optimizaciones NumPy/Supervision
- Toggle dinámico vía MQTT

Performance Optimizations:
- NumPy views para crop (zero-copy)
- Operaciones vectorizadas para bbox calculations
- ROI siempre cuadrado (sin distorsión)
- Tamaño en múltiplos de imgsz (resize eficiente)

Uso (sin cambios respecto a versión monolítica):
    from inference.roi.adaptive import AdaptiveInferenceHandler, ROIState

    roi_state = ROIState(margin=0.2, smoothing_alpha=0.3)
    handler = AdaptiveInferenceHandler(model, config, roi_state)
"""

# Re-export public API (mantiene compatibilidad con imports existentes)
from .geometry import ROIBox
from .state import ROIState
from .pipeline import (
    AdaptiveInferenceHandler,
    adaptive_roi_inference,
    roi_update_sink,
    crop_frame_if_roi,
    transform_predictions_vectorized,
    convert_predictions_to_sv_detections,
)

__all__ = [
    # Core classes
    "ROIBox",
    "ROIState",
    "AdaptiveInferenceHandler",

    # Pipeline functions
    "adaptive_roi_inference",
    "roi_update_sink",

    # Utility functions
    "crop_frame_if_roi",
    "transform_predictions_vectorized",
    "convert_predictions_to_sv_detections",
]

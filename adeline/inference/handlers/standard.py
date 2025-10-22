"""
Standard Inference Handler
==========================

Handler para pipeline standard (sin ROI, sin custom logic).
Wrapper mínimo para mantener interface consistente con otros handlers.

Diseño: KISS
- No hace nada (pipeline standard maneja inferencia internamente)
- Existe solo para uniformidad de interface
- Siempre enabled, no toggle
"""
from typing import Any, List
import logging

from .base import BaseInferenceHandler
from inference.core.interfaces.camera.entities import VideoFrame

logger = logging.getLogger(__name__)


class StandardInferenceHandler(BaseInferenceHandler):
    """
    Handler standard para pipeline sin custom logic.

    Nota: En modo standard, InferencePipeline maneja inferencia internamente
    usando model_id. Este handler es un placeholder para mantener interface
    consistente con AdaptiveInferenceHandler y FixedROIInferenceHandler.

    Properties:
    - enabled: Siempre True
    - supports_toggle: Siempre False (inmutable)

    Usage:
        # En Controller, para uniformidad:
        if config.ROI_MODE == 'none':
            handler = StandardInferenceHandler()

        # Pero el pipeline se crea con .init() (no init_with_custom_logic)
        pipeline = InferencePipeline.init(model_id=..., ...)
    """

    @property
    def enabled(self) -> bool:
        """Standard siempre habilitado."""
        return True

    @property
    def supports_toggle(self) -> bool:
        """Standard no soporta toggle (inmutable)."""
        return False

    def __call__(self, video_frames: List[VideoFrame]) -> List[Any]:
        """
        No-op: Pipeline standard no usa custom logic.

        Este método NO debería ser llamado en modo standard
        (pipeline usa model_id directamente con .init()).

        Raises:
            NotImplementedError: Siempre (este handler no debe ser invocado)
        """
        raise NotImplementedError(
            "StandardInferenceHandler should not be called directly. "
            "Use InferencePipeline.init() instead of init_with_custom_logic(). "
            "This handler exists only for interface uniformity."
        )

"""
Fixed ROI Strategy
==================

ROI estático con coordenadas fijas configuradas en YAML.
KISS: Inmutable, sin lógica compleja.
"""

from typing import Optional, Tuple, Dict
import logging

from .adaptive import ROIBox, adaptive_roi_inference
from ..handlers.base import BaseInferenceHandler

logger = logging.getLogger(__name__)


class FixedROIState:
    """
    ROI estático con coordenadas fijas.

    Diseño KISS:
    - Constructor recibe coordenadas normalizadas del YAML
    - get_roi() SIEMPRE devuelve las mismas coordenadas (inmutable)
    - Sin smoothing, sin updates, sin lógica compleja

    Coordenadas normalizadas [0.0 - 1.0]:
    - x_min, y_min: esquina superior izquierda
    - x_max, y_max: esquina inferior derecha

    Example:
        # ROI centrado, 60% del frame
        fixed_roi = FixedROIState(
            x_min=0.2, y_min=0.2,
            x_max=0.8, y_max=0.8,
        )

        roi_box = fixed_roi.get_roi(source_id=0, frame_shape=(720, 1280))
        # ROIBox(x1=256, y1=144, x2=1024, y2=576)
    """

    def __init__(
        self,
        x_min: float,
        y_min: float,
        x_max: float,
        y_max: float,
        show_overlay: bool = True,
        resize_to_model: bool = False,
    ):
        """
        Args:
            x_min: Coordenada X mínima normalizada (0.0 = izquierda, 1.0 = derecha)
            y_min: Coordenada Y mínima normalizada (0.0 = arriba, 1.0 = abajo)
            x_max: Coordenada X máxima normalizada
            y_max: Coordenada Y máxima normalizada
            show_overlay: Si dibujar ROI en visualización
            resize_to_model: Si resize ROI al tamaño del modelo (zoom) vs padding con negro
        """
        # Validación básica (ya validado en config, pero doble check)
        if not (0.0 <= x_min < x_max <= 1.0):
            raise ValueError(f"Invalid x coordinates: x_min={x_min}, x_max={x_max}")
        if not (0.0 <= y_min < y_max <= 1.0):
            raise ValueError(f"Invalid y coordinates: y_min={y_min}, y_max={y_max}")

        self._x_min = x_min
        self._y_min = y_min
        self._x_max = x_max
        self._y_max = y_max
        self.show_overlay = show_overlay
        self.resize_to_model = resize_to_model

        # Cache para evitar recalcular (key: frame_shape)
        self._roi_cache: Dict[Tuple[int, int], ROIBox] = {}

    def get_roi(
        self,
        source_id: int,
        frame_shape: Optional[Tuple[int, int]] = None,
    ) -> Optional[ROIBox]:
        """
        Retorna ROI fijo en coordenadas absolutas.

        Args:
            source_id: ID del source (ignorado, todas las sources usan mismo ROI)
            frame_shape: (height, width) del frame para convertir a píxeles

        Returns:
            ROIBox con coordenadas absolutas (píxeles)
        """
        if frame_shape is None:
            logger.warning("FixedROIState.get_roi() called without frame_shape, returning None")
            return None

        # Cache hit (evita recalcular para mismo frame size)
        if frame_shape in self._roi_cache:
            return self._roi_cache[frame_shape]

        # Convertir coordenadas normalizadas a píxeles
        h, w = frame_shape
        roi_box = ROIBox(
            x1=int(self._x_min * w),
            y1=int(self._y_min * h),
            x2=int(self._x_max * w),
            y2=int(self._y_max * h),
        )

        # Cache para reutilizar
        self._roi_cache[frame_shape] = roi_box

        logger.debug(
            f"FixedROI: frame {frame_shape} -> ROI ({roi_box.x1},{roi_box.y1})-({roi_box.x2},{roi_box.y2}) "
            f"[{roi_box.width}×{roi_box.height}]"
        )

        return roi_box

    def reset(self, source_id: Optional[int] = None):
        """
        Reset no-op para FixedROI (coordenadas inmutables).

        Implementado para compatibilidad con interface de ROIState.
        """
        logger.debug("FixedROI.reset() called (no-op for fixed coordinates)")

    @property
    def normalized_coords(self) -> Dict[str, float]:
        """Retorna coordenadas normalizadas (para logging/debugging)"""
        return {
            'x_min': self._x_min,
            'y_min': self._y_min,
            'x_max': self._x_max,
            'y_max': self._y_max,
        }


class FixedROIInferenceHandler(BaseInferenceHandler):
    """
    Wrapper callable para inferencia con ROI fijo.

    Reutiliza adaptive_roi_inference() pero con FixedROIState.
    KISS: No necesita toggle dinámico (fixed es inmutable).

    Hereda de BaseInferenceHandler para garantizar interface consistente.

    Properties:
    - enabled: Siempre True (inmutable)
    - supports_toggle: False (no soporta toggle)

    Usage:
        handler = FixedROIInferenceHandler(model, config, roi_state)
        pipeline = InferencePipeline.init_with_custom_logic(
            on_video_frame=handler,
            ...
        )

        # Fixed ROI NO soporta toggle
        # handler.disable() → NotImplementedError
    """

    def __init__(
        self,
        model,
        inference_config,
        roi_state: FixedROIState,
        process_frame_fn=None,
        show_statistics: bool = True,
    ):
        self.model = model
        self.inference_config = inference_config
        self.roi_state = roi_state
        self.process_frame_fn = process_frame_fn
        self.show_statistics = show_statistics

    @property
    def enabled(self) -> bool:
        """Fixed ROI siempre habilitado (inmutable)."""
        return True

    @property
    def supports_toggle(self) -> bool:
        """Fixed ROI NO soporta toggle (inmutable)."""
        return False

    def __call__(self, video_frames):
        """Callable interface para InferencePipeline"""
        # Reutilizar adaptive_roi_inference (FixedROIState tiene interface compatible)
        results = adaptive_roi_inference(
            video_frames=video_frames,
            model=self.model,
            inference_config=self.inference_config,
            roi_state=self.roi_state,
            enable_crop=True,  # Fixed siempre enabled
            process_frame_fn=self.process_frame_fn,
            show_statistics=self.show_statistics,
        )

        return results

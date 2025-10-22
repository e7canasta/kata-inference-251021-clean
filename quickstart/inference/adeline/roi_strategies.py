"""
ROI Strategies Module
=====================

Factory pattern para estrategias de Region Of Interest (ROI):
- None: Full frame (sin crop)
- Adaptive: ROI dinámico basado en detecciones
- Fixed: ROI estático configurado en YAML

Diseño: KISS + Complejidad por diseño
- FixedROIState: Inmutable, sin lógica compleja
- Reutiliza código de adaptive_roi.py (ROIBox, crop functions)
- Validación centralizada en factory
"""

from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
import logging

from .adaptive_roi import ROIBox, ROIState

logger = logging.getLogger(__name__)


# ============================================================================
# Fixed ROI Strategy (Simple, Immutable)
# ============================================================================

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


# ============================================================================
# ROI Strategy Factory
# ============================================================================

@dataclass
class ROIStrategyConfig:
    """Configuración validada de estrategia ROI"""
    mode: str  # "none", "adaptive", "fixed"

    # Adaptive parameters (solo si mode="adaptive")
    adaptive_margin: float = 0.2
    adaptive_smoothing: float = 0.3
    adaptive_min_roi_multiple: int = 1
    adaptive_max_roi_multiple: int = 4
    adaptive_show_statistics: bool = True
    adaptive_resize_to_model: bool = False  # Resize ROI to model size (zoom)

    # Fixed parameters (solo si mode="fixed")
    fixed_x_min: float = 0.2
    fixed_y_min: float = 0.2
    fixed_x_max: float = 0.8
    fixed_y_max: float = 0.8
    fixed_show_overlay: bool = True
    fixed_resize_to_model: bool = False  # Resize ROI to model size (zoom)

    # Modelo (para adaptive)
    imgsz: int = 320


def validate_and_create_roi_strategy(
    mode: str,
    config: ROIStrategyConfig,
) -> Optional[FixedROIState | ROIState]:
    """
    Factory function: valida configuración y crea estrategia ROI.

    Validaciones:
    - Mode debe ser "none", "adaptive", o "fixed"
    - Coordenadas fixed deben estar en [0.0, 1.0]
    - Parámetros adaptive deben ser válidos

    Args:
        mode: Estrategia seleccionada
        config: Configuración validada

    Returns:
        - None si mode="none" (usar full frame)
        - ROIState si mode="adaptive"
        - FixedROIState si mode="fixed"

    Raises:
        ValueError: Si configuración es inválida
    """
    mode = mode.lower()

    if mode not in ["none", "adaptive", "fixed"]:
        raise ValueError(
            f"Invalid ROI mode: '{mode}'. "
            f"Must be one of: 'none', 'adaptive', 'fixed'"
        )

    if mode == "none":
        logger.info("📦 ROI Strategy: NONE (full frame)")
        return None

    if mode == "adaptive":
        # Validar parámetros adaptive
        if not (0.0 <= config.adaptive_margin <= 1.0):
            raise ValueError(f"adaptive_margin must be in [0.0, 1.0], got {config.adaptive_margin}")
        if not (0.0 <= config.adaptive_smoothing <= 1.0):
            raise ValueError(f"adaptive_smoothing must be in [0.0, 1.0], got {config.adaptive_smoothing}")
        if config.adaptive_min_roi_multiple < 1:
            raise ValueError(f"adaptive_min_roi_multiple must be >= 1, got {config.adaptive_min_roi_multiple}")
        if config.adaptive_max_roi_multiple < config.adaptive_min_roi_multiple:
            raise ValueError(
                f"adaptive_max_roi_multiple ({config.adaptive_max_roi_multiple}) must be >= "
                f"min_roi_multiple ({config.adaptive_min_roi_multiple})"
            )

        # Log resize_to_model info
        resize_info = ""
        if config.adaptive_resize_to_model:
            resize_info = f" | 🔍 resize_to_model=TRUE (zoom ROI → {config.imgsz}×{config.imgsz})"
        else:
            resize_info = f" | resize_to_model=false (padding con negro)"

        logger.info(
            f"🔲 ROI Strategy: ADAPTIVE (margin={config.adaptive_margin}, "
            f"smoothing={config.adaptive_smoothing}, "
            f"multiples={config.adaptive_min_roi_multiple}-{config.adaptive_max_roi_multiple}){resize_info}"
        )

        return ROIState(
            margin=config.adaptive_margin,
            smoothing_alpha=config.adaptive_smoothing,
            min_roi_size=0.3,
            imgsz=config.imgsz,
            min_roi_multiple=config.adaptive_min_roi_multiple,
            max_roi_multiple=config.adaptive_max_roi_multiple,
            resize_to_model=config.adaptive_resize_to_model,
        )

    if mode == "fixed":
        # Validar coordenadas normalizadas
        if not (0.0 <= config.fixed_x_min < config.fixed_x_max <= 1.0):
            raise ValueError(
                f"Invalid x coordinates: x_min={config.fixed_x_min}, x_max={config.fixed_x_max}. "
                f"Must be in [0.0, 1.0] with x_min < x_max"
            )
        if not (0.0 <= config.fixed_y_min < config.fixed_y_max <= 1.0):
            raise ValueError(
                f"Invalid y coordinates: y_min={config.fixed_y_min}, y_max={config.fixed_y_max}. "
                f"Must be in [0.0, 1.0] with y_min < y_max"
            )

        # Log resize_to_model info
        resize_info = ""
        if config.fixed_resize_to_model:
            resize_info = f" | 🔍 resize_to_model=TRUE (zoom ROI → {config.imgsz}×{config.imgsz})"
        else:
            resize_info = f" | resize_to_model=false (padding con negro)"

        logger.info(
            f"📍 ROI Strategy: FIXED (x: {config.fixed_x_min:.2f}-{config.fixed_x_max:.2f}, "
            f"y: {config.fixed_y_min:.2f}-{config.fixed_y_max:.2f}){resize_info}"
        )

        return FixedROIState(
            x_min=config.fixed_x_min,
            y_min=config.fixed_y_min,
            x_max=config.fixed_x_max,
            y_max=config.fixed_y_max,
            show_overlay=config.fixed_show_overlay,
            resize_to_model=config.fixed_resize_to_model,
        )

    # Nunca debería llegar aquí
    raise ValueError(f"Unhandled ROI mode: {mode}")


# ============================================================================
# Fixed ROI Inference Handler (similar a AdaptiveInferenceHandler)
# ============================================================================

class FixedROIInferenceHandler:
    """
    Wrapper callable para inferencia con ROI fijo.

    Reutiliza adaptive_roi_inference() pero con FixedROIState.
    KISS: No necesita toggle dinámico (fixed es inmutable).

    Compatible con AdaptiveInferenceHandler interface para uniformidad.
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
        self.enabled = True  # Fixed siempre enabled (no toggle necesario)
        self.show_statistics = show_statistics

    def __call__(self, video_frames):
        """Callable interface para InferencePipeline"""
        from .adaptive_roi import adaptive_roi_inference

        # Reutilizar adaptive_roi_inference (FixedROIState tiene interface compatible)
        results = adaptive_roi_inference(
            video_frames=video_frames,
            model=self.model,
            inference_config=self.inference_config,
            roi_state=self.roi_state,
            enable_crop=self.enabled,
            process_frame_fn=self.process_frame_fn,
            show_statistics=self.show_statistics,
        )

        return results

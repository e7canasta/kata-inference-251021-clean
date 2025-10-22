"""
ROI Strategy Factory
====================

Factory pattern para crear estrategias de Region Of Interest (ROI).
Validación centralizada de configuración.
"""

from typing import Optional
from dataclasses import dataclass
import logging

from .adaptive import ROIState
from .fixed import FixedROIState

logger = logging.getLogger(__name__)


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

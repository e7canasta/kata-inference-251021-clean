"""
ROI State Management Module
============================

Bounded Context: Temporal ROI Tracking (gestión de estado por source)

This module manages ROI state across video sources and frames:
- ROIState: Tracks current ROI per video source
- Temporal smoothing: Prevents jittery ROI updates
- Detection-based updates: Updates ROI from inference results
- Reset capabilities: Clear state for scene changes

Design:
- Thread-safe for reading (writes only from inference thread)
- Per-source state isolation (multi-stream support)
- NumPy-optimized operations (vectorized bbox calculations)

Performance optimizations:
- ROI always SQUARE (no distortion)
- Size in MULTIPLES of imgsz (efficient resize)
- Clamp between [min_multiple × imgsz, max_multiple × imgsz]
"""

from typing import Dict, Optional, Tuple
import logging

import numpy as np
import supervision as sv

from .geometry import ROIBox


logger = logging.getLogger(__name__)


class ROIState:
    """
    Estado compartido para ROI adaptativo por video source.

    Optimizado para performance con numpy operations.
    Thread-safe para lectura (write solo desde inference thread).

    ROI Strategy (Performance Optimization):
    - ROI siempre es CUADRADO (sin distorsión de imagen)
    - Tamaño en MÚLTIPLOS de imgsz (resize eficiente: 640→320 es 2x limpio)
    - Clamp entre [min_multiple × imgsz, max_multiple × imgsz]
    """

    def __init__(
        self,
        margin: float = 0.2,
        smoothing_alpha: float = 0.3,
        min_roi_size: float = 0.3,
        imgsz: int = 320,
        min_roi_multiple: int = 1,
        max_roi_multiple: int = 4,
        resize_to_model: bool = False,
    ):
        """
        Args:
            margin: Expansión porcentual alrededor de detecciones (0.2 = 20%)
            smoothing_alpha: Factor de suavizado temporal (0 = no smooth, 1 = max smooth)
            min_roi_size: Tamaño mínimo de ROI como % del frame (0.3 = 30%)
            imgsz: Tamaño de inferencia del modelo (ej: 320, 640)
            min_roi_multiple: Múltiplo mínimo (ej: 1 → ROI min = 320×320 si imgsz=320)
            max_roi_multiple: Múltiplo máximo (ej: 4 → ROI max = 1280×1280 si imgsz=320)
            resize_to_model: Si resize ROI al tamaño del modelo (zoom) vs padding con negro
        """
        self._roi_by_source: Dict[int, Optional[ROIBox]] = {}
        self._margin = margin
        self._smoothing_alpha = smoothing_alpha
        self._min_roi_size = min_roi_size
        self._imgsz = imgsz
        self._min_roi_multiple = min_roi_multiple
        self._max_roi_multiple = max_roi_multiple
        self.resize_to_model = resize_to_model

    def get_roi(self, source_id: int) -> Optional[ROIBox]:
        """
        Retorna ROI actual para source_id o None (usa frame completo).

        Args:
            source_id: ID de la fuente de video

        Returns:
            ROIBox si hay ROI activo, None para frame completo
        """
        return self._roi_by_source.get(source_id)

    def update_from_detections(
        self,
        source_id: int,
        detections: sv.Detections,
        frame_shape: Tuple[int, int],
    ):
        """
        Actualiza ROI basado en detecciones usando operaciones vectorizadas.

        Strategy (Optimized for Performance):
        1. Calcula bbox que engloba todas las detecciones (vectorizado)
        2. Convierte a CUADRADO en MÚLTIPLO de imgsz (sin distorsión)
        3. Expande con margin
        4. Valida tamaño mínimo
        5. Suaviza temporalmente con ROI anterior

        Args:
            source_id: ID de la fuente de video
            detections: sv.Detections con bbox en formato xyxy
            frame_shape: (height, width) del frame
        """
        if len(detections) == 0:
            # Fallback: frame completo si no hay detecciones
            self._roi_by_source[source_id] = None
            return

        # 1. Operación vectorizada: min/max sobre todas las detecciones
        xyxy = detections.xyxy  # shape: (N, 4) - numpy array
        x1 = int(np.min(xyxy[:, 0]))
        y1 = int(np.min(xyxy[:, 1]))
        x2 = int(np.max(xyxy[:, 2]))
        y2 = int(np.max(xyxy[:, 3]))

        new_roi = ROIBox(x1, y1, x2, y2)

        # 2. Convertir a cuadrado en múltiplo de imgsz (performance optimization)
        new_roi = new_roi.make_square_multiple(
            imgsz=self._imgsz,
            min_multiple=self._min_roi_multiple,
            max_multiple=self._max_roi_multiple,
            frame_shape=frame_shape,
        )

        # 3. Expandir con margen (preservando cuadrado)
        new_roi = new_roi.expand(self._margin, frame_shape, preserve_square=True)

        # Validación: verificar que sigue siendo cuadrado (debug)
        if not new_roi.is_square:
            logger.warning(
                f"⚠️ ROI no es cuadrado después de expand: {new_roi.width}×{new_roi.height} "
                f"(diff: {abs(new_roi.width - new_roi.height)}px)"
            )

        # 4. Validar tamaño mínimo
        h, w = frame_shape
        roi_area = new_roi.width * new_roi.height
        frame_area = h * w

        if roi_area < self._min_roi_size * frame_area:
            # ROI muy pequeño, usar frame completo
            logger.debug(
                f"Source {source_id}: ROI too small ({roi_area}/{frame_area}), using full frame"
            )
            self._roi_by_source[source_id] = None
            return

        # 5. Suavizado temporal (si hay ROI previo)
        prev_roi = self._roi_by_source.get(source_id)
        if prev_roi is not None:
            new_roi = new_roi.smooth_with(prev_roi, self._smoothing_alpha)

        self._roi_by_source[source_id] = new_roi
        logger.debug(
            f"Source {source_id}: ROI updated to ({new_roi.x1},{new_roi.y1})-({new_roi.x2},{new_roi.y2}) "
            f"[{new_roi.width}×{new_roi.height}]"
        )

    def reset(self, source_id: Optional[int] = None):
        """
        Resetea ROI a frame completo.

        Args:
            source_id: Si especificado, resetea solo ese source. Si None, resetea todos.
        """
        if source_id is None:
            self._roi_by_source.clear()
            logger.info("ROI state reset for all sources")
        else:
            self._roi_by_source[source_id] = None
            logger.info(f"ROI state reset for source {source_id}")

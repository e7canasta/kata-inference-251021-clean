"""
ROI Geometry Module
===================

Bounded Context: Shape Algebra (operaciones sobre formas 2D)

This module contains pure geometric operations for ROI (Region of Interest) bounding boxes:
- ROIBox dataclass with immutable geometry
- Geometric transformations: expand, smooth, make_square_multiple
- Property computations: area, size_multiple, crop_ratio
- Invariants: square shape, multiple of imgsz

Design:
- Pure functions (no side effects)
- Immutable data structures
- Zero external dependencies (only numpy for arrays)
- Property-testable (invariants can be validated)

Performance optimizations:
- Square ROI (no image distortion)
- Size in multiples of imgsz (clean resize: 640→320 = 2x)
- NumPy arrays for efficient coordinate operations
"""

from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class ROIBox:
    """
    Bounding box inmutable para ROI.

    Attributes:
        x1, y1: Top-left corner
        x2, y2: Bottom-right corner
    """
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def xyxy(self) -> np.ndarray:
        """Formato supervision-compatible: [[x1, y1, x2, y2]]"""
        return np.array([[self.x1, self.y1, self.x2, self.y2]], dtype=np.float32)

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def area(self) -> int:
        """Área del ROI en píxeles"""
        return self.width * self.height

    @property
    def is_square(self) -> bool:
        """Verifica si el ROI es cuadrado (validación)"""
        return self.width == self.height

    def get_size_multiple(self, imgsz: int) -> float:
        """
        Calcula el múltiplo del ROI respecto a imgsz.

        Args:
            imgsz: Tamaño de inferencia del modelo

        Returns:
            Múltiplo (ej: 2.0 si ROI es 640×640 y imgsz=320)
        """
        return max(self.width, self.height) / imgsz if imgsz > 0 else 0.0

    def get_crop_ratio(self, frame_shape: Tuple[int, int]) -> float:
        """
        Ratio del ROI respecto al frame completo.

        Args:
            frame_shape: (height, width) del frame

        Returns:
            Ratio (0.0-1.0) del área ROI / área frame
        """
        h, w = frame_shape
        frame_area = h * w
        return self.area / frame_area if frame_area > 0 else 0.0

    def expand(self, margin: float, frame_shape: Tuple[int, int], preserve_square: bool = False) -> 'ROIBox':
        """
        Expande ROI con margen porcentual, clipped a frame bounds.

        Args:
            margin: Porcentaje de expansión (0.2 = 20%)
            frame_shape: (height, width) del frame
            preserve_square: Si True y ROI es cuadrado, mantiene forma cuadrada usando max(margin_x, margin_y)

        Returns:
            Nuevo ROIBox expandido
        """
        h, w = frame_shape
        margin_x = int(margin * w)
        margin_y = int(margin * h)

        # Preservar cuadrado: usar el margin más grande en ambas dimensiones
        if preserve_square and self.is_square:
            margin_px = max(margin_x, margin_y)
            margin_x = margin_px
            margin_y = margin_px

        return ROIBox(
            x1=max(0, self.x1 - margin_x),
            y1=max(0, self.y1 - margin_y),
            x2=min(w, self.x2 + margin_x),
            y2=min(h, self.y2 + margin_y),
        )

    def smooth_with(self, other: 'ROIBox', alpha: float) -> 'ROIBox':
        """
        Suavizado temporal entre dos ROIs.

        Args:
            other: ROI nuevo
            alpha: Factor de suavizado (0 = mantener self, 1 = usar other)

        Returns:
            ROI suavizado: alpha*other + (1-alpha)*self
            Si ambos ROIs son cuadrados, fuerza resultado cuadrado (previene errores de redondeo)
        """
        smoothed = ROIBox(
            x1=int(alpha * other.x1 + (1 - alpha) * self.x1),
            y1=int(alpha * other.y1 + (1 - alpha) * self.y1),
            x2=int(alpha * other.x2 + (1 - alpha) * self.x2),
            y2=int(alpha * other.y2 + (1 - alpha) * self.y2),
        )

        # Preservar cuadrado si ambos inputs son cuadrados (evita errores de redondeo)
        if self.is_square and other.is_square and not smoothed.is_square:
            # Forzar cuadrado usando el lado más grande
            size = max(smoothed.width, smoothed.height)
            center_x = (smoothed.x1 + smoothed.x2) // 2
            center_y = (smoothed.y1 + smoothed.y2) // 2
            half_size = size // 2

            smoothed = ROIBox(
                x1=center_x - half_size,
                y1=center_y - half_size,
                x2=center_x - half_size + size,
                y2=center_y - half_size + size,
            )

        return smoothed

    def make_square_multiple(
        self,
        imgsz: int,
        min_multiple: int,
        max_multiple: int,
        frame_shape: Tuple[int, int],
    ) -> 'ROIBox':
        """
        Convierte ROI a cuadrado perfecto en múltiplos de imgsz.

        Estrategia para optimal performance sin distorsión:
        1. Toma el lado más grande del bbox
        2. Redondea al múltiplo de imgsz más cercano
        3. Clamp entre [min_multiple × imgsz, max_multiple × imgsz]
        4. Centra el cuadrado sobre el bbox original
        5. Clip a frame bounds

        Ejemplo: bbox=450x300, imgsz=320, min=1, max=4
            → max_side=450
            → nearest_multiple=1.4 → round=1 → 320×320 (si <480)
            → nearest_multiple=1.4 → round=2 → 640×640 (si ≥480)

        Args:
            imgsz: Tamaño de inferencia del modelo (ej: 320, 640)
            min_multiple: Múltiplo mínimo permitido (ej: 1 → 320×320)
            max_multiple: Múltiplo máximo permitido (ej: 4 → 1280×1280)
            frame_shape: (height, width) del frame para clipping

        Returns:
            ROIBox cuadrado en múltiplo de imgsz, centrado y clipped
        """
        # 1. Lado más grande del bbox actual
        max_side = max(self.width, self.height)

        # 2. Redondear al múltiplo más cercano
        multiple = max_side / imgsz
        rounded_multiple = max(min_multiple, min(max_multiple, round(multiple)))

        # 3. Tamaño final del ROI cuadrado
        square_size = rounded_multiple * imgsz

        # 4. Centrar cuadrado sobre bbox original
        center_x = (self.x1 + self.x2) // 2
        center_y = (self.y1 + self.y2) // 2

        half_size = square_size // 2
        new_x1 = center_x - half_size
        new_y1 = center_y - half_size
        new_x2 = new_x1 + square_size
        new_y2 = new_y1 + square_size

        # 5. Clip a frame bounds
        h, w = frame_shape
        new_x1 = max(0, new_x1)
        new_y1 = max(0, new_y1)
        new_x2 = min(w, new_x2)
        new_y2 = min(h, new_y2)

        return ROIBox(x1=new_x1, y1=new_y1, x2=new_x2, y2=new_y2)

"""
Spatial Matching Utilities for Object Tracking
===============================================

Bounded Context: Spatial Matching (geometría de tracking)

This module provides spatial matching utilities for object tracking:
- IoU (Intersection over Union) calculation
- Bounding box overlap detection
- Distance metrics for tracking

Design:
- Pure functions (no side effects)
- Zero external dependencies
- Property-testable (IoU properties: symmetry, bounded [0,1], etc.)

Reusability:
- Can be used from stabilization (detection tracking)
- Can be used from adaptive ROI (multi-object tracking)
- Can be used for general bbox matching tasks

Performance:
- Optimized for normalized coordinates (0.0-1.0)
- Efficient computation (no NumPy needed, pure Python)
"""

from typing import Dict


def calculate_iou(bbox1: Dict[str, float], bbox2: Dict[str, float]) -> float:
    """
    Calcula Intersection over Union (IoU) entre dos bounding boxes.

    IoU es una métrica de similitud espacial entre bounding boxes.
    Valores cercanos a 1.0 indican alta superposición (mismo objeto).
    Valores cercanos a 0.0 indican poca/nula superposición (objetos distintos).

    Properties (matemáticas):
    - Simetría: IoU(A, B) = IoU(B, A)
    - Bounded: 0.0 <= IoU <= 1.0
    - Identidad: IoU(A, A) = 1.0
    - Disjoint: IoU(A, B) = 0.0 si no hay overlap

    Args:
        bbox1: {'x': center_x, 'y': center_y, 'width': w, 'height': h}
               Coordenadas normalizadas (0.0-1.0)
        bbox2: {'x': center_x, 'y': center_y, 'width': w, 'height': h}
               Coordenadas normalizadas (0.0-1.0)

    Returns:
        IoU score [0.0, 1.0]
        - 0.0 = sin overlap (objetos completamente separados)
        - 0.3 = overlap bajo (threshold típico para "mismo objeto")
        - 0.5 = overlap medio
        - 0.7 = overlap alto
        - 1.0 = perfect match (mismo bbox)

    Example:
        >>> bbox1 = {'x': 0.5, 'y': 0.5, 'width': 0.2, 'height': 0.3}
        >>> bbox2 = {'x': 0.52, 'y': 0.51, 'width': 0.21, 'height': 0.29}
        >>> iou = calculate_iou(bbox1, bbox2)
        >>> print(f"IoU: {iou:.2f}")  # ~0.85 (high overlap, likely same object)

        >>> bbox3 = {'x': 0.9, 'y': 0.9, 'width': 0.1, 'height': 0.1}
        >>> iou = calculate_iou(bbox1, bbox3)
        >>> print(f"IoU: {iou:.2f}")  # ~0.0 (no overlap, different objects)

    Implementation Notes:
    - Uses center+size format (common in YOLO/Roboflow models)
    - Converts to xyxy (min/max corners) internally for calculation
    - Handles edge cases: zero-size boxes, no overlap, etc.
    """
    # Convertir de formato center+size a xyxy (min/max corners)
    x1_min = bbox1['x'] - bbox1['width'] / 2
    y1_min = bbox1['y'] - bbox1['height'] / 2
    x1_max = bbox1['x'] + bbox1['width'] / 2
    y1_max = bbox1['y'] + bbox1['height'] / 2

    x2_min = bbox2['x'] - bbox2['width'] / 2
    y2_min = bbox2['y'] - bbox2['height'] / 2
    x2_max = bbox2['x'] + bbox2['width'] / 2
    y2_max = bbox2['y'] + bbox2['height'] / 2

    # Calcular intersección (overlap region)
    inter_x_min = max(x1_min, x2_min)
    inter_y_min = max(y1_min, y2_min)
    inter_x_max = min(x1_max, x2_max)
    inter_y_max = min(y1_max, y2_max)

    # Si no hay overlap, retornar 0
    if inter_x_max < inter_x_min or inter_y_max < inter_y_min:
        return 0.0

    inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)

    # Calcular áreas individuales
    area1 = bbox1['width'] * bbox1['height']
    area2 = bbox2['width'] * bbox2['height']

    # Union = area1 + area2 - intersection
    union_area = area1 + area2 - inter_area

    # Evitar división por cero (edge case: bboxes de tamaño 0)
    if union_area <= 0:
        return 0.0

    return inter_area / union_area

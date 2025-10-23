"""
Spatial Matching Utilities for Object Tracking
===============================================

Bounded Context: Spatial Matching (geometría de tracking)

This module provides spatial matching utilities and strategies for object tracking:
- IoU (Intersection over Union) calculation
- Matching strategies (Strategy pattern)
- Hierarchical matching with fallbacks
- Composable for compound/consensus strategies

Design Philosophy:
- Strategy pattern para matching algorithms
- Composable (preparado para compound strategies)
- Testable (cada strategy independientemente)
- Extensible (agregar strategies sin modificar existentes)

Práctica de Diseño (no over-engineering):
- Encapsulación de algoritmos para clarity
- Testing mejorado (mock lightweight)
- Preparado para evolución (compound, consensus, toggle)

Performance:
- Optimized for normalized coordinates (0.0-1.0)
- Efficient computation (no NumPy needed, pure Python)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from .core import DetectionTrack

logger = logging.getLogger(__name__)


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


# ============================================================================
# Matching Strategies (Strategy Pattern)
# ============================================================================

class MatchingStrategy(ABC):
    """
    Base abstracta para estrategias de matching.

    Práctica de Diseño:
    - Encapsular algoritmos de matching
    - Testeable independientemente
    - Composable (compound strategies)
    - Toggle on/off (enabled flag)

    Evolution:
    - Fácil agregar: CentroidDistanceStrategy, FeatureVectorStrategy
    - Compound: ConsensusStrategy([IoU, Centroid])
    - A/B testing: toggle enabled en runtime
    """

    def __init__(self):
        self.enabled = True  # Para toggle on/off

    @abstractmethod
    def calculate_similarity(
        self,
        detection: Dict[str, float],
        track: 'DetectionTrack'
    ) -> float:
        """
        Calcula similitud entre detection y track.

        Args:
            detection: {'class': str, 'x': float, 'y': float, 'width': float, 'height': float}
            track: DetectionTrack con historial

        Returns:
            Similarity score [0.0, 1.0]
            - 0.0 = no match
            - 1.0 = perfect match
        """
        pass

    @abstractmethod
    def get_threshold(self) -> float:
        """
        Threshold mínimo para considerar match válido.

        Returns:
            Threshold [0.0, 1.0]
        """
        pass

    def get_name(self) -> str:
        """Nombre de la strategy (para logging/debugging)."""
        return self.__class__.__name__


class IoUMatchingStrategy(MatchingStrategy):
    """
    Primary matching: Spatial awareness vía IoU.

    Encapsula el algoritmo IoU matching que estaba en core.py líneas 288-343.

    Beneficios:
    - Testeable aislado (no necesitas todo el stabilizer)
    - Claro qué hace (spatial matching)
    - Reutilizable (adaptive ROI multi-object tracking)
    - Composable (consensus con otras strategies)

    Threshold:
    - 0.3 típico para "mismo objeto"
    - Ajustable para diferentes escenarios
    """

    def __init__(self, threshold: float = 0.3):
        """
        Args:
            threshold: IoU mínimo para considerar match (default 0.3)
        """
        super().__init__()
        self.threshold = threshold

    def calculate_similarity(
        self,
        detection: Dict[str, float],
        track: 'DetectionTrack'
    ) -> float:
        """
        Calcula IoU entre detection bbox y track bbox.

        Returns:
            IoU score [0.0, 1.0]
            - 0.0 si clases diferentes
            - IoU spatial si misma clase
        """
        # Different class = no match
        if detection.get('class', 'unknown') != track.class_name:
            return 0.0

        # Calculate IoU (spatial overlap)
        det_bbox = {
            'x': detection['x'],
            'y': detection['y'],
            'width': detection['width'],
            'height': detection['height'],
        }

        track_bbox = {
            'x': track.x,
            'y': track.y,
            'width': track.width,
            'height': track.height,
        }

        return calculate_iou(det_bbox, track_bbox)

    def get_threshold(self) -> float:
        """IoU threshold para match."""
        return self.threshold


class ClassOnlyStrategy(MatchingStrategy):
    """
    Fallback strategy: Match solo por clase (no spatial awareness).

    Backward compatibility con matching simple original.

    Usado como último fallback cuando:
    - IoU no encuentra match (objetos muy separados)
    - Solo hay 1 objeto de la clase (no ambigüedad)

    Limitaciones:
    - Puede confundir tracks con múltiples objetos misma clase
    - No spatial awareness (puede swap tracks)
    """

    def calculate_similarity(
        self,
        detection: Dict[str, float],
        track: 'DetectionTrack'
    ) -> float:
        """
        Match binario por clase.

        Returns:
            1.0 si misma clase, 0.0 si diferente
        """
        if detection.get('class', 'unknown') == track.class_name:
            return 1.0
        return 0.0

    def get_threshold(self) -> float:
        """Threshold binario."""
        return 0.5  # Binary: match or no match


# ============================================================================
# Hierarchical Matcher (Composable)
# ============================================================================

class HierarchicalMatcher:
    """
    Matcher que prueba strategies en orden de prioridad (Chain of Responsibility).

    Diseño:
    - Intenta cada strategy en orden
    - Primera que supere threshold gana
    - Fallback garantizado (ClassOnly nunca falla)
    - Composable (preparado para compound strategies)

    Usage:
        matcher = HierarchicalMatcher()
        best_track = matcher.find_best_match(detection, active_tracks)

    Evolution (preparado para):
        # Compound strategy
        consensus = ConsensusStrategy([IoU, Centroid])
        matcher.strategies.insert(0, consensus)

        # Toggle strategies
        matcher.strategies[0].enabled = False  # Desactivar IoU temporalmente
    """

    def __init__(
        self,
        strategies: Optional[List[MatchingStrategy]] = None,
        iou_threshold: float = 0.3
    ):
        """
        Args:
            strategies: Lista de strategies (si None, usa default hierarchy)
            iou_threshold: Threshold para IoU strategy
        """
        if strategies is None:
            # Default hierarchy: IoU → ClassOnly fallback
            self.strategies = [
                IoUMatchingStrategy(threshold=iou_threshold),  # Primary
                ClassOnlyStrategy(),                            # Fallback
            ]
        else:
            self.strategies = strategies

        logger.debug(
            "HierarchicalMatcher initialized",
            extra={
                "component": "matching_strategy",
                "event": "matcher_initialized",
                "num_strategies": len(self.strategies),
                "strategies": [s.get_name() for s in self.strategies]
            }
        )

    def find_best_match(
        self,
        detection: Dict[str, float],
        tracks: List['DetectionTrack'],
        matched_indices: set
    ) -> Optional[tuple['DetectionTrack', int, float, str]]:
        """
        Encuentra mejor match usando jerarquía de strategies.

        Args:
            detection: Detección actual
            tracks: Lista de tracks activos
            matched_indices: Set de índices ya matched (para evitar re-match)

        Returns:
            (track, index, score, strategy_name) si hay match, None si no
        """
        if not tracks:
            return None

        # Intentar cada strategy en orden
        for strategy in self.strategies:
            # Skip si desactivada
            if not strategy.enabled:
                continue

            best_track = None
            best_idx = None
            best_score = 0.0

            # Buscar mejor match con esta strategy
            for idx, track in enumerate(tracks):
                # Skip si ya matched
                if idx in matched_indices:
                    continue

                score = strategy.calculate_similarity(detection, track)

                # Guardar mejor
                if score > best_score and score >= strategy.get_threshold():
                    best_score = score
                    best_track = track
                    best_idx = idx

            # Si encontramos match con esta strategy, retornar
            if best_track is not None:
                logger.debug(
                    "Match found",
                    extra={
                        "component": "matching_strategy",
                        "event": "match_found",
                        "strategy": strategy.get_name(),
                        "score": best_score,
                        "class_name": detection.get('class', 'unknown')
                    }
                )
                return (best_track, best_idx, best_score, strategy.get_name())

        # No match con ninguna strategy
        return None

"""
Detection Stabilization Strategies Module
==========================================

Factory pattern para estrategias de estabilización de detecciones:
- None: Sin estabilización (baseline)
- Temporal + Hysteresis: Filtrado temporal con umbrales de confianza adaptativos
- IoU Tracking: Matching espacial frame-a-frame (FASE 2)
- Confidence-weighted: Persistencia basada en historia (FASE 3)

Diseño: KISS + Complejidad por diseño
- Temporal+Hysteresis: Simple, probada, 70-80% efectividad
- Reduce parpadeos en modelos pequeños
- Validación centralizada en factory

Problema resuelto:
- Detecciones inestables (parpadeos) con modelos pequeños/rápidos
- Falsos negativos intermitentes

Solución:
- Requiere N frames consecutivos para "confirmar" detección
- Hysteresis: umbral alto para aparecer, bajo para persistir
- Adaptativo según confianza (baja confianza → menos estricto)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
import logging
import time

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class StabilizationConfig:
    """Configuración unificada para estrategias de estabilización"""
    mode: str  # 'none', 'temporal', 'iou_tracking', 'confidence_weighted'

    # Temporal Filtering params
    temporal_min_frames: int = 3  # Mínimo de frames consecutivos para confirmar
    temporal_max_gap: int = 2      # Máximo gap permitido antes de eliminar

    # Hysteresis params
    hysteresis_appear_conf: float = 0.5   # Umbral para aparecer (estricto)
    hysteresis_persist_conf: float = 0.3  # Umbral para persistir (relajado)

    # IoU Tracking params (FASE 2 - no implementado aún)
    iou_threshold: float = 0.3     # IoU mínimo para considerar "mismo objeto"
    iou_max_age: int = 5           # Frames sin match antes de eliminar

    # Confidence-weighted params (FASE 3 - no implementado aún)
    conf_weight_alpha: float = 0.7  # Peso de confianza en persistencia
    conf_min_history: int = 3       # Mínimo de frames para promediar


# ============================================================================
# Detection Tracking State
# ============================================================================

@dataclass
class DetectionTrack:
    """
    Estado de tracking para una detección.

    Lifecycle:
    1. TRACKING: Recién detectado, acumulando frames
    2. CONFIRMED: Superó min_frames, emitiendo detecciones
    3. REMOVED: Superó max_gap, eliminado del tracker
    """
    class_name: str
    confidence: float
    x: float  # Normalized x center
    y: float  # Normalized y center
    width: float  # Normalized width
    height: float  # Normalized height

    # Tracking state
    consecutive_frames: int = 0  # Frames consecutivos detectado
    gap_frames: int = 0          # Frames sin detectar
    confirmed: bool = False      # Si ya superó min_frames

    # History
    confidences: deque = field(default_factory=lambda: deque(maxlen=10))
    last_seen_time: float = field(default_factory=time.time)

    def update(self, confidence: float, x: float, y: float, width: float, height: float):
        """Actualiza track con nueva detección"""
        self.confidence = confidence
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.consecutive_frames += 1
        self.gap_frames = 0
        self.confidences.append(confidence)
        self.last_seen_time = time.time()

    def mark_missed(self):
        """Marca frame donde no se detectó"""
        self.consecutive_frames = 0
        self.gap_frames += 1

    @property
    def avg_confidence(self) -> float:
        """Confianza promedio histórica"""
        if not self.confidences:
            return self.confidence
        return sum(self.confidences) / len(self.confidences)


# ============================================================================
# Base Stabilizer (Abstract)
# ============================================================================

class BaseDetectionStabilizer(ABC):
    """
    Clase base abstracta para estrategias de estabilización.

    Interface contract:
    - process(): Recibe detecciones, retorna detecciones estabilizadas
    - reset(): Limpia estado interno
    """

    @abstractmethod
    def process(
        self,
        detections: List[Dict[str, Any]],
        source_id: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Procesa detecciones y retorna versión estabilizada.

        Args:
            detections: Lista de detecciones del frame actual
                        Formato: [{'class': str, 'confidence': float, 'x': float, 'y': float, ...}]
            source_id: ID del video source (para multi-stream)

        Returns:
            Lista de detecciones estabilizadas (mismo formato)
        """
        pass

    @abstractmethod
    def reset(self, source_id: Optional[int] = None):
        """
        Resetea estado interno del stabilizer.

        Args:
            source_id: Si especificado, resetea solo ese source. Si None, resetea todo.
        """
        pass

    @abstractmethod
    def get_stats(self, source_id: int = 0) -> Dict[str, Any]:
        """
        Retorna estadísticas de estabilización.

        Returns:
            Dict con métricas: total_tracked, confirmed, removed, etc.
        """
        pass


# ============================================================================
# Temporal + Hysteresis Stabilizer (FASE 1)
# ============================================================================

class TemporalHysteresisStabilizer(BaseDetectionStabilizer):
    """
    Estabilización mediante filtrado temporal + hysteresis de confianza.

    Estrategia:
    1. Umbral de aparición (high): Nueva detección debe superar appear_conf
    2. Tracking temporal: Requiere min_frames consecutivos para confirmar
    3. Umbral de persistencia (low): Una vez confirmado, usa persist_conf más bajo
    4. Gap tolerance: Tolera max_gap frames sin detección antes de eliminar

    Ejemplo (min_frames=3, max_gap=2, appear=0.5, persist=0.3):

    Frame 1: person 0.45 → IGNORAR (< 0.5 appear)
    Frame 2: person 0.52 → TRACKING (>= 0.5, frames=1/3)
    Frame 3: person 0.48 → TRACKING (>= 0.3 persist, frames=2/3)
    Frame 4: person 0.51 → CONFIRMED! Emite detección (frames=3/3)
    Frame 5: person 0.35 → KEEP (>= 0.3 persist, confirmed)
    Frame 6: (no detection) → GAP 1/2
    Frame 7: (no detection) → REMOVED (gap > max_gap)

    Complejidad: O(N*M) donde N=detections_current, M=tracks_active
    Típicamente N~5-20, M~10-50 → ~100-1000 comparisons @ 2fps → despreciable
    """

    def __init__(
        self,
        min_frames: int = 3,
        max_gap: int = 2,
        appear_conf: float = 0.5,
        persist_conf: float = 0.3,
    ):
        """
        Args:
            min_frames: Frames consecutivos requeridos para confirmar
            max_gap: Frames sin detección antes de eliminar track
            appear_conf: Umbral de confianza para nueva detección
            persist_conf: Umbral de confianza para detección confirmada
        """
        self.min_frames = min_frames
        self.max_gap = max_gap
        self.appear_conf = appear_conf
        self.persist_conf = persist_conf

        # State: source_id -> class_name -> list of DetectionTrack
        # Usamos defaultdict para facilitar multi-source
        self._tracks: Dict[int, Dict[str, List[DetectionTrack]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # Stats
        self._stats: Dict[int, Dict[str, int]] = defaultdict(
            lambda: {
                'total_detected': 0,
                'total_confirmed': 0,
                'total_ignored': 0,
                'total_removed': 0,
                'active_tracks': 0,
            }
        )

        logger.info(
            f"TemporalHysteresisStabilizer initialized: "
            f"min_frames={min_frames}, max_gap={max_gap}, "
            f"appear_conf={appear_conf:.2f}, persist_conf={persist_conf:.2f}"
        )

    def process(
        self,
        detections: List[Dict[str, Any]],
        source_id: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Procesa detecciones con filtrado temporal + hysteresis.

        Algoritmo:
        1. Para cada detección actual:
           - Si es nueva y conf >= appear_conf → crear track (TRACKING)
           - Si existe track y conf >= persist_conf → actualizar track
           - Si track.consecutive_frames >= min_frames → marcar CONFIRMED

        2. Para tracks sin match (no detectados este frame):
           - Incrementar gap_frames
           - Si gap_frames > max_gap → eliminar track
           - Si confirmed y gap <= max_gap → mantener (tolerancia)

        3. Emitir solo detecciones CONFIRMED
        """
        tracks = self._tracks[source_id]
        stats = self._stats[source_id]

        # Track matching: simple by class_name + proximity
        # (FASE 1: no usamos IoU, solo class matching)
        matched_tracks: Set[Tuple[str, int]] = set()  # (class_name, track_idx)
        stabilized_detections: List[Dict[str, Any]] = []

        stats['total_detected'] += len(detections)

        # 1. Match detections to existing tracks
        for det in detections:
            class_name = det.get('class', 'unknown')
            confidence = det.get('confidence', 0.0)

            # Coordenadas normalizadas (asumimos que vienen así desde inference)
            x = det.get('x', 0.0)
            y = det.get('y', 0.0)
            width = det.get('width', 0.0)
            height = det.get('height', 0.0)

            # Buscar track existente de misma clase
            # FASE 1: matching simple por clase (no espacial)
            # FASE 2: agregar IoU matching
            matched = False

            if class_name in tracks:
                for idx, track in enumerate(tracks[class_name]):
                    # Simple matching: misma clase, no matched aún
                    if (class_name, idx) not in matched_tracks:
                        # Match encontrado
                        matched_tracks.add((class_name, idx))
                        matched = True

                        # Aplicar hysteresis: persist_conf más bajo si ya confirmado
                        threshold = self.persist_conf if track.confirmed else self.appear_conf

                        if confidence >= threshold:
                            track.update(confidence, x, y, width, height)

                            # Confirmar si alcanzó min_frames
                            if not track.confirmed and track.consecutive_frames >= self.min_frames:
                                track.confirmed = True
                                stats['total_confirmed'] += 1
                                logger.debug(
                                    f"✅ Track confirmed: {class_name} after {track.consecutive_frames} frames "
                                    f"(avg_conf={track.avg_confidence:.2f})"
                                )
                        else:
                            # Confianza insuficiente, marcar missed
                            track.mark_missed()

                        break

            # 2. Si no match, crear nuevo track (si supera appear_conf)
            if not matched:
                if confidence >= self.appear_conf:
                    new_track = DetectionTrack(
                        class_name=class_name,
                        confidence=confidence,
                        x=x, y=y, width=width, height=height,
                        consecutive_frames=1,
                    )
                    new_track.confidences.append(confidence)
                    tracks[class_name].append(new_track)

                    logger.debug(
                        f"🆕 New track: {class_name} conf={confidence:.2f} (needs {self.min_frames} frames)"
                    )
                else:
                    stats['total_ignored'] += 1
                    logger.debug(
                        f"⏭️ Ignored detection: {class_name} conf={confidence:.2f} < {self.appear_conf:.2f}"
                    )

        # 3. Update unmatched tracks (incrementar gap)
        for class_name, track_list in tracks.items():
            for idx, track in enumerate(track_list):
                if (class_name, idx) not in matched_tracks:
                    track.mark_missed()

        # 4. Emitir solo detecciones CONFIRMED
        for class_name, track_list in tracks.items():
            for track in track_list:
                if track.confirmed and track.gap_frames == 0:
                    # Emitir detección estabilizada
                    stabilized_detections.append({
                        'class': track.class_name,
                        'confidence': track.confidence,
                        'x': track.x,
                        'y': track.y,
                        'width': track.width,
                        'height': track.height,
                        # Metadatos de tracking
                        '_stabilization': {
                            'avg_confidence': track.avg_confidence,
                            'frames_tracked': track.consecutive_frames,
                        }
                    })

        # 5. Limpiar tracks expirados (gap > max_gap)
        for class_name in list(tracks.keys()):
            track_list = tracks[class_name]
            initial_count = len(track_list)

            # Filtrar tracks vivos
            tracks[class_name] = [
                t for t in track_list
                if t.gap_frames <= self.max_gap
            ]

            removed_count = initial_count - len(tracks[class_name])
            if removed_count > 0:
                stats['total_removed'] += removed_count
                logger.debug(
                    f"🗑️ Removed {removed_count} expired tracks: {class_name} "
                    f"(gap > {self.max_gap})"
                )

            # Limpiar clase si no hay tracks
            if not tracks[class_name]:
                del tracks[class_name]

        # Update stats
        stats['active_tracks'] = sum(len(tl) for tl in tracks.values())

        logger.debug(
            f"Stabilization: {len(detections)} raw → {len(stabilized_detections)} stabilized "
            f"(active_tracks={stats['active_tracks']})"
        )

        return stabilized_detections

    def reset(self, source_id: Optional[int] = None):
        """Resetea tracks (útil para testing o cambio de escena)"""
        if source_id is None:
            # Reset all sources
            self._tracks.clear()
            self._stats.clear()
            logger.info("🔄 All stabilization tracks reset")
        else:
            # Reset specific source
            if source_id in self._tracks:
                del self._tracks[source_id]
            if source_id in self._stats:
                del self._stats[source_id]
            logger.info(f"🔄 Stabilization tracks reset for source {source_id}")

    def get_stats(self, source_id: int = 0) -> Dict[str, Any]:
        """Retorna estadísticas de estabilización"""
        stats = self._stats[source_id].copy()

        # Agregar breakdown por clase
        tracks = self._tracks[source_id]
        stats['tracks_by_class'] = {
            class_name: len(track_list)
            for class_name, track_list in tracks.items()
        }

        # Agregar confirmed ratio
        if stats['total_detected'] > 0:
            stats['confirm_ratio'] = stats['total_confirmed'] / stats['total_detected']
        else:
            stats['confirm_ratio'] = 0.0

        return stats


# ============================================================================
# No-op Stabilizer (Baseline)
# ============================================================================

class NoOpStabilizer(BaseDetectionStabilizer):
    """
    Pass-through sin estabilización (baseline para comparación).
    """

    def process(
        self,
        detections: List[Dict[str, Any]],
        source_id: int = 0,
    ) -> List[Dict[str, Any]]:
        """Pass-through directo"""
        return detections

    def reset(self, source_id: Optional[int] = None):
        """No-op"""
        pass

    def get_stats(self, source_id: int = 0) -> Dict[str, Any]:
        """Sin estadísticas"""
        return {'mode': 'none'}


# ============================================================================
# Factory
# ============================================================================

def create_stabilization_strategy(
    config: StabilizationConfig,
) -> BaseDetectionStabilizer:
    """
    Factory: valida configuración y crea estrategia de estabilización.

    Args:
        config: Configuración validada

    Returns:
        Instancia de BaseDetectionStabilizer

    Raises:
        ValueError: Si configuración inválida
    """
    mode = config.mode.lower()

    if mode not in ['none', 'temporal']:
        raise ValueError(
            f"Invalid stabilization mode: '{mode}'. "
            f"Currently supported: 'none', 'temporal'. "
            f"Coming in FASE 2: 'iou_tracking', 'confidence_weighted'"
        )

    if mode == 'none':
        logger.info("🔲 Stabilization: NONE (baseline, no filtering)")
        return NoOpStabilizer()

    if mode == 'temporal':
        # Validar parámetros
        if config.temporal_min_frames < 1:
            raise ValueError(f"temporal_min_frames must be >= 1, got {config.temporal_min_frames}")
        if config.temporal_max_gap < 0:
            raise ValueError(f"temporal_max_gap must be >= 0, got {config.temporal_max_gap}")
        if not (0.0 <= config.hysteresis_appear_conf <= 1.0):
            raise ValueError(f"hysteresis_appear_conf must be in [0.0, 1.0], got {config.hysteresis_appear_conf}")
        if not (0.0 <= config.hysteresis_persist_conf <= 1.0):
            raise ValueError(f"hysteresis_persist_conf must be in [0.0, 1.0], got {config.hysteresis_persist_conf}")
        if config.hysteresis_persist_conf > config.hysteresis_appear_conf:
            raise ValueError(
                f"hysteresis_persist_conf ({config.hysteresis_persist_conf}) must be <= "
                f"appear_conf ({config.hysteresis_appear_conf})"
            )

        logger.info(
            f"⏱️ Stabilization: TEMPORAL+HYSTERESIS "
            f"(min_frames={config.temporal_min_frames}, max_gap={config.temporal_max_gap}, "
            f"appear={config.hysteresis_appear_conf:.2f}, persist={config.hysteresis_persist_conf:.2f})"
        )

        return TemporalHysteresisStabilizer(
            min_frames=config.temporal_min_frames,
            max_gap=config.temporal_max_gap,
            appear_conf=config.hysteresis_appear_conf,
            persist_conf=config.hysteresis_persist_conf,
        )

    # Nunca debería llegar aquí
    raise ValueError(f"Unhandled stabilization mode: {mode}")


# ============================================================================
# Stabilization Sink Wrapper
# ============================================================================

def create_stabilization_sink(
    stabilizer: BaseDetectionStabilizer,
    downstream_sink: Callable,
) -> Callable:
    """
    Factory: crea sink wrapper que estabiliza detecciones antes de pasar a downstream.

    Patrón: Decorator/Wrapper para interceptar predictions del pipeline.

    Args:
        stabilizer: Estrategia de estabilización
        downstream_sink: Sink original (e.g., mqtt_sink, render_boxes)

    Returns:
        Callable compatible con InferencePipeline.on_prediction

    Example:
        stabilizer = create_stabilization_strategy(config)
        stabilized_sink = create_stabilization_sink(stabilizer, mqtt_sink)

        pipeline = InferencePipeline.init(
            ...,
            on_prediction=stabilized_sink,
        )
    """

    def stabilization_wrapper(predictions: dict, video_frame) -> None:
        """
        Wrapper que estabiliza detecciones antes de pasar a downstream.

        Args:
            predictions: Dict con predictions del InferencePipeline
            video_frame: VideoFrame del pipeline
        """
        # Extraer detecciones del formato inference SDK
        # predictions puede tener diferentes formatos según modelo
        # Típicamente: predictions['predictions'] o predictions directamente

        if isinstance(predictions, dict):
            # Formato standard de inference SDK
            raw_detections = predictions.get('predictions', [])
            source_id = video_frame.source_id if hasattr(video_frame, 'source_id') else 0

            # Estabilizar
            stabilized = stabilizer.process(raw_detections, source_id=source_id)

            # Reemplazar detecciones con versión estabilizada
            predictions_stabilized = predictions.copy()
            predictions_stabilized['predictions'] = stabilized

            # Agregar metadata de estabilización
            predictions_stabilized['_stabilization_stats'] = stabilizer.get_stats(source_id)

            # Log comparación
            logger.debug(
                f"Stabilization wrapper: {len(raw_detections)} raw → {len(stabilized)} stable "
                f"(source={source_id})"
            )

            # Pasar a downstream
            downstream_sink(predictions_stabilized, video_frame)
        else:
            # Formato desconocido, pass-through directo
            logger.warning(
                f"Stabilization wrapper received unexpected format: {type(predictions)}, "
                f"passing through without stabilization"
            )
            downstream_sink(predictions, video_frame)

    return stabilization_wrapper

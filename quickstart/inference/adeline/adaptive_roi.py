"""
Adaptive ROI Module - Custom Inference Logic
============================================

Este módulo solo se carga si adaptive_crop.enabled = true en config.yaml

Features:
- Dynamic crop basado en detecciones previas
- Temporal smoothing del ROI
- Optimizaciones NumPy/Supervision
- Toggle dinámico vía MQTT

Usage:
    # En config.yaml
    adaptive_crop:
      enabled: true
      margin: 0.2
      smoothing: 0.3

    # MQTT command (solo si enabled)
    {"command": "toggle_crop"}

Performance Optimizations:
- NumPy views para crop (zero-copy)
- Operaciones vectorizadas para bbox calculations
- Supervision utilities para coordinate transforms
"""

from typing import List, Dict, Optional, Tuple, Union
from dataclasses import dataclass
import logging

import cv2
import numpy as np
import supervision as sv
from inference.core.interfaces.camera.entities import VideoFrame

logger = logging.getLogger(__name__)

# Track sources que ya mostraron log de resize (para no spamear logs)
_resize_logged_sources = set()


# ============================================================================
# ROI Data Structures
# ============================================================================

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


# ============================================================================
# ROI State Manager
# ============================================================================

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


# ============================================================================
# Optimized Crop Functions
# ============================================================================

def crop_frame_if_roi(
    video_frame: VideoFrame,
    roi: Optional[ROIBox],
    model_size: Optional[int] = None,
    resize_to_model: bool = False,
) -> Tuple[VideoFrame, Optional[Tuple[int, int]]]:
    """
    Crop eficiente usando numpy view (sin copia), con resize opcional.

    Performance: NumPy slicing crea VIEW, no copia datos - muy eficiente.

    Resize Strategy (resize_to_model=True):
    - Si ROI < model_size: Resize (zoom) a model_size×model_size
    - Si ROI >= model_size: Sin resize (model hace padding/resize automático)
    - Trade-off: Mejor detección pequeña vs. pérdida de escala original

    Args:
        video_frame: Frame original
        roi: ROI a aplicar, o None para frame completo
        model_size: Tamaño del modelo (ej: 320, 640) para resize
        resize_to_model: Si True, resize ROI a model_size (zoom). Si False, padding con negro.

    Returns:
        (cropped_frame, (offset_x, offset_y)) o (original_frame, None)
    """
    if roi is None:
        return video_frame, None

    # Numpy slicing crea VIEW (no copia) - muy eficiente
    cropped_image = video_frame.image[roi.y1:roi.y2, roi.x1:roi.x2]

    # Validar crop no vacío
    if cropped_image.size == 0:
        logger.warning(f"Empty crop for ROI {roi}, using full frame")
        return video_frame, None

    # Resize condicional (solo si resize_to_model=True y ROI < model_size)
    if resize_to_model and model_size is not None:
        roi_size = max(cropped_image.shape[0], cropped_image.shape[1])

        if roi_size < model_size:
            # Zoom: resize a model_size×model_size
            # INTER_LINEAR es buen balance entre calidad y performance
            original_size = roi_size
            cropped_image = cv2.resize(
                cropped_image,
                (model_size, model_size),
                interpolation=cv2.INTER_LINEAR
            )

            # Log solo la primera vez por source (evitar spam en logs)
            source_id = video_frame.source_id
            if source_id not in _resize_logged_sources:
                logger.info(
                    f"🔍 Zoom aplicado (source {source_id}): "
                    f"ROI {original_size}×{original_size} → {model_size}×{model_size}"
                )
                _resize_logged_sources.add(source_id)

    # Nuevo VideoFrame (solo metadata nueva, imagen es view o resized)
    cropped_frame = VideoFrame(
        image=cropped_image,
        frame_id=video_frame.frame_id,
        frame_timestamp=video_frame.frame_timestamp,
        source_id=video_frame.source_id,
    )

    return cropped_frame, (roi.x1, roi.y1)


def transform_predictions_vectorized(
    predictions: dict,
    crop_offset: Optional[Tuple[int, int]],
) -> dict:
    """
    Transforma coordenadas usando operaciones vectorizadas.

    Performance: ~20x más rápido que loop en Python puro.

    Args:
        predictions: Dict con predictions de modelo Roboflow
        crop_offset: (x_offset, y_offset) del crop, o None si no hay crop

    Returns:
        predictions con coordenadas transformadas al frame original
    """
    if crop_offset is None or 'predictions' not in predictions:
        return predictions

    x_offset, y_offset = crop_offset
    detections_list = predictions['predictions']

    if not detections_list:
        return predictions

    # Extraer coordenadas en arrays numpy (más eficiente que loop)
    xs = np.array([d['x'] for d in detections_list])
    ys = np.array([d['y'] for d in detections_list])

    # Operación vectorizada: suma broadcast
    xs += x_offset
    ys += y_offset

    # Actualizar in-place (evita crear nuevo dict)
    for i, det in enumerate(detections_list):
        det['x'] = float(xs[i])  # numpy float64 -> Python float
        det['y'] = float(ys[i])

    return predictions


def convert_predictions_to_sv_detections(predictions: dict) -> sv.Detections:
    """
    Convierte predictions dict a sv.Detections para usar supervision utils.

    Optimizado con operaciones vectorizadas.

    Args:
        predictions: Dict con formato Roboflow standard

    Returns:
        sv.Detections object
    """
    detections_list = predictions.get('predictions', [])

    if not detections_list:
        return sv.Detections.empty()

    # Operaciones vectorizadas para construir xyxy
    n = len(detections_list)
    xyxy = np.zeros((n, 4), dtype=np.float32)

    # Extraer en paralelo (list comprehension más rápida que loop)
    xs = np.array([d['x'] for d in detections_list], dtype=np.float32)
    ys = np.array([d['y'] for d in detections_list], dtype=np.float32)
    ws = np.array([d['width'] for d in detections_list], dtype=np.float32)
    hs = np.array([d['height'] for d in detections_list], dtype=np.float32)

    # Operaciones vectorizadas: (x,y,w,h) -> (x1,y1,x2,y2)
    xyxy[:, 0] = xs - ws / 2  # x1
    xyxy[:, 1] = ys - hs / 2  # y1
    xyxy[:, 2] = xs + ws / 2  # x2
    xyxy[:, 3] = ys + hs / 2  # y2

    confidence = np.array([d.get('confidence', 1.0) for d in detections_list], dtype=np.float32)
    class_id = np.array([d.get('class_id', 0) for d in detections_list], dtype=int)

    return sv.Detections(
        xyxy=xyxy,
        confidence=confidence,
        class_id=class_id,
    )


# ============================================================================
# Main Inference Pipeline
# ============================================================================

def adaptive_roi_inference(
    video_frames: List[VideoFrame],
    model,
    inference_config,
    roi_state: ROIState,
    enable_crop: bool = True,
    process_frame_fn=None,
    show_statistics: bool = True,
) -> List[dict]:
    """
    Pipeline de inferencia con crop adaptativo optimizado.

    Flow por frame:
    1. Get ROI del estado compartido
    2. Crop eficiente (numpy view - zero copy)
    3. Inferencia con modelo (Roboflow o local ONNX)
    4. Transform coords de vuelta al frame original (vectorizado)
    5. Agregar métricas de ROI/performance (opcional, según show_statistics)

    Performance optimizations:
    - NumPy views para crop (no copia)
    - Operaciones vectorizadas para coordenadas
    - Supervision utilities para bbox ops
    - Metrics computation opcional (desactivar en producción para mejor performance)

    Args:
        video_frames: Batch de frames a procesar
        model: Modelo de inferencia (Roboflow o LocalONNXModel)
        inference_config: Configuración del modelo
        roi_state: Estado compartido de ROI
        enable_crop: Flag para habilitar/deshabilitar crop
        process_frame_fn: Función para procesar frames (auto-detectada si None)
        show_statistics: Si calcular y publicar métricas de performance (default: True)

    Returns:
        Lista de predictions (formato Roboflow standard) con métricas de ROI (si show_statistics=True)
    """
    # Auto-detectar función de procesamiento si no se provee
    if process_frame_fn is None:
        from inference.core.interfaces.stream.model_handlers.roboflow_models import (
            default_process_frame,
        )
        process_frame_fn = default_process_frame

    results = []

    for video_frame in video_frames:
        # 1. Get ROI del estado
        roi = None
        if enable_crop:
            # Soporte para ROIState (adaptive) y FixedROIState (fixed)
            # FixedROIState necesita frame_shape para convertir coords normalizadas
            frame_shape = video_frame.image.shape[:2]

            # Intentar llamar con frame_shape (FixedROIState)
            try:
                roi = roi_state.get_roi(source_id=video_frame.source_id, frame_shape=frame_shape)
            except TypeError:
                # Fallback: ROIState (adaptive) solo necesita source_id
                roi = roi_state.get_roi(source_id=video_frame.source_id)

        # 2. Crop eficiente (numpy view) + resize opcional
        model_size = getattr(roi_state, '_imgsz', None)
        resize_to_model = getattr(roi_state, 'resize_to_model', False)
        frame_to_infer, crop_offset = crop_frame_if_roi(
            video_frame,
            roi,
            model_size=model_size,
            resize_to_model=resize_to_model,
        )

        # 3. Inferencia (función configurable: Roboflow o local ONNX)
        prediction = process_frame_fn(
            [frame_to_infer],
            model=model,
            inference_config=inference_config
        )[0]

        # 4. Transform coords (vectorizado)
        prediction = transform_predictions_vectorized(prediction, crop_offset)

        # 5. Metadata + métricas para monitoring/debugging (solo si show_statistics=True)
        if show_statistics:
            frame_shape = video_frame.image.shape[:2]
            crop_metadata = {
                'enabled': enable_crop,
                'crop_applied': crop_offset is not None,
                'crop_offset': crop_offset,
            }

            if roi:
                # Métricas del ROI
                crop_metadata['roi'] = {
                    'x1': roi.x1,
                    'y1': roi.y1,
                    'x2': roi.x2,
                    'y2': roi.y2,
                    'width': roi.width,
                    'height': roi.height,
                    'area': roi.area,
                    'is_square': roi.is_square,
                }

                # Performance metrics
                # Soporte para ROIState (adaptive) y FixedROIState (fixed)
                imgsz = getattr(roi_state, '_imgsz', None)
                crop_metadata['performance'] = {
                    'imgsz': imgsz,
                    'size_multiple': roi.get_size_multiple(imgsz) if imgsz else None,
                    'crop_ratio': roi.get_crop_ratio(frame_shape),
                    'pixel_reduction': 1.0 - roi.get_crop_ratio(frame_shape),
                    'frame_size': {'height': frame_shape[0], 'width': frame_shape[1]},
                }
            else:
                # Full frame (no crop)
                imgsz = getattr(roi_state, '_imgsz', None)
                crop_metadata['roi'] = None
                crop_metadata['performance'] = {
                    'imgsz': imgsz,
                    'size_multiple': 0.0,  # No crop
                    'crop_ratio': 1.0,  # Full frame
                    'pixel_reduction': 0.0,  # No reduction
                    'frame_size': {'height': frame_shape[0], 'width': frame_shape[1]},
                }

            prediction['__crop_metadata__'] = crop_metadata

        results.append(prediction)

    return results


# ============================================================================
# Sink for ROI Update
# ============================================================================

def roi_update_sink(
    predictions: Union[dict, List[Optional[dict]]],
    video_frames: Union[VideoFrame, List[Optional[VideoFrame]]],
    roi_state: ROIState,
):
    """
    Sink que actualiza ROI state basado en detecciones.

    Este sink NO hace I/O, solo actualiza estado compartido.
    Debe combinarse con otros sinks usando multi_sink.

    Args:
        predictions: Predictions del modelo
        video_frames: Frames correspondientes
        roi_state: Estado compartido de ROI
    """
    # Normalizar a listas (para compatibilidad con SinkMode.ADAPTIVE)
    if not isinstance(predictions, list):
        predictions = [predictions]
        video_frames = [video_frames]

    for prediction, video_frame in zip(predictions, video_frames):
        if prediction is None or video_frame is None:
            continue

        # Convertir a sv.Detections (operaciones vectorizadas)
        detections = convert_predictions_to_sv_detections(prediction)

        # Actualizar ROI (operaciones numpy optimizadas)
        roi_state.update_from_detections(
            source_id=video_frame.source_id,
            detections=detections,
            frame_shape=video_frame.image.shape[:2],
        )


# ============================================================================
# Adaptive Inference Handler (Mutable for MQTT Toggle)
# ============================================================================

class AdaptiveInferenceHandler:
    """
    Wrapper callable para adaptive_roi_inference que permite toggle dinámico.

    Este wrapper es necesario porque InferencePipeline.init_with_custom_logic()
    espera un callable, pero necesitamos poder cambiar el flag 'enabled' en runtime
    (vía MQTT command).

    Usage:
        handler = AdaptiveInferenceHandler(model, config, roi_state)
        pipeline = InferencePipeline.init_with_custom_logic(
            on_video_frame=handler,  # callable
            ...
        )

        # Luego, desde MQTT callback:
        handler.enabled = False  # Disable crop dinámicamente
    """

    def __init__(
        self,
        model,
        inference_config,
        roi_state: ROIState,
        process_frame_fn=None,
        show_statistics: bool = True,
    ):
        self.model = model
        self.inference_config = inference_config
        self.roi_state = roi_state
        self.process_frame_fn = process_frame_fn
        self.enabled = True  # Mutable flag
        self.show_statistics = show_statistics  # Performance optimization flag

    def __call__(self, video_frames: List[VideoFrame]) -> List[dict]:
        """Callable interface para InferencePipeline"""
        return adaptive_roi_inference(
            video_frames=video_frames,
            model=self.model,
            inference_config=self.inference_config,
            roi_state=self.roi_state,
            enable_crop=self.enabled,  # Lee el flag actual
            process_frame_fn=self.process_frame_fn,
            show_statistics=self.show_statistics,  # Control metrics computation
        )

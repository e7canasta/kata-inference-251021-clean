"""
Custom Visualization for InferencePipeline
===========================================

Render simple pero bien diseñado que muestra:
- Bounding boxes de detecciones
- ROI (zona de atención) cuando está activo
- Estadísticas básicas

Philosophy: KISS - Keep It Simple, Stupid
- Una ventana única con toda la info
- Funciones auxiliares pequeñas y enfocadas
- Sin abstracciones innecesarias
"""

from typing import Union, List, Optional
import cv2
import numpy as np
from inference.core.interfaces.camera.entities import VideoFrame


# ============================================================================
# Color Palette (BGR format for OpenCV)
# ============================================================================
COLORS = {
    'bbox': (0, 255, 255),      # Amarillo para detecciones
    'roi': (0, 255, 0),         # Verde para ROI
    'text_bg': (0, 0, 0),       # Negro para fondo de texto
    'text_fg': (255, 255, 255), # Blanco para texto
    'roi_text': (0, 255, 0),    # Verde para texto de ROI
}


# ============================================================================
# Drawing Utilities
# ============================================================================

def draw_bbox(image: np.ndarray, detection: dict, color: tuple = COLORS['bbox']) -> None:
    """
    Dibuja una bounding box con etiqueta.

    Args:
        image: Frame donde dibujar (se modifica in-place)
        detection: Dict con 'x', 'y', 'width', 'height', 'class', 'confidence'
        color: Color BGR para la bbox
    """
    # Extraer coordenadas (formato center x,y + width,height)
    x_center = int(detection['x'])
    y_center = int(detection['y'])
    width = int(detection['width'])
    height = int(detection['height'])

    # Convertir a esquinas
    x1 = x_center - width // 2
    y1 = y_center - height // 2
    x2 = x_center + width // 2
    y2 = y_center + height // 2

    # Dibujar rectángulo
    cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

    # Preparar etiqueta
    class_name = detection.get('class', 'unknown')
    confidence = detection.get('confidence', 0.0)
    label = f"{class_name} {confidence:.2f}"

    # Dibujar etiqueta con fondo
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    thickness = 1

    (text_w, text_h), _ = cv2.getTextSize(label, font, font_scale, thickness)

    # Fondo negro para texto
    cv2.rectangle(
        image,
        (x1, y1 - text_h - 8),
        (x1 + text_w + 4, y1),
        COLORS['text_bg'],
        -1
    )

    # Texto blanco
    cv2.putText(
        image,
        label,
        (x1 + 2, y1 - 4),
        font,
        font_scale,
        COLORS['text_fg'],
        thickness
    )


def draw_roi_box(image: np.ndarray, roi, color: tuple = COLORS['roi']) -> None:
    """
    Dibuja el ROI (zona de atención) con etiqueta.

    Args:
        image: Frame donde dibujar (se modifica in-place)
        roi: ROIBox object con x1, y1, x2, y2
        color: Color BGR para el ROI
    """
    # Dibujar rectángulo del ROI
    cv2.rectangle(image, (roi.x1, roi.y1), (roi.x2, roi.y2), color, 2)

    # Etiqueta del ROI
    label = f"Attention Zone: {roi.width}x{roi.height}px"
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.6
    thickness = 2

    (text_w, text_h), _ = cv2.getTextSize(label, font, font_scale, thickness)

    # Posicionar texto arriba del ROI (o abajo si no hay espacio)
    text_x = roi.x1
    text_y = roi.y1 - 10
    if text_y < text_h + 10:
        text_y = roi.y1 + text_h + 10

    # Fondo negro para texto
    cv2.rectangle(
        image,
        (text_x, text_y - text_h - 5),
        (text_x + text_w + 5, text_y + 5),
        COLORS['text_bg'],
        -1
    )

    # Texto verde
    cv2.putText(
        image,
        label,
        (text_x, text_y),
        font,
        font_scale,
        COLORS['roi_text'],
        thickness
    )


def draw_stats_overlay(
    image: np.ndarray,
    detection_count: int,
    frame_id: Optional[int] = None,
    source_id: Optional[int] = None,
) -> None:
    """
    Dibuja estadísticas básicas en la esquina superior.

    Args:
        image: Frame donde dibujar (se modifica in-place)
        detection_count: Número de detecciones
        frame_id: ID del frame (opcional)
        source_id: ID de la fuente (opcional)
    """
    # Preparar líneas de texto
    lines = [f"Detections: {detection_count}"]

    if source_id is not None:
        lines.append(f"Source: {source_id}")

    if frame_id is not None:
        lines.append(f"Frame: {frame_id}")

    # Configuración de texto
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    thickness = 1
    line_height = 20
    padding = 5

    # Calcular dimensiones del overlay
    max_width = max(cv2.getTextSize(line, font, font_scale, thickness)[0][0] for line in lines)
    overlay_height = len(lines) * line_height + padding * 2
    overlay_width = max_width + padding * 2

    # Dibujar fondo semi-transparente
    overlay = image.copy()
    cv2.rectangle(
        overlay,
        (0, 0),
        (overlay_width, overlay_height),
        COLORS['text_bg'],
        -1
    )
    cv2.addWeighted(overlay, 0.7, image, 0.3, 0, image)

    # Dibujar líneas de texto
    y = padding + 15
    for line in lines:
        cv2.putText(
            image,
            line,
            (padding, y),
            font,
            font_scale,
            COLORS['text_fg'],
            thickness
        )
        y += line_height


# ============================================================================
# Main Render Function
# ============================================================================

def render_predictions_with_roi(
    predictions: Union[dict, List[Optional[dict]]],
    video_frames: Union[VideoFrame, List[Optional[VideoFrame]]],
    roi_state: Optional['ROIState'] = None,
    inference_handler: Optional['AdaptiveInferenceHandler'] = None,
    display_stats: bool = True,
    window_name: str = "Inference Pipeline",
) -> None:
    """
    Render principal que dibuja detecciones + ROI en una sola ventana.

    Philosophy: KISS
    - Una sola ventana con toda la información
    - Código directo sin abstracciones innecesarias
    - Funciones auxiliares pequeñas y enfocadas

    Args:
        predictions: Predictions del modelo (dict o lista)
        video_frames: Frame(s) de video
        roi_state: Estado del ROI (opcional, para mostrar zona de atención)
        inference_handler: Handler de inferencia (opcional, para verificar si crop está activo)
        display_stats: Si mostrar estadísticas básicas
        window_name: Nombre de la ventana
    """
    # Normalizar a listas
    if not isinstance(predictions, list):
        predictions = [predictions]
        video_frames = [video_frames]

    # Procesar cada frame
    for prediction, video_frame in zip(predictions, video_frames):
        if prediction is None or video_frame is None:
            continue

        # Clonar frame para no modificar el original
        display_frame = video_frame.image.copy()

        # 1. Dibujar detecciones
        detections_list = prediction.get('predictions', [])
        for detection in detections_list:
            draw_bbox(display_frame, detection)

        # 2. Dibujar ROI si está activo
        if roi_state and inference_handler and inference_handler.enabled:
            # Soporte para ROIState (adaptive) y FixedROIState (fixed)
            frame_shape = video_frame.image.shape[:2]

            # Intentar con frame_shape (FixedROIState lo necesita)
            try:
                roi = roi_state.get_roi(source_id=video_frame.source_id, frame_shape=frame_shape)
            except TypeError:
                # Fallback: ROIState (adaptive) solo necesita source_id
                roi = roi_state.get_roi(source_id=video_frame.source_id)

            if roi is not None:
                draw_roi_box(display_frame, roi)

        # 3. Dibujar estadísticas
        if display_stats:
            draw_stats_overlay(
                display_frame,
                detection_count=len(detections_list),
                frame_id=video_frame.frame_id,
                source_id=video_frame.source_id,
            )

        # 4. Mostrar frame
        cv2.imshow(window_name, display_frame)
        cv2.waitKey(1)


# ============================================================================
# Sink Factory (para integración con InferencePipeline)
# ============================================================================

def create_visualization_sink(
    roi_state: Optional['ROIState'] = None,
    inference_handler: Optional['AdaptiveInferenceHandler'] = None,
    display_stats: bool = True,
    window_name: str = "Inference Pipeline",
):
    """
    Factory para crear sink function compatible con InferencePipeline.

    Args:
        roi_state: Estado del ROI (opcional)
        inference_handler: Handler de inferencia (opcional)
        display_stats: Si mostrar estadísticas
        window_name: Nombre de la ventana

    Returns:
        Función sink lista para usar con InferencePipeline
    """
    from functools import partial

    return partial(
        render_predictions_with_roi,
        roi_state=roi_state,
        inference_handler=inference_handler,
        display_stats=display_stats,
        window_name=window_name,
    )

"""
Detection Publisher
===================

Publisher especializado en formatear mensajes de detecciones.

Responsabilidad:
- Conoce estructura de detecciones (class, confidence, bbox)
- Formatea predicciones para MQTT
- Extrae ROI metadata si existe

Diseño: Complejidad por diseño
- Lógica de negocio separada de infraestructura MQTT
- SRP: solo formateo de detecciones
- NO conoce MQTT (eso es del DataPlane)
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from inference.core.interfaces.camera.entities import VideoFrame


class DetectionPublisher:
    """
    Publisher de detecciones.

    Formatea predicciones del modelo en mensajes MQTT.
    """

    def __init__(self):
        """Inicializa publisher."""
        self._message_count = 0

    def format_message(
        self,
        predictions: Union[Dict[str, Any], List[Dict[str, Any]]],
        video_frame: Optional[Union[VideoFrame, List[VideoFrame]]] = None
    ) -> Dict[str, Any]:
        """
        Formatea predicciones en mensaje MQTT.

        Args:
            predictions: Predicciones del modelo
            video_frame: Frame(s) de video (opcional)

        Returns:
            Diccionario con mensaje formateado
        """
        # Convertir a lista si es necesario
        if not isinstance(predictions, list):
            predictions = [predictions]

        # Construir mensaje
        message = self._build_message(predictions, video_frame)

        # Incrementar contador
        self._message_count += 1
        message["message_id"] = self._message_count

        return message

    def _build_message(
        self,
        predictions: List[Dict[str, Any]],
        video_frame: Optional[Union[VideoFrame, List[VideoFrame]]] = None
    ) -> Dict[str, Any]:
        """
        Construye el mensaje a partir de las predicciones.

        Extrae:
        - Detecciones (class, confidence, bbox)
        - ROI metadata (si existe)
        - Frame info (frame_id, source_id, timestamp)
        """
        # Extraer detecciones
        detections = []
        crop_metadata = None

        for pred in predictions:
            if isinstance(pred, dict):
                # Extraer crop metadata (solo del primer prediction)
                if crop_metadata is None and '__crop_metadata__' in pred:
                    crop_metadata = pred['__crop_metadata__']

                # Extraer predictions si existe
                pred_data = pred.get('predictions', pred)
                if isinstance(pred_data, list):
                    for detection in pred_data:
                        detections.append(self._extract_detection(detection))
                elif isinstance(pred_data, dict):
                    detections.append(self._extract_detection(pred_data))

        # Información del frame
        frame_info = {}
        if video_frame:
            frames = video_frame if isinstance(video_frame, list) else [video_frame]
            if frames and len(frames) > 0:
                frame = frames[0]
                frame_info = {
                    "frame_id": getattr(frame, 'frame_id', None),
                    "source_id": getattr(frame, 'source_id', None),
                    "timestamp": getattr(frame, 'frame_timestamp', datetime.now()).isoformat()
                }

        message = {
            "timestamp": datetime.now().isoformat(),
            "detection_count": len(detections),
            "detections": detections,
            "frame": frame_info,
        }

        # Agregar métricas de ROI si están disponibles (adaptive crop feature)
        if crop_metadata:
            message["roi_metrics"] = crop_metadata

        return message

    def _extract_detection(self, detection: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrae información relevante de una detección.

        Args:
            detection: Diccionario con detección del modelo

        Returns:
            Diccionario con campos estandarizados
        """
        return {
            "class": detection.get('class', detection.get('class_name', 'unknown')),
            "confidence": detection.get('confidence', 0.0),
            "bbox": {
                "x": detection.get('x', 0),
                "y": detection.get('y', 0),
                "width": detection.get('width', 0),
                "height": detection.get('height', 0)
            } if 'x' in detection else None,
            "class_id": detection.get('class_id'),
        }

    @property
    def message_count(self) -> int:
        """Retorna contador de mensajes formateados."""
        return self._message_count

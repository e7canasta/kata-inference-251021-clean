"""
MQTT Data Plane
===============

Data Plane para publicar resultados de inferencia vía MQTT (QoS 0).
Fire-and-forget para máxima performance.
"""
import json
import logging
from datetime import datetime
from threading import Event, Lock
from typing import Any, Dict, List, Optional, Union

import paho.mqtt.client as mqtt
from inference.core.interfaces.camera.entities import VideoFrame
from inference.core.interfaces.stream.watchdog import BasePipelineWatchDog

logger = logging.getLogger(__name__)


class MQTTDataPlane:
    """
    Data Plane para publicar resultados de inferencia vía MQTT.

    Publica las detecciones/inferencias del pipeline.
    """

    def __init__(
        self,
        broker_host: str,
        broker_port: int = 1883,
        data_topic: str = "inference/data/detections",
        metrics_topic: str = "inference/data/metrics",
        client_id: str = "inference_data",
        username: Optional[str] = None,
        password: Optional[str] = None,
        publish_full_frame: bool = False,
        qos: int = 0,
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.data_topic = data_topic
        self.metrics_topic = metrics_topic
        self.client_id = client_id
        self.publish_full_frame = publish_full_frame
        self.qos = qos
        self._watchdog: Optional[BasePipelineWatchDog] = None

        # MQTT Client
        self.client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv5)
        if username and password:
            self.client.username_pw_set(username, password)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

        self._connected = Event()
        self._lock = Lock()
        self._message_count = 0

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback cuando se conecta al broker"""
        if rc == 0:
            logger.info(f"✅ Data Plane conectado a {self.broker_host}:{self.broker_port}")
            self._connected.set()
        else:
            logger.error(f"❌ Error conectando Data Plane al broker MQTT: {rc}")

    def _on_disconnect(self, client, userdata, rc, properties=None):
        """Callback cuando se desconecta del broker"""
        logger.warning(f"⚠️ Data Plane desconectado (rc={rc})")
        self._connected.clear()

    def connect(self, timeout: float = 5.0) -> bool:
        """Conecta al broker MQTT"""
        try:
            logger.info(f"🔌 Conectando Data Plane a: {self.broker_host}:{self.broker_port}")
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            return self._connected.wait(timeout=timeout)
        except Exception as e:
            logger.error(f"❌ Error conectando Data Plane: {e}")
            return False

    def disconnect(self):
        """Desconecta del broker MQTT"""
        logger.info("🔌 Desconectando Data Plane...")
        self.client.loop_stop()
        self.client.disconnect()

    def publish_inference(
        self,
        predictions: Union[Dict[str, Any], List[Dict[str, Any]]],
        video_frame: Optional[Union[VideoFrame, List[VideoFrame]]] = None
    ):
        """
        Publica resultados de inferencia.

        Args:
            predictions: Predicciones del modelo
            video_frame: Frame(s) de video (opcional)
        """
        if not self._connected.is_set():
            logger.warning("⚠️ Data Plane no conectado, mensaje descartado")
            return

        try:
            # Convertir a lista si es necesario
            if not isinstance(predictions, list):
                predictions = [predictions]

            # Construir mensaje
            message = self._build_message(predictions, video_frame)

            # Publicar
            result = self.client.publish(
                self.data_topic,
                json.dumps(message, default=str),
                qos=self.qos
            )

            with self._lock:
                self._message_count += 1

            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.warning(f"⚠️ Error publicando mensaje: {result.rc}")

        except Exception as e:
            logger.error(f"❌ Error en publish_inference: {e}")

    def _build_message(
        self,
        predictions: List[Dict[str, Any]],
        video_frame: Optional[Union[VideoFrame, List[VideoFrame]]] = None
    ) -> Dict[str, Any]:
        """Construye el mensaje MQTT a partir de las predicciones"""

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
            "message_id": self._message_count,
        }

        # Agregar métricas de ROI si están disponibles (adaptive crop feature)
        if crop_metadata:
            message["roi_metrics"] = crop_metadata

        return message

    def _extract_detection(self, detection: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae información relevante de una detección"""
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

    def set_watchdog(self, watchdog: BasePipelineWatchDog):
        """
        Conecta un watchdog para publicar métricas del pipeline.

        Args:
            watchdog: Instancia de BasePipelineWatchDog del pipeline
        """
        self._watchdog = watchdog
        logger.info(f"📊 Watchdog conectado al Data Plane")

    def publish_metrics(self):
        """
        Publica métricas del watchdog vía MQTT.

        Publica en topic: inference/data/metrics
        Formato JSON con throughput, latencias por fuente, etc.
        """
        if not self._watchdog:
            logger.warning("⚠️ Watchdog no configurado, no se pueden publicar métricas")
            return

        if not self._connected.is_set():
            logger.warning("⚠️ Data Plane no conectado, métricas descartadas")
            return

        try:
            report = self._watchdog.get_report()

            # Construir mensaje con métricas
            message = {
                "timestamp": datetime.now().isoformat(),
                "throughput_fps": report.inference_throughput,
                "latency_reports": [
                    {
                        "source_id": getattr(lr, 'source_id', 0),
                        "frame_decoding_latency_ms": getattr(lr, 'frame_decoding_latency', 0),
                        "inference_latency_ms": getattr(lr, 'inference_latency', 0),
                        "e2e_latency_ms": getattr(lr, 'e2e_latency', 0),
                    }
                    for lr in report.latency_reports
                ],
                "sources_count": len(report.sources_metadata),
            }

            # Publicar
            result = self.client.publish(
                self.metrics_topic,
                json.dumps(message, default=str),
                qos=0  # Fire-and-forget para métricas
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"📊 Métricas publicadas: {report.inference_throughput:.2f} FPS")
            else:
                logger.warning(f"⚠️ Error publicando métricas: {result.rc}")

        except Exception as e:
            logger.error(f"❌ Error en publish_metrics: {e}", exc_info=True)

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del data plane"""
        with self._lock:
            return {
                "messages_published": self._message_count,
                "connected": self._connected.is_set(),
                "topic": self.data_topic,
            }

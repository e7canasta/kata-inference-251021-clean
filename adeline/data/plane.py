"""
MQTT Data Plane
===============

Data Plane para publicar resultados de inferencia vía MQTT (QoS 0).
Fire-and-forget para máxima performance.

Diseño: Complejidad por diseño
- MQTTDataPlane = infraestructura MQTT (canal/orquestador)
- Publishers = lógica de negocio (formateo de mensajes)
- SRP: Plane solo publica, Publishers formatean
"""
import json
import logging
from threading import Event, Lock
from typing import Any, Dict, List, Optional, Union

import paho.mqtt.client as mqtt
from inference.core.interfaces.camera.entities import VideoFrame
from inference.core.interfaces.stream.watchdog import BasePipelineWatchDog

from .publishers import DetectionPublisher, MetricsPublisher
from adeline.logging import (
    log_mqtt_publish,
    log_pipeline_metrics,
    log_error_with_context,
)

logger = logging.getLogger(__name__)


class MQTTDataPlane:
    """
    Data Plane para publicar resultados de inferencia vía MQTT.

    Responsabilidad: Infraestructura MQTT (canal/orquestador)
    - Conecta/desconecta de broker MQTT
    - Publica mensajes formateados por publishers
    - NO conoce estructura de mensajes (delega a publishers)

    Diseño: Complejidad por diseño
    - Plane = infraestructura (MQTT)
    - Publishers = lógica de negocio (formateo)
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

        # Publishers (lógica de negocio)
        self.detection_publisher = DetectionPublisher()
        self.metrics_publisher = MetricsPublisher()

        # MQTT Client (infraestructura)
        self.client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv5)
        if username and password:
            self.client.username_pw_set(username, password)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

        self._connected = Event()
        self._lock = Lock()

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback cuando se conecta al broker"""
        if rc == 0:
            logger.info(
                "✅ Data Plane conectado",
                extra={
                    "component": "data_plane",
                    "event": "connected",
                    "broker_host": self.broker_host,
                    "broker_port": self.broker_port,
                }
            )
            self._connected.set()
        else:
            log_error_with_context(
                logger,
                message=f"❌ Error conectando Data Plane al broker MQTT: {rc}",
                error_code=f"mqtt_rc_{rc}",
                component="data_plane",
                event="connection_failed",
                broker_host=self.broker_host,
                broker_port=self.broker_port,
            )

    def _on_disconnect(self, client, userdata, rc, properties=None):
        """Callback cuando se desconecta del broker"""
        logger.warning(
            "⚠️ Data Plane desconectado",
            extra={
                "component": "data_plane",
                "event": "disconnected",
                "rc": rc,
            }
        )
        self._connected.clear()

    def connect(self, timeout: float = 5.0) -> bool:
        """Conecta al broker MQTT"""
        try:
            logger.info(
                "🔌 Conectando Data Plane",
                extra={
                    "component": "data_plane",
                    "event": "connecting",
                    "broker_host": self.broker_host,
                    "broker_port": self.broker_port,
                    "timeout": timeout,
                }
            )
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            return self._connected.wait(timeout=timeout)
        except Exception as e:
            log_error_with_context(
                logger,
                message="❌ Error conectando Data Plane",
                exception=e,
                component="data_plane",
                event="connection_error",
                broker_host=self.broker_host,
                broker_port=self.broker_port,
            )
            return False

    def disconnect(self):
        """Desconecta del broker MQTT"""
        logger.info(
            "🔌 Desconectando Data Plane",
            extra={
                "component": "data_plane",
                "event": "disconnecting",
            }
        )
        self.client.loop_stop()
        self.client.disconnect()

    def publish_inference(
        self,
        predictions: Union[Dict[str, Any], List[Dict[str, Any]]],
        video_frame: Optional[Union[VideoFrame, List[VideoFrame]]] = None
    ):
        """
        Publica resultados de inferencia.

        Responsabilidad: Solo publicar (infraestructura)
        - Delega formateo a DetectionPublisher (lógica de negocio)
        - Publica mensaje formateado vía MQTT

        Args:
            predictions: Predicciones del modelo
            video_frame: Frame(s) de video (opcional)
        """
        if not self._connected.is_set():
            logger.warning(
                "⚠️ Data Plane no conectado, mensaje descartado",
                extra={
                    "component": "data_plane",
                    "event": "publish_skipped",
                    "reason": "not_connected",
                }
            )
            return

        try:
            # Formatear mensaje (delega a publisher)
            message = self.detection_publisher.format_message(predictions, video_frame)

            # Publicar (infraestructura MQTT)
            result = self.client.publish(
                self.data_topic,
                json.dumps(message, default=str),
                qos=self.qos
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                # Log exitoso con helper
                num_detections = len(message.get('detections', []))
                log_mqtt_publish(
                    logger,
                    topic=self.data_topic,
                    qos=self.qos,
                    payload_size=len(json.dumps(message, default=str)),
                    num_detections=num_detections,
                )
            else:
                logger.warning(
                    "⚠️ Error publicando mensaje",
                    extra={
                        "component": "data_plane",
                        "event": "publish_failed",
                        "mqtt_rc": result.rc,
                        "topic": self.data_topic,
                    }
                )

        except Exception as e:
            log_error_with_context(
                logger,
                message="❌ Error en publish_inference",
                exception=e,
                component="data_plane",
                event="publish_exception",
                topic=self.data_topic,
            )

    def set_watchdog(self, watchdog: BasePipelineWatchDog):
        """
        Conecta un watchdog para publicar métricas del pipeline.

        Delega a MetricsPublisher (lógica de negocio).

        Args:
            watchdog: Instancia de BasePipelineWatchDog del pipeline
        """
        self.metrics_publisher.set_watchdog(watchdog)
        logger.info(
            "📊 Watchdog conectado al Data Plane",
            extra={
                "component": "data_plane",
                "event": "watchdog_connected",
            }
        )

    def publish_metrics(self):
        """
        Publica métricas del watchdog vía MQTT.

        Responsabilidad: Solo publicar (infraestructura)
        - Delega formateo a MetricsPublisher (lógica de negocio)
        - Publica mensaje formateado vía MQTT

        Publica en topic: inference/data/metrics
        """
        if not self.metrics_publisher.has_watchdog:
            logger.warning(
                "⚠️ Watchdog no configurado, no se pueden publicar métricas",
                extra={
                    "component": "data_plane",
                    "event": "publish_metrics_skipped",
                    "reason": "no_watchdog",
                }
            )
            return

        if not self._connected.is_set():
            logger.warning(
                "⚠️ Data Plane no conectado, métricas descartadas",
                extra={
                    "component": "data_plane",
                    "event": "publish_metrics_skipped",
                    "reason": "not_connected",
                }
            )
            return

        try:
            # Formatear mensaje (delega a publisher)
            message = self.metrics_publisher.format_message()

            if message is None:
                logger.warning(
                    "⚠️ No se pudo formatear mensaje de métricas",
                    extra={
                        "component": "data_plane",
                        "event": "format_failed",
                    }
                )
                return

            # Publicar (infraestructura MQTT)
            result = self.client.publish(
                self.metrics_topic,
                json.dumps(message, default=str),
                qos=0  # Fire-and-forget para métricas
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                # Usar helper para métricas del pipeline
                throughput = message.get('throughput_fps', 0)
                latency_ms = message.get('latency_ms', None)

                log_pipeline_metrics(
                    logger,
                    fps=throughput,
                    latency_ms=latency_ms,
                    component="data_plane",
                )
            else:
                logger.warning(
                    "⚠️ Error publicando métricas",
                    extra={
                        "component": "data_plane",
                        "event": "publish_metrics_failed",
                        "mqtt_rc": result.rc,
                        "topic": self.metrics_topic,
                    }
                )

        except Exception as e:
            log_error_with_context(
                logger,
                message="❌ Error en publish_metrics",
                exception=e,
                component="data_plane",
                event="publish_metrics_exception",
                topic=self.metrics_topic,
            )

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del data plane"""
        with self._lock:
            return {
                "messages_published": self.detection_publisher.message_count,
                "connected": self._connected.is_set(),
                "topic": self.data_topic,
            }

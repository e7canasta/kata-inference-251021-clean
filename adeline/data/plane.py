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

        Responsabilidad: Solo publicar (infraestructura)
        - Delega formateo a DetectionPublisher (lógica de negocio)
        - Publica mensaje formateado vía MQTT

        Args:
            predictions: Predicciones del modelo
            video_frame: Frame(s) de video (opcional)
        """
        if not self._connected.is_set():
            logger.warning("⚠️ Data Plane no conectado, mensaje descartado")
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

            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.warning(f"⚠️ Error publicando mensaje: {result.rc}")

        except Exception as e:
            logger.error(f"❌ Error en publish_inference: {e}")

    def set_watchdog(self, watchdog: BasePipelineWatchDog):
        """
        Conecta un watchdog para publicar métricas del pipeline.

        Delega a MetricsPublisher (lógica de negocio).

        Args:
            watchdog: Instancia de BasePipelineWatchDog del pipeline
        """
        self.metrics_publisher.set_watchdog(watchdog)
        logger.info("📊 Watchdog conectado al Data Plane")

    def publish_metrics(self):
        """
        Publica métricas del watchdog vía MQTT.

        Responsabilidad: Solo publicar (infraestructura)
        - Delega formateo a MetricsPublisher (lógica de negocio)
        - Publica mensaje formateado vía MQTT

        Publica en topic: inference/data/metrics
        """
        if not self.metrics_publisher.has_watchdog:
            logger.warning("⚠️ Watchdog no configurado, no se pueden publicar métricas")
            return

        if not self._connected.is_set():
            logger.warning("⚠️ Data Plane no conectado, métricas descartadas")
            return

        try:
            # Formatear mensaje (delega a publisher)
            message = self.metrics_publisher.format_message()

            if message is None:
                logger.warning("⚠️ No se pudo formatear mensaje de métricas")
                return

            # Publicar (infraestructura MQTT)
            result = self.client.publish(
                self.metrics_topic,
                json.dumps(message, default=str),
                qos=0  # Fire-and-forget para métricas
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                throughput = message.get('throughput_fps', 0)
                logger.info(f"📊 Métricas publicadas: {throughput:.2f} FPS")
            else:
                logger.warning(f"⚠️ Error publicando métricas: {result.rc}")

        except Exception as e:
            logger.error(f"❌ Error en publish_metrics: {e}", exc_info=True)

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del data plane"""
        with self._lock:
            return {
                "messages_published": self.detection_publisher.message_count,
                "connected": self._connected.is_set(),
                "topic": self.data_topic,
            }
